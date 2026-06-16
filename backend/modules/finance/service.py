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
    PnlScope,
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
# NB4 — common USD-pegged stablecoins. Held in the crypto channel they are dry-powder-
# like (no crypto price exposure), so we split their value out for honest framing.
STABLECOINS = frozenset({
    "USDT", "USDC", "DAI", "TUSD", "BUSD", "USDP", "FDUSD", "GUSD", "USDD", "PYUSD",
})
STABLE_HEAVY_PCT = 50.0  # crypto channel >this% stablecoins → honest "dry-powder-like" warning
STABLE_UNDEPLOYED_PCT = 90.0  # D3a: crypto >this% stablecoin → drift warning reframed as undeployed-cash
# FINANCE-CORRECTNESS (Task #49, team-lead decided): a holding worth 0<usdValue<$1 is DUST —
# folded into ONE per-channel ·dust summary entry for DISPLAY (value preserved, still counts
# toward channel + total). A DISPLAY threshold, not a value cut. null-usdValue is NOT dust
# (unknown ≠ small — stays visible). The "·" prefix is collision-proof (no real ticker starts
# with it), so a real token can never be mistaken for the dust summary line.
DUST_USD_THRESHOLD = 1.00
DUST_SYMBOL = "·dust"

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
    holding = Holding(  # type: ignore[call-arg]  # FINANCE-CORRECTNESS #49 enrichment fields default (no pydantic mypy plugin in env → it can't see Field() defaults)
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


def _change_pct_of(symbol: str, price: float, *, priced: bool) -> float | None:
    """FINANCE-CORRECTNESS (#49): per-holding 24h %, via market.derive_change_pct — the
    SAME path the watchlist uses (one consistent feed). The feed is TTL-cached, so the
    quote re-fetch here is served from cache within the request (no double network hit).

    ``priced`` = the price came from a REAL market quote. When False (cost-fallback price,
    or an OKX value-only coin) there is no live quote to fall back on AND price is an
    estimate, so changePct is honest-NULL (a series may still exist from our own history,
    but without a real current quote the % would mix an estimated price with a real old
    price — misleading; keep it null). When True, derive from our series with the quote's
    own 24h change as the feed fallback."""
    if not priced:
        return None
    quote = market_service.get_quote(symbol)
    feed_fallback = quote.changePct if quote is not None else None
    return market_service.derive_change_pct(symbol, price, feed_fallback)


def _pnl(cost: float, current: float) -> PnL:
    abs_ = round(current - cost, 2)
    pct = round(abs_ / cost * 100.0, 2) if cost > 0 else None
    return PnL(cost=round(cost, 2), current=round(current, 2), abs=abs_, pct=pct)


def _pnl_framed(cost: float, current: float, basis_unknown: bool) -> PnL:
    """NB4 + D3a: channel-level pnl with honest framing. When basisUnknown (the channel's
    holdings majority lack a real avgCost — e.g. OKX value-only, cost≈0), NULL BOTH pnl.abs
    AND pnl.pct so the misleading gain (a value-only inflow reads as +$X / +Y%) doesn't
    show; KEEP cost/current (the raw $ figures the FE/agent can still display + reason on).
    A channel with real basis → unchanged pnl (the legit manual P&L is NOT hidden)."""
    pnl = _pnl(cost, current)
    if basis_unknown:
        return pnl.model_copy(update={"abs": None, "pct": None})
    return pnl


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
        # OKX-FINANCE: avgCost may be None (value-only holding) — use 0.0 as the
        # price fail-open fallback (no fabricated cost) and compute cost=0 → the pnl
        # is honest-null (PnL.pct None when cost==0), never a fake +∞% gain.
        avg_cost = h.avgCost if h.avgCost is not None else 0.0
        price, source, warn = _price_of(h.symbol, avg_cost)
        if warn:
            warnings.append(warn)
        value = round(price * h.qty, 2)
        cost = round(avg_cost * h.qty, 2)
        # FINANCE-CORRECTNESS (#49): a real quote → changePct from the market feed; a
        # cost-fallback price (source="cost-fallback") has no live quote → changePct null.
        priced = source != "cost-fallback"
        change_pct = _change_pct_of(h.symbol, price, priced=priced)
        ch = by_channel.setdefault(h.channel, {"value": 0.0, "cost": 0.0, "holdings": []})
        ch["value"] = round(ch["value"] + value, 2)
        ch["cost"] = round(ch["cost"] + cost, 2)
        ch["holdings"].append({
            "holding": h.model_dump(), "price": price, "source": source,
            "value": value, "pnl": _pnl(cost, value).model_dump(),
            "changePct": change_pct,
        })
    return by_channel, warnings


# --------------------------------------------------------------------------- #
# NB4 — honest framing of value-only / stablecoin-heavy channel data. Pure       #
# derivations over a channel's holdings entry-list ({holding, value, ...}).      #
# READ-PATH only — no store change, no channel re-architecture.                  #
# --------------------------------------------------------------------------- #
def _basis_unknown(holdings_entries: list[dict]) -> bool:
    """True when the MAJORITY (by value) of a channel's holdings lack a cost basis
    (avgCost None or 0) — so the channel pnl is computed against cost≈0 and a value-only
    inflow reads as a fake huge gain. Empty channel → False (no holdings, no false alarm).
    Decided by VALUE-weight (not count) so one large value-only coin dominates the verdict
    the way it dominates the pnl."""
    total_value = sum(float(e.get("value") or 0.0) for e in holdings_entries)
    if total_value <= 0:
        # No value to weigh → fall back to count (any present holding lacking basis).
        present = [e for e in holdings_entries]
        if not present:
            return False
        unknown = sum(1 for e in present if not (e.get("holding") or {}).get("avgCost"))
        return unknown > len(present) / 2
    unknown_value = sum(
        float(e.get("value") or 0.0)
        for e in holdings_entries
        if not (e.get("holding") or {}).get("avgCost")  # None or 0 → unknown basis
    )
    return unknown_value > total_value / 2


def _stable_split(holdings_entries: list[dict], channel_value: float) -> tuple[float | None, float | None]:
    """Crypto channel ONLY: (stableValue, stablePct) — USD held in stablecoins, which is
    dry-powder-like, not crypto exposure. Returns (None, None) — caller decides to apply
    only for the crypto channel. stablePct None when channel_value ≤ 0 (no div-0)."""
    stable_value = round(sum(
        float(e.get("value") or 0.0)
        for e in holdings_entries
        if str((e.get("holding") or {}).get("symbol", "")).upper() in STABLECOINS
    ), 2)
    stable_pct = round(stable_value / channel_value * 100.0, 2) if channel_value > 0 else None
    return stable_value, stable_pct


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


def _okx_crypto_holdings() -> list[dict] | None:
    """OKX-FINANCE (G2) — OKX per-coin balances as VALUE-ONLY crypto holdings.

    Returns the channel-``holdings`` entry list (same shape ``_aggregate`` builds:
    ``{holding, price, source, value, pnl}``) for the crypto channel, where each entry
    is value-only: ``holding.avgCost=None``, ``pnl=None`` (honest-null per-coin P&L —
    OKX exposes no per-coin cost basis; fabricating one would lie). ``value`` = the
    coin's usdValue; ``price`` = usdValue/qty (derived display price, NOT a cost).

    Returns None (NOT []) when OKX is unconfigured / down / has no balances → the
    caller keeps the MANUAL crypto holdings (fail-soft; finance never breaks on OKX).
    A coin with NO usdValue is still SHOWN (qty visible) with value=0 + honest-null pnl
    (architect: "show qty, value honest-null — don't crash, don't assume") — NOT
    skipped, NOT fabricated. A zero-total position IS skipped (not held). USDT/
    stablecoins included (real crypto-channel value). asOf = the snapshot time.
    """
    try:
        snap, _ = exchange_service.get_overview()
    except Exception as exc:  # noqa: BLE001 — fail-soft: OKX down → manual holdings
        logger.warning("OKX balances read failed (fail-soft to manual): %s", exc)
        return None
    if not snap.configured or not snap.balances:
        return None

    now = _now_iso()
    entries: list[dict] = []
    for b in snap.balances:
        if b.total <= 0:
            continue  # not actually held → skip
        valued = b.usdValue is not None
        value = round(float(b.usdValue), 2) if b.usdValue is not None else 0.0
        # display price = value/qty when valued; None when unvalued (don't assume a price).
        price = round(value / b.total, 6) if (valued and b.total) else None
        # FINANCE-ASSISTANT P1 (#52): OKX exposes a per-coin cost-basis (accAvgPx). When
        # present, wire it into Holding.avgCost → the SHIPPED _pnl() lights up automatically
        # (per-coin P&L is no longer null). None for a coin OKX has no basis for (stablecoin /
        # pre-OKX-history) → pnl stays honest-null. accAvgPx is the SINGLE source of truth for
        # pnl; b.spotUpl/spotUplRatio are OKX's OWN P&L, carried for the cross-check only.
        avg_cost = b.accAvgPx if b.accAvgPx else None  # '' / 0 / None → None (honest-null)
        holding = Holding(channel="crypto", symbol=b.symbol, qty=b.total,  # type: ignore[call-arg]  # see #49 note above
                          avgCost=avg_cost, source="okx", asOf=now)
        # FINANCE-CORRECTNESS (#49): a valued OKX coin gets a real 24h changePct from our
        # series (the symbol is tradeable); an unvalued coin (price None) → null changePct.
        change_pct = (_change_pct_of(b.symbol, price, priced=True)
                      if (valued and price is not None) else None)
        # Per-coin P&L: real when we have BOTH a basis (avg_cost) AND a value; else honest-null.
        # cost = accAvgPx × qty; _pnl computes abs/pct (pct null when cost==0, no ÷0).
        pnl = (_pnl(round(avg_cost * b.total, 2), value)
               if (avg_cost is not None and valued) else None)
        entries.append({
            "holding": holding.model_dump(), "price": price, "source": "okx",
            "value": value,
            "pnl": pnl.model_dump() if pnl is not None else None,
            "changePct": change_pct,
            # FINANCE-ASSISTANT P1 (#52): OKX's OWN P&L — carried for the T4 sanity cross-check
            # (our recomputed pnl.pct ≈ spotUplRatio×100), NOT displayed as a 2nd pnl.
            "okxSpotUplRatio": b.spotUplRatio,
        })
    if not entries:
        return None
    entries.sort(key=lambda e: e["value"], reverse=True)  # most-valuable first
    return entries


def _holding_from_entry(entry: dict) -> Holding:
    """FINANCE-CORRECTNESS (#49): build an ENRICHED flat Holding from an aggregate entry
    (the `{holding, price, value, changePct, source, ...}` shape `_aggregate`/
    `_okx_crypto_holdings` produce). Surfaces the already-computed price/usdValue/changePct
    onto the Holding — NEVER re-prices (the consistency invariant: this usdValue is the same
    number that summed to the channel value).

    UNPRICEABLE → honest-NULL price+usdValue (missing price ≠ zero worth, so it stays VISIBLE,
    never folded as dust). Two unpriceable shapes:
      - OKX value-only coin with no usdValue: price None, value 0.
      - manual cost-fallback (NO market quote) with NO real basis (avgCost 0 → price 0.0):
        a 0.0 "price" here is the ABSENCE of a price coinciding with a zero basis, NOT a real
        ~$0 valuation — treat it as unpriceable so it doesn't masquerade as priced sub-cent
        dust. A cost-fallback WITH a real avgCost keeps usdValue=avgCost×qty (honest estimate).
    A REAL quote whose value rounds to ~$0.00 is NOT unpriceable — it IS ~$0 worth (priced
    sub-cent → dust-eligible)."""
    base = dict(entry.get("holding") or {})
    price = entry.get("price")
    value = entry.get("value")
    source = entry.get("source")
    # Unpriceable: no usable price at all. (a) OKX no-value (price None); (b) cost-fallback
    # whose price is 0 (no quote AND no basis) — a 0 there is "no price", not a $0 valuation.
    unpriceable = (price is None) or (source == "cost-fallback" and not price)
    if unpriceable:
        price = None
        usd_value = None
    else:
        usd_value = value
    base.update({
        "price": price,
        "usdValue": usd_value,
        "changePct": entry.get("changePct"),
        "isDust": False,
        "count": None,
        # FINANCE-ASSISTANT P1 T5 (#52): surface the per-holding pnl _aggregate already
        # computed (entry["pnl"] = _pnl(cost, value).model_dump(), or None for OKX value-only).
        # NOT recomputed — the exact same number (consistency). A basis-less holding's pnl has
        # abs/pct null (cost 0); a real-basis holding (avgCost from accAvgPx) → real pnl. This
        # is the per-holding granularity where USDT-null doesn't mask PEPE-real (the channel-
        # level basisUnknown nulls the aggregate; per-holding keeps each coin honest).
        "pnl": entry.get("pnl"),
    })
    return Holding(**base)


def _is_dust(h: Holding) -> bool:
    """FINANCE-CORRECTNESS (#49) dust predicate (team-lead RULING, decide-and-log): a holding
    is dust when it is PRICED (price not None) AND has a known usdValue (not None) BELOW $1 —
    INCLUDING usdValue that rounds to 0.0 (a sub-cent coin OKX still prices, e.g. ETH/LINK/DOGE
    1e-7 qty — the consumer-agent's literal complaint). A null-price OR null-usdValue coin is
    UNKNOWN, not small → NOT dust (stays visible — lock d). `< threshold` is STRICT: usdValue
    exactly $1.00 is NOT dust (≥ threshold stays visible)."""
    return (h.price is not None and h.usdValue is not None
            and h.usdValue < DUST_USD_THRESHOLD)


def _fold_dust(holdings: list[Holding]) -> list[Holding]:
    """FINANCE-CORRECTNESS (#49): per channel, collapse the priced-sub-$1 holdings (see
    _is_dust) into ONE ·dust summary entry (isDust, count, usdValue=sum) so dust doesn't
    clutter the list. Keeps DISPLAY order otherwise. NOT folded: usdValue ≥ $1 (individual)
    and any null-price/null-usdValue holding (unknown ≠ small — stays visible). 0 dust in a
    channel → no dust entry. The fold is DISPLAY-only — totalValue/channel value were already
    computed from the full set."""
    by_channel: dict[str, list[Holding]] = {}
    for h in holdings:
        by_channel.setdefault(h.channel, []).append(h)
    out: list[Holding] = []
    for channel, hs in by_channel.items():
        kept: list[Holding] = []
        dust: list[Holding] = []
        for h in hs:
            if _is_dust(h):
                dust.append(h)
            else:
                kept.append(h)  # ≥$1, or null-price/null-usdValue (unknown) → stays individual
        out.extend(kept)
        if dust:
            dust_value = round(sum(float(h.usdValue or 0.0) for h in dust), 2)
            out.append(Holding(
                channel=channel,  # type: ignore[arg-type]  # came off a valid Holding
                symbol=DUST_SYMBOL, qty=0, avgCost=None, source="dust-fold", asOf=None,
                price=None, usdValue=dust_value, changePct=None,
                isDust=True, count=len(dust), pnl=None,  # #52 T5: a sum-of-many has no single pnl
            ))
    return out


def _enriched_holdings(by_channel: dict) -> list[Holding]:
    """FINANCE-CORRECTNESS (#49): the flat FinanceOverview.holdings, enriched + dust-folded.
    Built from the per-channel aggregate entries (which carry the already-computed price/
    value/changePct) — so the per-holding usdValue is consistent with the channel value, by
    construction. Unknown stored channels (not in CHANNELS) are skipped (same resilience as
    the allocations loop)."""
    flat: list[Holding] = []
    for ch in sorted(by_channel):
        if ch not in CHANNELS:
            continue  # stale/unknown stored channel — skipped (mirrors allocations loop)
        for entry in by_channel[ch].get("holdings", []):
            flat.append(_holding_from_entry(entry))
    return _fold_dust(flat)


def _finance_warnings(holdings: list[Holding]) -> tuple[dict[str, float], dict, dict, list[str]]:
    """FINANCE-MCP-SHAPE (#50): the SHARED golden-path + aggregate prefix that get_overview
    and get_channel both build identically. Returns ``(targets, ladder_cfg, by_channel,
    warnings)`` where ``warnings = gp_warnings + price_warnings`` (the golden-path baseline/
    absence warning followed by the per-holding no-price cost-fallback warnings) — BYTE-
    IDENTICAL to the inline ``gp_warnings + price_warnings`` it replaces. Pure dedup of the
    two identical call-sites; it does NOT include the overview-specific okx/stable/drift/
    unknown-channel warnings (those are appended by the caller, unchanged). simulate (gp-only,
    no price) and get_analytics (inherits overview's warnings) are DIVERGENT and keep their
    own assembly — not routed through here."""
    targets, ladder_cfg, gp_warnings = get_golden_path()
    by_channel, price_warnings = _aggregate(holdings)
    return targets, ladder_cfg, by_channel, gp_warnings + price_warnings


def _basis_known_pnl(by_channel: dict, total_value: float) -> tuple[PnL, PnlScope]:
    """FINANCE-AUDIT2 (#66): pnlTotal aggregated from the per-coin entries WITH a real cost basis
    (entry["pnl"] non-null AND abs non-null) — NOT the channel snapshot cost (which ≈ value on
    first connect → a fake ~$0 gain that hides the real per-coin losses). known_cost = Σ pnl.cost,
    known_value = Σ pnl.current over basis-known coins → _pnl(known_cost, known_value). A no-basis
    holding (stablecoin/dust/OKX value-only) is EXCLUDED (you can't claim gain/loss with no cost
    basis — honest-null at the total). NO basis-known coin → pnlTotal honest-null (cost/current 0).
    pnlScope labels the coverage so −X% on the basis-known slice isn't misread as whole-portfolio."""
    known_cost = 0.0
    known_value = 0.0
    n_known = 0
    for ch in by_channel.values():
        for e in ch.get("holdings", []):
            pnl = e.get("pnl")
            if pnl is None:
                continue
            # require a real basis: abs computed (cost>0 → not basisUnknown). A 0-cost/None-abs
            # entry (OKX value-only / stablecoin) is excluded — no basis to claim P&L against.
            if pnl.get("abs") is None or pnl.get("cost") in (None, 0, 0.0):
                continue
            known_cost += float(pnl["cost"])
            known_value += float(pnl["current"])
            n_known += 1
    known_cost = round(known_cost, 2)
    known_value = round(known_value, 2)
    coverage_pct = (round(known_value / total_value * 100.0, 1)
                    if total_value and n_known else None)
    if n_known == 0:
        # honest-null: NO basis-known holding → P&L is UNKNOWN, NOT a $0 gain. abs/pct null,
        # cost/current 0 (the raw $ are genuinely 0 — nothing has a basis to aggregate).
        note = ("no holding has a cost basis yet — total P&L is unknown (the OKX positions are "
                "value-only / stablecoin; set a cost basis to compute P&L)")
        return (PnL(cost=0.0, current=0.0, abs=None, pct=None),
                PnlScope(basis="known-cost-only", coveragePct=None, note=note))

    cov = coverage_pct if coverage_pct is not None else 0.0
    # format small coverage precisely (~0.5%, not a misleading ~0%); 1 decimal under 10%.
    cov_str = f"{cov:.1f}" if cov < 10 else f"{cov:.0f}"
    excl_str = f"{100 - cov:.1f}" if (100 - cov) < 10 else f"{100 - cov:.0f}"
    note = (f"P&L on the ~{cov_str}% of the book ({n_known} holding(s)) that have a cost basis; "
            f"the ~{excl_str}% no-basis stablecoin/value-only is excluded (no cost basis)")
    return _pnl(known_cost, known_value), PnlScope(basis="known-cost-only", coveragePct=coverage_pct, note=note)


def get_overview() -> tuple[FinanceOverview, list[str]]:
    holdings = list_holdings()
    targets, _ladder, by_channel, warnings = _finance_warnings(holdings)

    # OKX override: if configured, replace crypto channel value with live OKX totalUsdValue.
    # Cost basis = snapshot on first call (or user manual override via PUT /crypto-basis).
    # Holdings list from manual holdings (kept for individual position detail).
    okx_value, okx_warn = _okx_crypto_value()
    if okx_value is not None:
        crypto_cost = _ensure_crypto_basis(okx_value)
        # OKX-FINANCE (G2): replace the (manual, usually empty) crypto holdings with the
        # OKX per-coin balances — value-only, honest-null per-coin P&L. NO double-count:
        # OKX is the source of truth for the crypto channel; manual etf/vn/dry holdings
        # (in other channels of by_channel) are untouched. If OKX per-coin read fails-soft
        # (None), keep the manual crypto holdings (the prior behavior).
        okx_holdings = _okx_crypto_holdings()
        crypto_holdings = (okx_holdings if okx_holdings is not None
                           else by_channel.get("crypto", {}).get("holdings", []))
        by_channel["crypto"] = {
            "value": round(okx_value, 2),       # aggregate value (OKX total) — unchanged
            "cost": crypto_cost,                 # aggregate cost (snapshot) — unchanged
            "holdings": crypto_holdings,         # NOW per-coin (value-only) from OKX
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
        # NB4 — honest framing (derived from this channel's holdings entries). Compute the
        # stable split BEFORE the drift warning so D3a can reframe a stablecoin-dominated
        # crypto channel's drift as undeployed-cash (the raw drift number is unchanged on
        # the ChannelAlloc — only the WARNING wording is reframed).
        ch_entries = by_channel.get(ch, {}).get("holdings", [])
        basis_unknown = _basis_unknown(ch_entries)
        stable_value, stable_pct = (None, None)
        crypto_undeployed = False
        if ch == "crypto":
            stable_value, stable_pct = _stable_split(ch_entries, value)
            crypto_undeployed = stable_pct is not None and stable_pct > STABLE_UNDEPLOYED_PCT
            if stable_pct is not None and stable_pct > STABLE_HEAVY_PCT:
                warnings.append(
                    f"crypto channel is {stable_pct:.0f}% stablecoins "
                    f"(${stable_value:,.0f}) — dry-powder-like, not crypto exposure")
        if drift_alert:
            if crypto_undeployed:
                # D3a: when crypto is >90% stablecoin, a "crypto drift" warning is
                # misleading — the gap is UNDEPLOYED CASH sitting in the crypto channel,
                # not over/under crypto EXPOSURE. Reframe (raw drift number unchanged).
                warnings.append(
                    f"crypto: {drift:+.1f}% vs target reflects ~{stable_pct:.0f}% UNDEPLOYED "
                    f"stablecoin (cash-equivalent), not crypto exposure (target {target}%, "
                    f"actual {pct}%)")
            else:
                warnings.append(
                    f"{ch}: allocation drift {drift:+.1f}% (target {target}%, actual {pct}%)")
        allocations.append(ChannelAlloc(
            channel=ch, value=value, pct=pct, target=target, drift=drift,  # type: ignore[arg-type]
            driftAlert=drift_alert, pnl=_pnl_framed(cost, value, basis_unknown),
            basisUnknown=basis_unknown, stableValue=stable_value, stablePct=stable_pct,
        ))

    # FINANCE-AUDIT2 (#66): pnlTotal from the basis-known per-coin sum + its scope label.
    pnl_total, pnl_scope = _basis_known_pnl(by_channel, total_value)

    overview = FinanceOverview(
        totalValue=total_value,
        change=Change(abs=0.0, pct=None) if total_value else None,
        # FINANCE-CORRECTNESS (#49): the flat holdings list is now ENRICHED (per-holding
        # price/usdValue/changePct surfaced from the aggregate entries) + dust-folded. Built
        # from by_channel (which already has the OKX override applied), so usdValue is
        # consistent with each ChannelAlloc.value by construction.
        holdings=_enriched_holdings(by_channel),
        allocations=allocations,
        # FINANCE-AUDIT2 (#66): pnlTotal from the BASIS-KNOWN per-coin sum (not the snapshot cost,
        # which lied +$7 while the real per-coin loss was −$617) + a scope label so the basis-
        # known % isn't misread as whole-portfolio. The crypto snapshot `cost` (total_cost) stays
        # for the channel drift framing — only pnlTotal stops using it.
        pnlTotal=pnl_total,
        pnlScope=pnl_scope,
        dryPowder=dry_powder,
        series=_series(),
    )
    return overview, warnings


def get_channel(channel: str) -> tuple[dict | None, list[str]]:
    """S6 detail: a channel's holdings + ChannelAlloc + LadderState. None if unknown."""
    holdings = list_holdings()
    # FINANCE-MCP-SHAPE (#50): shared golden-path + aggregate prefix (byte-identical warnings).
    targets, ladder_cfg, all_by_channel, warnings = _finance_warnings(holdings)
    ch_holdings = [h for h in holdings if h.channel == channel]
    if not ch_holdings and channel not in targets:
        return None, []

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
            # OKX-FINANCE (G2): per-coin holdings = OKX value-only (honest-null P&L),
            # replacing manual crypto. Fail-soft (None → keep manual). Same as overview.
            okx_holdings = _okx_crypto_holdings()
            if okx_holdings is not None:
                agg["holdings"] = okx_holdings
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

    # NB4 — honest framing for this channel (same derivations as the overview).
    ch_value = round(agg["value"], 2)
    basis_unknown = _basis_unknown(agg["holdings"])
    stable_value, stable_pct = (None, None)
    if channel == "crypto":
        stable_value, stable_pct = _stable_split(agg["holdings"], ch_value)
        if stable_pct is not None and stable_pct > STABLE_HEAVY_PCT:
            warnings.append(
                f"crypto channel is {stable_pct:.0f}% stablecoins "
                f"(${stable_value:,.0f}) — dry-powder-like, not crypto exposure")

    detail = {
        "channel": channel,
        "alloc": ChannelAlloc(
            channel=channel, value=ch_value, pct=pct, target=target,  # type: ignore[arg-type]
            drift=drift, driftAlert=drift_alert,
            pnl=_pnl_framed(agg["cost"], agg["value"], basis_unknown),
            basisUnknown=basis_unknown, stableValue=stable_value, stablePct=stable_pct,
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
