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

from . import pricing, reader, transcripts
from .schema import ClaudeUsage, DayBurn, ManualOverride, ModelBurn, ProjectBurn

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


def _fmt_reset_in(resets_at: float | int) -> str | None:
    """Unix-epoch reset → human countdown from now. None if past/invalid.

    Rolls hours into days past 24h so a 7-day reset reads "6d 3h" not "147h 25m":
      < 1h  → "45m"
      < 24h → "3h 12m"
      ≥ 24h → "6d 3h"  (minutes dropped once we're showing days — not useful at that scale)
    """
    try:
        reset = datetime.fromtimestamp(float(resets_at), tz=timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError):
        return None
    delta = reset - datetime.now(timezone.utc)
    secs = delta.total_seconds()
    if secs <= 0:
        return None
    days = int(secs // 86400)
    hours = int((secs % 86400) // 3600)
    mins = int((secs % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def _parse_quota(quota: dict | None) -> dict:
    """Live quota snapshot → {pct5h, reset5h, pctWeek, resetWeek, ctxPct, ctxUsed, ctxMax, ctxModel}.

    All keys default to None — a missing/partial snapshot never raises (the file is
    only fresh while Claude Code is running). five_hour/seven_day carry
    used_percentage + resets_at (Unix epoch). context is the CURRENT SESSION's window
    (model-dependent: opus 1M, sonnet 200k), NOT a quota — carries used %, the raw
    token count, and the window size so the FE shows "312k / 1M" of THIS session.
    """
    out: dict = {
        "pct5h": None, "reset5h": None, "pctWeek": None, "resetWeek": None,
        "ctxPct": None, "ctxUsed": None, "ctxMax": None, "ctxModel": None,
    }
    if not isinstance(quota, dict):
        return out
    fh = quota.get("five_hour")
    if isinstance(fh, dict):
        if isinstance(fh.get("used_percentage"), (int, float)):
            out["pct5h"] = round(float(fh["used_percentage"]), 1)
        if fh.get("resets_at") is not None:
            out["reset5h"] = _fmt_reset_in(fh["resets_at"])
    sd = quota.get("seven_day")
    if isinstance(sd, dict):
        if isinstance(sd.get("used_percentage"), (int, float)):
            out["pctWeek"] = round(float(sd["used_percentage"]), 1)
        if sd.get("resets_at") is not None:
            out["resetWeek"] = _fmt_reset_in(sd["resets_at"])
    ctx = quota.get("context")
    if isinstance(ctx, dict):
        if isinstance(ctx.get("used_percentage"), (int, float)):
            out["ctxPct"] = round(float(ctx["used_percentage"]), 1)
        if isinstance(ctx.get("total_input_tokens"), (int, float)):
            out["ctxUsed"] = int(ctx["total_input_tokens"])
        if isinstance(ctx.get("context_window_size"), (int, float)):
            out["ctxMax"] = int(ctx["context_window_size"])
    if isinstance(quota.get("model"), str):
        out["ctxModel"] = quota["model"]
    return out


# --------------------------------------------------------------------------- #
# Build the view from LIVE transcripts (Agg → ClaudeUsage parts)                #
# --------------------------------------------------------------------------- #
def _agg_cost(a: "transcripts.Agg", model: str) -> float:
    """Cost for one model's Agg via the pricing table (includes cache tokens)."""
    return pricing.compute_cost(
        a.input, a.output, model,
        cache_read=a.cacheRead, cache_create=a.cacheCreate, cache_create_1h=a.cacheCreate1h,
    )


def _series_from_agg(agg: "transcripts.Agg") -> list[DayBurn]:
    """Last 7 calendar days of output tokens (newest last) — zero-filled for gaps."""
    if not agg.byDate:
        return []
    last7 = sorted(agg.byDate)[-7:]
    return [DayBurn(date=d, label=_weekday_label(d), tokens=int(agg.byDate[d])) for d in last7]


def _bymodel_from_agg(agg: "transcripts.Agg") -> list[ModelBurn]:
    """Per-model burn + derived cost, sorted total desc."""
    out: list[ModelBurn] = []
    for model, a in agg.byModel.items():
        out.append(ModelBurn(
            model=model, inputTokens=a.input, outputTokens=a.output,
            cacheReadTokens=a.cacheRead, cacheCreateTokens=a.cacheCreate,
            total=a.input + a.output, costUSD=_agg_cost(a, model),
        ))
    out.sort(key=lambda b: b.total, reverse=True)
    return out


def _byproject_from_agg(agg: "transcripts.Agg", limit: int = 12) -> list[ProjectBurn]:
    """Per-project burn + cost, sorted total desc, capped to ``limit``.

    Cost is priced EXACTLY: each project Agg carries its own per-model split, so we
    sum compute_cost per model (an opus-heavy project is priced at opus, a sonnet
    one at sonnet — no blended-rate distortion)."""
    out: list[ProjectBurn] = []
    for proj, a in agg.byProject.items():
        cost = sum(_agg_cost(am, model) for model, am in a.byModel.items())
        out.append(ProjectBurn(
            project=proj, inputTokens=a.input, outputTokens=a.output,
            cacheReadTokens=a.cacheRead, cacheCreateTokens=a.cacheCreate,
            total=a.input + a.output, costUSD=round(cost, 4), msgs=a.msgs,
        ))
    out.sort(key=lambda b: b.total, reverse=True)
    return out[:limit]


def _top_model_label(agg: "transcripts.Agg") -> str:
    """Most-used model by total tokens (for headline + project pricing fallback)."""
    if not agg.byModel:
        return "—"
    return max(agg.byModel.items(), key=lambda kv: kv[1].input + kv[1].output)[0]


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

    # Live quota snapshot (5h/7d/context) — priority: manual override > snapshot > stub.
    q = _parse_quota(reader.read_quota())
    has_snapshot = any(q[k] is not None for k in ("pct5h", "pctWeek", "ctxPct"))
    # resetIn: manual override wins, else live 5h reset countdown.
    reset_in = override.resetIn if override.resetIn is not None else q["reset5h"]
    # weekly %: manual override wins, else live 7-day used %.
    weekly = override.weekly if override.weekly is not None else (
        int(round(q["pctWeek"])) if q["pctWeek"] is not None else None
    )
    quota_source = "manual" if (override.resetIn is not None or override.weekly is not None) else (
        "snapshot" if has_snapshot else "stub"
    )
    yesterday_iso = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    def _finish(*, model, series, by_model, by_project, cost_usd, as_of, stale, token_source):
        """Common tail — applies cap/pct/today/avg/peak + the resolved quota fields."""
        today = series[-1].tokens if series else 0
        avg_per_day = round(sum(d.tokens for d in series) / len(series)) if series else 0
        peak = max(series, key=lambda d: d.tokens) if series else _zero_day()
        used = today  # active window default = today's total
        # NG1 (source fix): pct is the QUOTA-WINDOW used %, NOT used/cap. cap is a
        # context-WINDOW allowance (200k), used is today's TOKEN count (~8.9M) → used/cap
        # reads ~4500% garbage that leaked to EVERY consumer (raw tool / life_brief /
        # daily_brief). Derive from the sane snapshot window: pct5h, else weekly, else
        # None. Clamped 0-100. NEVER used/cap. (weekly is the resolved field above —
        # NOT pctWeek, which is only the internal dict key; SYNTH lesson.)
        pct: float | None
        if q["pct5h"] is not None:
            pct = round(min(max(float(q["pct5h"]), 0.0), 100.0), 1)
        elif weekly is not None:
            pct = round(min(max(float(weekly), 0.0), 100.0), 1)
        else:
            pct = None
        # remaining off the broken used/cap is meaningless (used >> cap → always 0);
        # null it when used exceeds cap (honest — we don't know the real token quota).
        remaining = max(cap - used, 0) if used <= cap else None
        return ClaudeUsage(
            model=model, used=used, cap=cap, pct=pct, remaining=remaining,
            resetIn=reset_in, weekly=weekly, pct5h=q["pct5h"], resetWeek=q["resetWeek"],
            ctxPct=q["ctxPct"], ctxUsed=q["ctxUsed"], ctxMax=q["ctxMax"], ctxModel=q["ctxModel"],
            quotaSource=quota_source, series=series, today=today,
            avgPerDay=avg_per_day, peak=peak, byModel=by_model, costUSD=cost_usd,
            byProject=by_project, tokenSource=token_source, asOf=as_of, stale=stale,
            source=token_source,
        )

    # --- PRIMARY: live session transcripts (.jsonl) — real tokens + byProject ----
    agg = transcripts.aggregate()
    if agg is not None and agg.msgs > 0:
        series = _series_from_agg(agg)
        by_model = _bymodel_from_agg(agg)
        by_project = _byproject_from_agg(agg)
        cost_usd = round(sum(b.costUSD for b in by_model), 4)
        as_of = max(agg.byDate) if agg.byDate else today_iso
        return _finish(
            model=_top_model_label(agg), series=series, by_model=by_model,
            by_project=by_project, cost_usd=cost_usd, as_of=as_of,
            stale=as_of < yesterday_iso, token_source="transcripts",
        )

    # --- FALLBACK: stats-cache.json (legacy; usually dead now) ------------------
    if stats is None:
        # Fail-open manual mode — never 500.
        return _finish(
            model="—", series=[], by_model=[], by_project=[], cost_usd=0.0,
            as_of=today_iso, stale=False, token_source="none",
        )

    series = _parse_series(stats)
    by_model = _parse_by_model(stats)
    top_model = by_model[0].model if by_model else "—"
    cost_usd = round(sum(b.costUSD for b in by_model), 4)
    _as_of_raw = stats.get("lastComputedDate")  # Any | None from the stats dict
    as_of = _as_of_raw if isinstance(_as_of_raw, str) else today_iso  # #57: narrow to str (non-str → today)
    return _finish(
        model=top_model, series=series, by_model=by_model, by_project=[],
        cost_usd=cost_usd, as_of=as_of, stale=as_of < yesterday_iso,
        token_source="stats-cache",
    )
