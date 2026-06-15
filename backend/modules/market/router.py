"""modules/market/router.py — Market REST endpoints + market-poll routine (S3).

Mounts at ``/market`` via the registry (``MODULE``). Endpoints return the locked
envelope ``{success, data, warning?}``. Business logic is in service.py; this is
HTTP shape + status codes only.

T3 lives here too: ``MODULE.routines()`` hands the scheduler the ``market-poll``
routine (every 5 min: fetch → persist → eval alerts → record fired alerts).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from core.base import BaseModule, Routine
from core.responses import ok
from store import db

from . import service
from .schema import AlertRuleInput, BackfillInput, IndicatorAlertRuleInput, WatchlistInput

logger = logging.getLogger("life-os.market.router")

router = APIRouter(tags=["market"])

MARKET_POLL_ID = service.MARKET_POLL_ID


@router.get("")
def get_market():
    """Live market view: quotes + alert triggers + macro + alert history."""
    data, warnings = service.get_market()
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/history/{symbol}")
def get_history(symbol: str, hours: int = 24):
    """price_history points for a TRACKED asset over the last ``hours`` (default 24).

    A tracked asset with no series yet → 200 + {points: []} (empty is a valid
    state — raw-data-first, like /projects:[] or /market triggers:[]). Only a
    symbol NOT in the tracked universe is a true 404.
    """
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if symbol not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {symbol!r} is not tracked")
    points = service.history(symbol, hours=hours)
    return ok(data={"points": [p.model_dump() for p in points]})


@router.get("/indicators/{symbol}")
def get_indicators(symbol: str, indicators: str = "summary", hours: int = 720,
                   full: bool = False):
    """Technical indicators over a TRACKED asset's close series (price_history).

    ``indicators`` = comma-separated ∈ {sma,ema,rsi,macd,bollinger,atr,summary}
    (default ``summary``). ``hours`` windows the series (default 720h ≈ 30d so the
    longer indicators have enough points); ``full=true`` attaches the aligned series
    (default = latest values only). Output is NEUTRAL technical data — no buy/sell
    advice. A short/empty series → per-indicator warning, never a 500. 404 only if
    the symbol is not in the tracked universe.
    """
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if symbol not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {symbol!r} is not tracked")
    names = indicators.split(",")
    data, warnings = service.compute_indicators(symbol, names, hours=hours, full=full)
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/ohlc/{symbol}")
def get_ohlc(symbol: str, hours: int = 168, interval: int = 60):
    """OHLC candles for a TRACKED asset, DERIVED from the close-tick series.

    ⚠️ The feed is close-only (CoinGecko /simple/price = one price per poll), so these
    are NOT exchange candles — each bar's O/H/L/C are the first/max/min/last observed
    close inside the ``interval`` (minutes) bucket. The `warning` says so; a bar's
    ``ticks`` count shows how many real observations it aggregates. For a true line
    chart use GET /market/history (raw close points). 404 only if untracked.
    """
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if symbol not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {symbol!r} is not tracked")
    bars, warnings = service.candles(symbol, hours=hours, interval_minutes=interval)
    return ok(data={"symbol": symbol, "interval": interval, "candles": bars},
              warning="; ".join(warnings) if warnings else None)


# --- multi-symbol analytics: correlation / comparison / relative strength ----
def _parse_symbols(symbols: str, *, min_n: int) -> list[str]:
    """Parse + validate the comma-separated ``symbols`` query. De-duped (order kept),
    uppercased. <``min_n`` → 422; >10 → 422 (bounded request, N² for correlation)."""
    parsed: list[str] = []
    seen: set[str] = set()
    for s in symbols.split(","):
        sym = s.strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            parsed.append(sym)
    if len(parsed) < min_n:
        raise HTTPException(status_code=422, detail=f"need ≥{min_n} distinct symbols (got {len(parsed)})")
    if len(parsed) > service.MAX_COMPARE_SYMBOLS:
        raise HTTPException(status_code=422,
                            detail=f"too many symbols ({len(parsed)}); max {service.MAX_COMPARE_SYMBOLS}")
    return parsed


@router.get("/correlation")
def get_correlation(symbols: str, hours: int = 720):
    """Pairwise Pearson correlation matrix for ≥2 comma-separated symbols (≤10) over
    the close series. Each cell ∈ [-1, 1] or None (no overlap / flat series — honest,
    not fabricated). Needs ≥2 symbols → 422 otherwise. NEUTRAL numbers, no advice."""
    syms = _parse_symbols(symbols, min_n=2)
    data, warnings = service.correlation(syms, hours=hours)
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/compare")
def get_compare(symbols: str, hours: int = 720):
    """Side-by-side comparison table for 1..10 comma-separated symbols: each
    {changePct, volatility, rsi, trend} over the window, for relative ranking.
    Short/absent series → honest None fields. NEUTRAL numbers, no advice."""
    syms = _parse_symbols(symbols, min_n=1)
    data, warnings = service.compare(syms, hours=hours)
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/relative-strength/{symbol}")
def get_relative_strength(symbol: str, vs: str = "BTC", hours: int = 720):
    """``symbol`` vs a ``vs`` benchmark (default BTC): the price-ratio trend + %
    change. ratioTrend 'up' = outperforming the benchmark (NEUTRAL observation, NOT a
    recommendation). Thin data → None fields, never fabricated."""
    data, warnings = service.relative_strength(symbol.strip().upper(), vs=vs.strip().upper(), hours=hours)
    return ok(data=data, warning="; ".join(warnings) if warnings else None)


@router.get("/price-at/{symbol}")
def get_price_at(symbol: str, ts: str):
    """Point-in-time price for ``symbol`` AS OF ``ts`` (ISO-8601 UTC) — the most recent
    OWNED price point at or before ``ts``. 404 if untracked. If we have no point that
    old → 200 with ``{point: null}`` + a warning (HONEST: not fabricated/interpolated)."""
    sym = symbol.strip().upper()
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if sym not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {sym!r} is not tracked")
    point = service.price_at(sym, ts)
    if point is None:
        return ok(data={"symbol": sym, "ts": ts, "point": None},
                  warning=f"no owned price point at or before {ts} for {sym}")
    return ok(data={"symbol": sym, "ts": ts, "point": point.model_dump()})


@router.post("/backfill")
def post_backfill(body: BackfillInput):
    """Backfill historical daily prices (CoinGecko market_chart) into price_history —
    fixes the shallow ~9-day window. IDEMPOTENT + DEDUP (a day already present is not
    re-inserted). ``symbols`` defaults to ALL cgId-backed tracked assets; ``days`` caps
    the lookback (1..3650). Returns ``{symbol: {inserted, skipped, error?}}``."""
    syms = None
    if body.symbols:
        syms = [s.strip().upper() for s in body.symbols if s and s.strip()]
        if not syms:
            raise HTTPException(status_code=422, detail="symbols, if given, must be non-empty")
    summary = service.backfill(syms, days=body.days)
    return ok(data={"backfill": summary, "days": body.days})


@router.get("/alerts")
def list_alerts():
    """All configured alert rules."""
    return ok(data=[r.model_dump() for r in service.list_rules()])


@router.post("/alerts")
def set_alert(body: AlertRuleInput):
    """Create an alert rule (id assigned server-side). Returns the created rule."""
    rule = service.add_rule(body.symbol, body.op, body.threshold, body.enabled)
    return ok(data=rule.model_dump())


@router.delete("/alerts/{rule_id}")
def delete_alert(rule_id: str):
    """Delete the alert rule by id. 404 if no such rule."""
    if not service.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"no alert rule {rule_id!r}")
    return ok(data={"deleted": rule_id})


# --- indicator-based alerts (TA conditions: RSI / price×SMA / MACD cross) ----
@router.get("/indicator-alerts")
def list_indicator_alerts():
    """All configured indicator alert rules + their LIVE evaluation (fired + detail).

    Returns ``{rules:[...], triggers:[...]}``: the persisted rules and a live
    ``IndicatorTrigger`` per enabled rule (fired now? + the current reading).
    """
    rules = service.list_indicator_rules()
    triggers = service.eval_indicator_alerts(rules)
    return ok(data={
        "rules": [r.model_dump() for r in rules],
        "triggers": [t.model_dump() for t in triggers],
    })


@router.post("/indicator-alerts")
def set_indicator_alert(body: IndicatorAlertRuleInput):
    """Create an indicator alert rule (id assigned server-side). UPSERT by
    (symbol, kind, period). 404 if the symbol is not tracked. Returns the rule."""
    tracked = {a.get("symbol") for a in service.tracked_assets()}
    if body.symbol not in tracked:
        raise HTTPException(status_code=404, detail=f"asset {body.symbol!r} is not tracked")
    rule = service.add_indicator_rule(body.symbol, body.kind, body.value, body.period, body.enabled)
    return ok(data=rule.model_dump())


@router.delete("/indicator-alerts/{rule_id}")
def delete_indicator_alert(rule_id: str):
    """Delete the indicator alert rule by id. 404 if no such rule."""
    if not service.delete_indicator_rule(rule_id):
        raise HTTPException(status_code=404, detail=f"no indicator alert rule {rule_id!r}")
    return ok(data={"deleted": rule_id})


# --- watchlist (user-curated symbols + one-shot quick view) ------------------
@router.get("/watchlist")
def get_watchlist():
    """The watchlist with a rich per-symbol view for a mini-chart screen:
    ``{items:[{symbol,name,price,changePct,source,sparkline[],rsi,trend,warning?}]}``.
    A symbol with no series yet still appears (price from the live quote, sparkline
    empty, rsi/trend pending) + a per-row warning — never a 500.
    """
    items, warnings = service.watchlist_data()
    return ok(data={"items": items}, warning="; ".join(warnings) if warnings else None)


@router.post("/watchlist")
def add_to_watchlist(body: WatchlistInput):
    """Add a symbol to the watchlist (idempotent). An untracked symbol is also
    registered as a best-effort crypto asset (so it gets polled + priced). Returns
    the updated symbol list."""
    symbols = service.add_watchlist(body.symbol)
    return ok(data={"symbols": symbols})


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(symbol: str):
    """Remove a symbol from the watchlist. 404 if it wasn't watchlisted."""
    if not service.delete_watchlist(symbol):
        raise HTTPException(status_code=404, detail=f"{symbol!r} not in watchlist")
    return ok(data={"deleted": symbol.strip().upper()})


# --------------------------------------------------------------------------- #
# T3 — the market-poll routine (rule-based, no AI; fetch+persist+alert detect)  #
# --------------------------------------------------------------------------- #
def _market_poll_work() -> tuple[str, str]:
    """The poll work — returns (status, detail). Raises are caught by the wrapper.

    Fail-open per asset (service.poll_once handles it). warn if any per-asset warning.
    """
    summary = service.poll_once()
    status = "warn" if summary.get("warnings") else "ok"
    detail = (f"polled: persisted={summary['persisted']} fired={summary['fired']}"
              + (f" warnings={len(summary['warnings'])}" if summary.get("warnings") else ""))
    return status, detail


def market_poll() -> None:
    """Scheduler entry point — runs the poll via the unified run-record wrapper, gated on
    the master automation switch (S12; no-ops when off). S10A: all routines share the
    wrapper instead of hand-rolling record_run + try/except."""
    from modules.automation import service as auto
    auto.run_scheduled(MARKET_POLL_ID, _market_poll_work)


_MARKET_POLL_ROUTINE = Routine(
    id=MARKET_POLL_ID,
    func=market_poll,
    trigger="interval",
    trigger_args={"minutes": 5},
    name="market-poll (fetch + persist + alert detect, 5min)",
    enabled=True,
)


MODULE = BaseModule(name="market", router=router, routines=[_MARKET_POLL_ROUTINE])
