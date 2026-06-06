"""modules/finance/service.py — finance orchestration (Sprint 4, SPEC §S5/§S6).

Holdings persist in md_store `finance/holdings.md` (YAML list); the golden-path
(channel targets + per-channel buy-ladder) in `finance/golden_path.md` — absent →
BASELINE (crypto 38 / etf 24 / vn 18 / dry 20, ladder rungs -10/-20/-30%) +
warning. Current prices come from the market module (`market.service.get_quote`,
fail-open — NO re-fetch). All derived numbers carry their inputs (self-describing).

Decide-and-log (architect Logic block, verbatim):
  - 4 channels: crypto / etf / vn / dry (dry = dry powder).
  - drift = actualPct - targetPct; driftAlert = |drift| > 5 (BACKEND owns the rule).
  - P&L: current = price*qty, cost = avgCost*qty, abs = current-cost,
    pct = abs/cost*100 (cost==0 → null, no ÷0).
  - ladder: triggerPrice = reference*(1+rung/100); rungsIn = #rungs where
    currentPrice ≤ triggerPrice (entered); nextRung = first rung not yet entered;
    distancePct = (currentPrice - nextTrigger)/currentPrice*100.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import yaml

from modules.market import service as market_service
from store import db, md_store

from .schema import (
    Change,
    ChannelAlloc,
    FinanceOverview,
    GoldenPathInput,
    Holding,
    HoldingInput,
    LadderState,
    PnL,
)

logger = logging.getLogger("life-os.finance.service")

HOLDINGS_MD = "finance/holdings.md"
GOLDEN_PATH_MD = "finance/golden_path.md"
DRIFT_ALERT_PCT = 5.0
DRY_CHANNEL = "dry"
CHANNELS = ("crypto", "etf", "vn", "dry")

BASELINE_TARGETS: dict[str, float] = {"crypto": 38.0, "etf": 24.0, "vn": 18.0, "dry": 20.0}
BASELINE_RUNGS: list[float] = [-10.0, -20.0, -30.0]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# md_store front-matter helpers                                                 #
# --------------------------------------------------------------------------- #
def _parse_front_matter(content: str | None) -> dict:
    if not content:
        return {}
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return {}
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        logger.warning("malformed finance front-matter, ignoring: %s", exc)
        return {}
    return data if isinstance(data, dict) else {}


def _write_front_matter(path: str, payload: dict, msg: str) -> None:
    body = "---\n" + yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).strip() + "\n---\n"
    md_store.write_file(path, body, msg)


# --------------------------------------------------------------------------- #
# Holdings                                                                      #
# --------------------------------------------------------------------------- #
def list_holdings() -> list[Holding]:
    try:
        content = md_store.read(HOLDINGS_MD)
    except Exception as exc:
        logger.warning("holdings.md read failed: %s", exc)
        return []
    data = _parse_front_matter(content)
    out: list[Holding] = []
    for item in data.get("holdings", []) or []:
        try:
            out.append(Holding(**item))
        except Exception as exc:
            logger.warning("skipping invalid holding %r: %s", item, exc)
    return out


def _write_holdings(holdings: list[Holding]) -> None:
    _write_front_matter(HOLDINGS_MD, {"holdings": [h.model_dump() for h in holdings]}, "update holdings")


def upsert_holding(body: HoldingInput) -> Holding:
    """Add or replace (by symbol) a holding. Returns it."""
    holdings = [h for h in list_holdings() if h.symbol != body.symbol]
    holding = Holding(
        channel=body.channel, symbol=body.symbol, qty=body.qty,
        avgCost=body.avgCost, source=body.source, asOf=_now_iso(),
    )
    holdings.append(holding)
    _write_holdings(holdings)
    return holding


def delete_holding(symbol: str) -> bool:
    """Delete the holding with this symbol. True if removed."""
    holdings = list_holdings()
    kept = [h for h in holdings if h.symbol != symbol]
    removed = len(kept) != len(holdings)
    if removed:
        _write_holdings(kept)
    return removed


# --------------------------------------------------------------------------- #
# Golden path (targets + per-channel ladder) — baseline fallback                #
# --------------------------------------------------------------------------- #
def get_golden_path() -> tuple[dict[str, float], dict[str, dict], list[str]]:
    """(targets, ladder, warnings). Absent/malformed → baseline + warning.

    ladder: {channel: {reference: float, rungs: [float]}}.
    """
    try:
        content = md_store.read(GOLDEN_PATH_MD)
    except Exception as exc:
        logger.warning("golden_path.md read failed: %s", exc)
        content = None
    data = _parse_front_matter(content)
    targets = data.get("targets")
    ladder = data.get("ladder")
    warnings: list[str] = []
    if not isinstance(targets, dict) or not targets:
        targets = dict(BASELINE_TARGETS)
        warnings.append("golden-path absent — using baseline targets (crypto38/etf24/vn18/dry20)")
    else:
        targets = {str(k): float(v) for k, v in targets.items()}
    if not isinstance(ladder, dict):
        ladder = {}
    return targets, ladder, warnings


def set_golden_path(body: GoldenPathInput) -> tuple[dict[str, float], dict[str, dict]]:
    targets = {str(k): float(v) for k, v in body.targets.items()}
    ladder = {str(k): v for k, v in (body.ladder or {}).items()}
    _write_front_matter(GOLDEN_PATH_MD, {"targets": targets, "ladder": ladder}, "set golden path")
    return targets, ladder


# --------------------------------------------------------------------------- #
# Pricing + P&L                                                                 #
# --------------------------------------------------------------------------- #
def _price_of(symbol: str, avg_cost: float) -> tuple[float, str, str | None]:
    """(price, source, warning). Fail-open: no quote → avgCost as price + warning."""
    quote = market_service.get_quote(symbol)
    if quote is not None and quote.price > 0:
        return quote.price, quote.source, None
    return avg_cost, "cost-fallback", f"{symbol}: no market price — using avgCost"


def _pnl(cost: float, current: float) -> PnL:
    abs_ = round(current - cost, 2)
    pct = round(abs_ / cost * 100.0, 2) if cost > 0 else None
    return PnL(cost=round(cost, 2), current=round(current, 2), abs=abs_, pct=pct)


# --------------------------------------------------------------------------- #
# Ladder                                                                        #
# --------------------------------------------------------------------------- #
def _ladder_for(channel: str, reference: float, current: float, rungs: list[float]) -> LadderState:
    """rungsIn = #rungs where current ≤ triggerPrice (entered); nextRung = first
    rung not yet entered (current > trigger); distancePct to it."""
    # rungs are negative offsets; triggers descend. Sort by trigger DESC (closest first).
    rung_triggers = sorted(
        ((r, reference * (1 + r / 100.0)) for r in rungs),
        key=lambda rt: rt[1], reverse=True,
    )
    rungs_in = sum(1 for _r, t in rung_triggers if current <= t)
    next_rung = None
    distance_pct = None
    for r, t in rung_triggers:
        if current > t:  # not yet entered (price still above this trigger)
            next_rung = {"pct": round(r, 2), "triggerPrice": round(t, 2)}
            distance_pct = round((current - t) / current * 100.0, 2) if current > 0 else None
            break
    return LadderState(
        channel=channel,  # type: ignore[arg-type]  # validated channel string
        referencePrice=round(reference, 2), currentPrice=round(current, 2),
        rungsIn=rungs_in, nextRung=next_rung, distancePct=distance_pct,
    )


# --------------------------------------------------------------------------- #
# Aggregation + overview + channel detail                                       #
# --------------------------------------------------------------------------- #
def _aggregate(holdings: list[Holding]) -> tuple[dict, list[str]]:
    """Per-channel {value, cost, holdings:[{holding, price, source, value, pnl}]}."""
    warnings: list[str] = []
    by_channel: dict[str, dict] = {}
    for h in holdings:
        price, source, warn = _price_of(h.symbol, h.avgCost)
        if warn:
            warnings.append(warn)
        value = round(price * h.qty, 2)
        cost = round(h.avgCost * h.qty, 2)
        ch = by_channel.setdefault(h.channel, {"value": 0.0, "cost": 0.0, "holdings": []})
        ch["value"] = round(ch["value"] + value, 2)
        ch["cost"] = round(ch["cost"] + cost, 2)
        ch["holdings"].append({
            "holding": h.model_dump(), "price": price, "source": source,
            "value": value, "pnl": _pnl(cost, value).model_dump(),
        })
    return by_channel, warnings


def _series() -> list[float]:
    """Portfolio value over time — [] this build (no snapshot routine, north-star)."""
    return []


def get_overview() -> tuple[FinanceOverview, list[str]]:
    holdings = list_holdings()
    targets, _ladder, gp_warnings = get_golden_path()
    by_channel, price_warnings = _aggregate(holdings)
    warnings = gp_warnings + price_warnings

    total_value = round(sum(c["value"] for c in by_channel.values()), 2)
    total_cost = round(sum(c["cost"] for c in by_channel.values()), 2)
    dry_powder = round(by_channel.get(DRY_CHANNEL, {}).get("value", 0.0), 2)

    allocations: list[ChannelAlloc] = []
    channels = set(by_channel) | set(targets)
    for ch in sorted(channels):
        # Fail-open on stale/unknown STORED channels: a golden_path or holding may
        # carry a channel from an older naming (e.g. 'cash' before cash→dry). It is
        # NOT in the Channel Literal → building a ChannelAlloc(channel=ch) would
        # raise and 500 the overview. Skip + warn instead (the service owns
        # resilience against its own store — cf. 3B status.md repo-path).
        if ch not in CHANNELS:
            warnings.append(f"ignored unknown stored channel {ch!r} — not in {'/'.join(CHANNELS)}")
            continue
        value = round(by_channel.get(ch, {}).get("value", 0.0), 2)
        cost = round(by_channel.get(ch, {}).get("cost", 0.0), 2)
        pct = round(value / total_value * 100.0, 2) if total_value > 0 else 0.0
        target = round(float(targets.get(ch, 0.0)), 2)
        drift = round(pct - target, 2)
        drift_alert = abs(drift) > DRIFT_ALERT_PCT
        if drift_alert:
            warnings.append(f"{ch}: allocation drift {drift:+.1f}% (target {target}%, actual {pct}%)")
        allocations.append(ChannelAlloc(
            channel=ch, value=value, pct=pct, target=target, drift=drift,  # type: ignore[arg-type]
            driftAlert=drift_alert, pnl=_pnl(cost, value),
        ))

    overview = FinanceOverview(
        totalValue=total_value,
        change=Change(abs=0.0, pct=None) if total_value else None,
        holdings=holdings,
        allocations=allocations,
        pnlTotal=_pnl(total_cost, total_value),
        dryPowder=dry_powder,
        series=_series(),
    )
    return overview, warnings


def get_channel(channel: str) -> tuple[dict | None, list[str]]:
    """S6 detail: a channel's holdings + ChannelAlloc + LadderState. None if unknown."""
    targets, ladder_cfg, gp_warnings = get_golden_path()
    ch_holdings = [h for h in list_holdings() if h.channel == channel]
    if not ch_holdings and channel not in targets:
        return None, []

    all_by_channel, price_warnings = _aggregate(list_holdings())
    warnings = gp_warnings + price_warnings
    agg = all_by_channel.get(channel, {"value": 0.0, "cost": 0.0, "holdings": []})

    total_value = round(sum(c["value"] for c in all_by_channel.values()), 2)
    pct = round(agg["value"] / total_value * 100.0, 2) if total_value > 0 else 0.0
    target = round(float(targets.get(channel, 0.0)), 2)
    drift = round(pct - target, 2)
    drift_alert = abs(drift) > DRIFT_ALERT_PCT

    # Ladder from golden_path config for this channel (reference + rungs).
    ladder = None
    cfg = ladder_cfg.get(channel) if isinstance(ladder_cfg, dict) else None
    if isinstance(cfg, dict) and isinstance(cfg.get("reference"), (int, float)):
        reference = float(cfg["reference"])
        rungs = [float(r) for r in cfg.get("rungs", BASELINE_RUNGS)]
        # current = channel's weighted-avg current price per unit (value / qty).
        total_qty = sum(h["holding"]["qty"] for h in agg["holdings"])
        current = round(agg["value"] / total_qty, 2) if total_qty > 0 else reference
        ladder = _ladder_for(channel, reference, current, rungs).model_dump()

    detail = {
        "channel": channel,
        "alloc": ChannelAlloc(
            channel=channel, value=round(agg["value"], 2), pct=pct, target=target,  # type: ignore[arg-type]
            drift=drift, driftAlert=drift_alert, pnl=_pnl(agg["cost"], agg["value"]),
        ).model_dump(),
        "holdings": agg["holdings"],
        "ladder": ladder,
    }
    return detail, warnings
