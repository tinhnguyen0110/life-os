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

import json
import logging
from datetime import datetime, timedelta, timezone

import yaml

from modules.exchange import service as exchange_service
from modules.market import service as market_service
from store import db, md_store

from .schema import (
    AllocationShape,
    Change,
    ChannelAlloc,
    ChannelShape,
    ConcentrationItem,
    CryptoBasisInput,
    FinanceOverview,
    GoldenPathInput,
    Holding,
    HoldingInput,
    LadderState,
    PnL,
    PortfolioAnalytics,
    RebalanceAction,
    ReturnMetrics,
    RiskMetrics,
    SimulateResult,
)

logger = logging.getLogger("life-os.finance.service")

HOLDINGS_MD = "finance/holdings.md"
GOLDEN_PATH_MD = "finance/golden_path.md"
CRYPTO_BASIS_MD = "finance/crypto_basis.md"
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
# Crypto cost basis — snapshot-on-first-connect or user manual override         #
# --------------------------------------------------------------------------- #
def get_crypto_basis() -> tuple[float | None, str]:
    """(basis_usd, source). Returns (None, 'unset') if never set.

    source is one of: 'snapshot' (auto-captured from first OKX value) |
    'manual' (user PUT override). Manual is never overwritten by snapshot.
    """
    try:
        content = md_store.read(CRYPTO_BASIS_MD)
    except Exception as exc:
        logger.debug("crypto_basis.md not found (will snapshot on first OKX value): %s", exc)
        return None, "unset"
    data = _parse_front_matter(content)
    basis = data.get("basis")
    source = data.get("source", "unset")
    if basis is None:
        return None, str(source)
    try:
        return float(basis), str(source)
    except (TypeError, ValueError):
        return None, "unset"


def _ensure_crypto_basis(okx_total: float) -> float:
    """Return the stored cost basis; snapshot okx_total if not yet set.

    Rules (decided-and-logged):
    - basis is None → snapshot okx_total now, source="snapshot"
    - basis already set (snapshot or manual) → return as-is; NEVER override
    This means the very first GET /finance after OKX connect locks in cost.
    User can override at any time via PUT /finance/crypto-basis.
    """
    basis, _ = get_crypto_basis()
    if basis is None and okx_total > 0:
        snapped = round(okx_total, 2)
        _write_front_matter(CRYPTO_BASIS_MD, {
            "basis": snapped,
            "source": "snapshot",
            "setAt": _now_iso(),
        }, "snapshot crypto basis from OKX")
        logger.info("crypto basis snapshotted: %.2f USD", snapped)
        return snapped
    return basis if basis is not None else 0.0


def set_crypto_basis(body: CryptoBasisInput) -> dict:
    """User manual override. Writes source='manual' — snapshot never overwrites this."""
    payload = {
        "basis": round(body.basis, 2),
        "source": "manual",
        "setAt": _now_iso(),
    }
    _write_front_matter(CRYPTO_BASIS_MD, payload, "manual crypto basis override")
    logger.info("crypto basis manually set: %.2f USD", body.basis)
    return payload


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


def _series(days: int = 365) -> list[float]:
    """Portfolio total-value series (oldest→newest) from the daily equity snapshots.
    Empty until ≥1 snapshot exists (POST /finance/snapshot records them)."""
    since = (_now() - timedelta(days=max(1, days))).date().isoformat()
    try:
        rows = db.snapshots(since=since, limit=10000)
    except Exception as exc:  # snapshot store unavailable → degrade to empty, never crash
        logger.warning("portfolio snapshot read failed: %s", exc)
        return []
    return [float(r["total_value"]) for r in rows]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def take_snapshot() -> dict:
    """Record TODAY's portfolio snapshot (one row per UTC day — upsert). Captures the
    current totalValue + per-channel breakdown from get_overview(). An empty portfolio
    snapshots totalValue=0 (still recorded — a $0 day is a real data point). Returns
    the snapshot ``{day, ts, totalValue, byChannel}``."""
    overview, _ = get_overview()
    by_channel = {a.channel: a.value for a in overview.allocations}
    ts = _now_iso()
    day = db.record_snapshot(ts, overview.totalValue, json.dumps(by_channel))
    return {"day": day, "ts": ts, "totalValue": overview.totalValue, "byChannel": by_channel}


def value_history(days: int = 90) -> list[dict]:
    """Daily equity-curve points (oldest→newest) for the last ``days``:
    ``[{day, ts, totalValue, byChannel}]``. Empty list if no snapshots yet."""
    since = (_now() - timedelta(days=max(1, days))).date().isoformat()
    try:
        rows = db.snapshots(since=since, limit=10000)
    except Exception as exc:
        logger.warning("value_history read failed: %s", exc)
        return []
    out: list[dict] = []
    for r in rows:
        try:
            by_channel = json.loads(r["by_channel"]) if r["by_channel"] else {}
        except (json.JSONDecodeError, TypeError):
            by_channel = {}
        out.append({
            "day": r["day"], "ts": r["ts"],
            "totalValue": float(r["total_value"]), "byChannel": by_channel,
        })
    return out


def _okx_crypto_value() -> tuple[float | None, str | None]:
    """Return (okx_total_usd, warning_or_None) when OKX is configured and has value.

    Fail-open: exchange_service.get_overview() never raises. Returns (None, None) if
    unconfigured or totalUsdValue == 0 → caller keeps manual-price fallback unchanged.
    """
    try:
        snap, _ = exchange_service.get_overview()
        if snap.configured and snap.totalUsdValue > 0:
            return snap.totalUsdValue, None
    except Exception as exc:
        logger.warning("OKX overview unexpected error (fail-open): %s", exc)
    return None, None


def get_overview() -> tuple[FinanceOverview, list[str]]:
    holdings = list_holdings()
    targets, _ladder, gp_warnings = get_golden_path()
    by_channel, price_warnings = _aggregate(holdings)
    warnings = gp_warnings + price_warnings

    # OKX override: if configured, replace crypto channel value with live OKX totalUsdValue.
    # Cost basis = snapshot on first call (or user manual override via PUT /crypto-basis).
    # Holdings list from manual holdings (kept for individual position detail).
    okx_value, okx_warn = _okx_crypto_value()
    if okx_value is not None:
        crypto_cost = _ensure_crypto_basis(okx_value)
        crypto_holdings = by_channel.get("crypto", {}).get("holdings", [])
        by_channel["crypto"] = {
            "value": round(okx_value, 2),
            "cost": crypto_cost,
            "holdings": crypto_holdings,
        }
    if okx_warn:
        warnings.append(okx_warn)

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

    # OKX override for crypto channel: replace value with live OKX totalUsdValue.
    # Cost basis from snapshot/manual; total_value recomputed after override.
    if channel == "crypto":
        okx_value, okx_warn = _okx_crypto_value()
        if okx_value is not None:
            crypto_cost = _ensure_crypto_basis(okx_value)
            agg = dict(agg)  # don't mutate all_by_channel
            agg["value"] = round(okx_value, 2)
            agg["cost"] = crypto_cost
            all_by_channel = dict(all_by_channel)
            all_by_channel["crypto"] = agg
        if okx_warn:
            warnings.append(okx_warn)

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


# --------------------------------------------------------------------------- #
# Portfolio analytics — rebalance + risk + return (NEUTRAL numbers, NO advice)   #
# --------------------------------------------------------------------------- #
def _return_metrics(series: list[float]) -> ReturnMetrics:
    """Total return + volatility from a portfolio-value series. Honest: no series
    (the snapshot routine isn't built yet) → available=False, metrics None."""
    clean = [float(v) for v in series if isinstance(v, (int, float))]
    if len(clean) < 2:
        return ReturnMetrics(points=len(clean), totalReturnPct=None, volatilityPct=None, available=False)
    first, last = clean[0], clean[-1]
    total_return = round((last - first) / first * 100.0, 4) if first != 0 else None
    # period-over-period % returns → sample stddev = volatility.
    rets = [(clean[i] - clean[i - 1]) / clean[i - 1] * 100.0
            for i in range(1, len(clean)) if clean[i - 1] != 0]
    vol: float | None = None
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)  # sample variance
        vol = round(var ** 0.5, 4)
    return ReturnMetrics(points=len(clean), totalReturnPct=total_return,
                         volatilityPct=vol, available=True)


def get_analytics() -> tuple[PortfolioAnalytics, list[str]]:
    """Portfolio analytics over the live overview: actionable rebalance amounts,
    concentration / drift risk metrics, and (when a value series exists) return /
    volatility. All NEUTRAL numbers — NOT investment advice. Returns ``(analytics,
    warnings)``; an empty portfolio yields zeroed/None metrics, never a crash."""
    overview, warnings = get_overview()
    total = overview.totalValue

    # --- rebalance: per channel, the |USD| to move to hit the target weight -----
    rebalance: list[RebalanceAction] = []
    for a in overview.allocations:
        target_value = round(a.target / 100.0 * total, 2)
        delta = round(target_value - a.value, 2)  # +ve → under target → buy; -ve → sell
        if abs(delta) < 0.01:
            action, amount = "hold", 0.0
        elif delta > 0:
            action, amount = "buy", round(delta, 2)
        else:
            action, amount = "sell", round(-delta, 2)
        rebalance.append(RebalanceAction(
            channel=a.channel, currentValue=a.value, currentPct=a.pct,
            targetPct=a.target, targetValue=target_value, drift=a.drift,
            action=action, amount=amount,  # type: ignore[arg-type]
        ))

    # --- risk: per-holding concentration (HHI) + channel drift summary ----------
    by_channel, agg_warn = _aggregate(list_holdings())
    warnings += [w for w in agg_warn if w not in warnings]
    holding_items: list[ConcentrationItem] = []
    for ch, data in by_channel.items():
        if ch not in CHANNELS:
            continue
        for h in data["holdings"]:
            val = float(h["value"])
            holding_items.append(ConcentrationItem(
                symbol=h["holding"]["symbol"], channel=ch,
                value=val, pct=round(val / total * 100.0, 2) if total > 0 else 0.0,
            ))
    holding_items.sort(key=lambda c: c.value, reverse=True)

    top_pct = holding_items[0].pct if holding_items else None
    top_sym = holding_items[0].symbol if holding_items else None
    top3 = round(sum(c.pct for c in holding_items[:3]), 2) if holding_items else None
    # HHI = Σ(weight²) over holdings (weight = fraction of total); 1 = single asset.
    hhi: float | None = None
    if holding_items and total > 0:
        hhi = round(sum((c.value / total) ** 2 for c in holding_items), 4)
    total_abs_drift = round(sum(abs(a.drift) for a in overview.allocations), 2)

    risk = RiskMetrics(
        topHoldingPct=top_pct, topHoldingSymbol=top_sym, top3Pct=top3, hhi=hhi,
        holdingCount=len(holding_items), totalAbsDrift=total_abs_drift,
        rebalanceDistance=round(total_abs_drift / 2.0, 2),  # ½Σ|drift| = min turnover
    )

    returns = _return_metrics(overview.series)
    if not returns.available:
        warnings.append("no portfolio value series yet — return/volatility unavailable")

    analytics = PortfolioAnalytics(
        totalValue=total, rebalance=rebalance, risk=risk, returns=returns,
        asOf=_now_iso(),
    )
    return analytics, warnings


# --------------------------------------------------------------------------- #
# Scenario / what-if simulate — shape a HYPOTHETICAL allocation, NEUTRAL         #
# --------------------------------------------------------------------------- #
def _shape_allocation(weights_pct: dict[str, float], targets: dict[str, float],
                      current_pct: dict[str, float] | None) -> AllocationShape:
    """Build the risk-shape of a channel→pct allocation (sums to ~100). HHI = Σ(weight²)
    over CHANNELS; concentration = the largest channel; drift = pct - target; turnover =
    ½Σ|drift|. ``current_pct`` (if given) yields a per-channel delta vs the live portfolio.
    All NEUTRAL numbers. Channels with 0% are still listed (so the shape is complete)."""
    # union of channels present in the allocation, the targets, and current (complete view)
    chans = set(weights_pct) | set(targets) | set(current_pct or {})
    channels: list[ChannelShape] = []
    for ch in sorted(chans):
        if ch not in CHANNELS:
            continue
        pct = round(weights_pct.get(ch, 0.0), 4)
        target = round(float(targets.get(ch, 0.0)), 2)
        drift = round(pct - target, 4)
        delta: float | None = None
        if current_pct is not None:
            delta = round(pct - round(current_pct.get(ch, 0.0), 4), 4)
        channels.append(ChannelShape(
            channel=ch, pct=pct, targetPct=target, drift=drift,  # type: ignore[arg-type]
            deltaVsCurrentPct=delta,
        ))

    nonzero = [c for c in channels if c.pct > 0]
    hhi: float | None = None
    top_pct: float | None = None
    top_chan: str | None = None
    if nonzero:
        # HHI over channel weights as FRACTIONS (0..1); 1 = everything in one channel.
        hhi = round(sum((c.pct / 100.0) ** 2 for c in nonzero), 4)
        top = max(nonzero, key=lambda c: c.pct)
        top_pct, top_chan = round(top.pct, 2), top.channel
    total_abs_drift = round(sum(abs(c.drift) for c in channels), 2)
    return AllocationShape(
        hhi=hhi, concentrationTopPct=top_pct, concentrationTopChannel=top_chan,
        totalAbsDrift=total_abs_drift, rebalanceDistance=round(total_abs_drift / 2.0, 2),
        channels=channels,
    )


def _current_channel_pct() -> tuple[dict[str, float], float, list[str]]:
    """The live portfolio's channel→pct weights (and totalValue). Empty portfolio →
    all-zero pct + total 0 (honest, never a div-by-zero)."""
    overview, warnings = get_overview()
    total = overview.totalValue
    pct: dict[str, float] = {}
    for a in overview.allocations:
        pct[a.channel] = round(a.value / total * 100.0, 4) if total > 0 else 0.0
    return pct, total, warnings


def simulate(allocation: dict[str, float]) -> tuple[SimulateResult, list[str]]:
    """Shape a HYPOTHETICAL allocation and compare it to the current portfolio.

    ``allocation`` = {channel: weight}; weights are NORMALIZED to 100% (so the caller
    may pass %s or $s). Returns ``(SimulateResult, warnings)`` with the hypothetical's
    risk-shape (HHI / concentration / drift-vs-golden-path / turnover), the current
    portfolio's shape for comparison, the HHI delta, and per-channel delta-vs-current.

    PURE NUMBERS — explicitly NOT advice. Caller (router) enforces: non-empty, no
    negative weights, known channels. A zero-sum allocation → honest warning + None HHI
    (can't normalize), never a crash. Re-normalization is flagged (``normalized``)."""
    targets, _ladder, gp_warnings = get_golden_path()
    warnings: list[str] = list(gp_warnings)

    total_weight = sum(allocation.values())
    normalized = False
    if total_weight <= 0:
        warnings.append("allocation weights sum to 0 — cannot normalize; shape is empty")
        weights_pct: dict[str, float] = {ch: 0.0 for ch in allocation}
    else:
        weights_pct = {ch: w / total_weight * 100.0 for ch, w in allocation.items()}
        # flag if the RAW input didn't already sum to ~100 (we normalized it)
        if abs(total_weight - 100.0) > 0.01:
            normalized = True
            warnings.append(
                f"input weights summed to {round(total_weight, 2)} (not 100) — "
                f"normalized to 100% before analysis")

    current_pct, current_total, ov_warnings = _current_channel_pct()
    warnings += [w for w in ov_warnings if w not in warnings]
    have_current = current_total > 0

    hypo_shape = _shape_allocation(weights_pct, targets, current_pct if have_current else None)
    cur_shape = _shape_allocation(current_pct, targets, None) if have_current else \
        _shape_allocation({}, targets, None)
    if not have_current:
        warnings.append("no current holdings — delta-vs-current is unavailable (empty portfolio)")

    hhi_delta: float | None = None
    if hypo_shape.hhi is not None and cur_shape.hhi is not None:
        hhi_delta = round(hypo_shape.hhi - cur_shape.hhi, 4)

    result = SimulateResult(
        hypothetical=hypo_shape, current=cur_shape, hhiDelta=hhi_delta,
        normalized=normalized, asOf=_now_iso(),
    )
    return result, warnings
