"""modules/claude_usage/service.py — assemble ClaudeUsage (Sprint 7, SPEC §S9).

Reads stats-cache (reader), derives cost (pricing), applies the manual override
(md_store `claude_usage/override.md`). All derived per the architect's Logic
block. Fail-open: no stats-cache → manual mode, never 500.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import yaml

from core.config import settings
from store import md_store

from . import pricing, reader
from .schema import ClaudeUsage, DayBurn, ManualOverride, ModelBurn

logger = logging.getLogger("life-os.claude_usage.service")

OVERRIDE_MD = "claude_usage/override.md"
# Vietnamese weekday short labels, Monday=0 .. Sunday=6.
_WEEKDAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]


def is_claude(model: str) -> bool:
    """True for Claude models only. This is the CLAUDE Usage screen — non-Claude
    models (MiniMax/glm/arcee/...) in the same stats-cache are EXCLUDED from every
    derived figure, else e.g. MiniMax's 4.66B tokens priced at the sonnet fallback
    would headline a garbage $55K cost. The fallback now only catches an unknown
    CLAUDE model, never a non-Claude one.
    """
    return model.startswith("claude-")


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _weekday_label(date_str: str) -> str:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return date_str
    return _WEEKDAY_LABELS[d.weekday()]


# --------------------------------------------------------------------------- #
# Manual override (md_store)                                                    #
# --------------------------------------------------------------------------- #
def _load_override() -> ManualOverride:
    try:
        content = md_store.read(OVERRIDE_MD)
    except Exception as exc:
        logger.warning("override.md read failed: %s", exc)
        content = None
    if not content:
        return ManualOverride()
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return ManualOverride()
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return ManualOverride()
    if not isinstance(data, dict):
        return ManualOverride()
    try:
        return ManualOverride(cap=data.get("cap"), resetIn=data.get("resetIn"), weekly=data.get("weekly"))
    except Exception:
        return ManualOverride()


def set_override(override: ManualOverride) -> ClaudeUsage:
    """Persist a manual override (one md_store commit) + return the fresh usage."""
    payload = {"cap": override.cap, "resetIn": override.resetIn, "weekly": override.weekly}
    body = "---\n" + yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).strip() + "\n---\n"
    md_store.write_file(OVERRIDE_MD, body, "set claude-usage override")
    return get_usage()


# --------------------------------------------------------------------------- #
# Section parsers (per-section try/except — one bad part never sinks the rest)  #
# --------------------------------------------------------------------------- #
def _parse_series(stats: dict) -> list[DayBurn]:
    """Last 7 dailyModelTokens entries → DayBurn list (oldest→newest)."""
    dmt = stats.get("dailyModelTokens")
    if not isinstance(dmt, list):
        return []
    series: list[DayBurn] = []
    for entry in dmt[-7:]:
        if not isinstance(entry, dict):
            continue
        date = entry.get("date")
        by = entry.get("tokensByModel")
        if not isinstance(date, str) or not isinstance(by, dict):
            continue
        # Claude-only: sum tokens for claude-* keys, exclude MiniMax/glm/etc.
        tokens = sum(v for k, v in by.items() if is_claude(str(k)) and isinstance(v, (int, float)))
        series.append(DayBurn(date=date, label=_weekday_label(date), tokens=int(tokens)))
    return series


def _parse_by_model(stats: dict) -> list[ModelBurn]:
    """modelUsage → ModelBurn list, cost derived, sorted total desc."""
    mu = stats.get("modelUsage")
    if not isinstance(mu, dict):
        return []
    out: list[ModelBurn] = []
    for model, m in mu.items():
        if not is_claude(str(model)):
            continue  # Claude-only screen — exclude non-Claude models entirely
        if not isinstance(m, dict):
            continue
        in_tok = int(m.get("inputTokens", 0) or 0)
        out_tok = int(m.get("outputTokens", 0) or 0)
        cache_r = int(m.get("cacheReadInputTokens", 0) or 0)
        cache_c = int(m.get("cacheCreationInputTokens", 0) or 0)
        out.append(ModelBurn(
            model=model, inputTokens=in_tok, outputTokens=out_tok,
            cacheReadTokens=cache_r, cacheCreateTokens=cache_c,
            total=in_tok + out_tok,
            costUSD=pricing.compute_cost(in_tok, out_tok, model, cache_read=cache_r, cache_create=cache_c),
        ))
    out.sort(key=lambda b: b.total, reverse=True)
    return out


def _zero_day() -> DayBurn:
    return DayBurn(date=_today_iso(), label=_weekday_label(_today_iso()), tokens=0)


# --------------------------------------------------------------------------- #
# Assemble                                                                      #
# --------------------------------------------------------------------------- #
def get_usage(window: str = "5h") -> ClaudeUsage:
    """The composite ClaudeUsage view. Fail-open to manual mode if no stats-cache.

    ``window`` is accepted for the API contract but the active window = today's
    total this sprint (the 5h-window state isn't readable from disk).
    """
    override = _load_override()
    cap = override.cap if override.cap is not None else settings.claude_usage_cap
    today_iso = _today_iso()
    stats = reader.read_stats()

    if stats is None:
        # Fail-open manual mode — never 500.
        used = 0
        pct = round(used / cap * 100, 1) if cap > 0 else 0.0
        return ClaudeUsage(
            model="—", used=used, cap=cap, pct=pct, remaining=max(cap - used, 0),
            resetIn=override.resetIn, weekly=override.weekly, series=[], today=0,
            avgPerDay=0, peak=_zero_day(), byModel=[], costUSD=0.0, byProject=None,
            asOf=today_iso, stale=False, source="manual",
        )

    series = _parse_series(stats)
    by_model = _parse_by_model(stats)

    today = series[-1].tokens if series else 0
    avg_per_day = round(sum(d.tokens for d in series) / len(series)) if series else 0
    peak = max(series, key=lambda d: d.tokens) if series else _zero_day()
    top_model = by_model[0].model if by_model else "—"
    cost_usd = round(sum(b.costUSD for b in by_model), 4)

    used = today  # active window default = today's total
    pct = round(used / cap * 100, 1) if cap > 0 else 0.0

    as_of = stats.get("lastComputedDate")
    if not isinstance(as_of, str):
        as_of = today_iso
    # 1-day grace: a cache computed yesterday is still "fresh". stale only when
    # lastComputedDate is older than yesterday (architect refinement).
    yesterday_iso = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    stale = as_of < yesterday_iso

    return ClaudeUsage(
        model=top_model, used=used, cap=cap, pct=pct, remaining=max(cap - used, 0),
        resetIn=override.resetIn, weekly=override.weekly, series=series, today=today,
        avgPerDay=avg_per_day, peak=peak, byModel=by_model, costUSD=cost_usd,
        byProject=None, asOf=as_of, stale=stale, source="stats-cache",
    )
