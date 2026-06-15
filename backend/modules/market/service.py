"""modules/market/service.py — market orchestration (Sprint 3, SPEC §S8).

Composes the live market view: quotes (reader) → changePct derived server-side
from price_history → alert triggers (eval rules) → macro stubs → alert history
(run_log). Alert rules persist in md_store (`market/alerts.md` front-matter list).

Decide-and-log rules (architect Logic block, verbatim):
  - changePct: derive from price_history (point ≥24h ago vs latest); if our series
    is too short, fall back to the feed's usd_24h_change. NEVER trust the feed blindly.
  - Alert state: hit (above:price≥thr / below:price≤thr) · near (within 5% of thr)
    · far. distance = (threshold - price) / price.
  - Macro: stub mock block this build.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone

import yaml

from core.config import settings
from store import db, md_store

from . import reader
from .schema import (
    AlertEvent,
    AlertRule,
    AlertState,
    AlertTrigger,
    AssetQuote,
    IndicatorAlertRule,
    IndicatorTrigger,
    MacroSignal,
    PricePoint,
    WatchlistItem,
)

logger = logging.getLogger("life-os.market.service")

ALERTS_MD = "market/alerts.md"
INDICATOR_ALERTS_MD = "market/indicator_alerts.md"  # separate file from price rules
WATCHLIST_MD = "market/watchlist.md"                # user-curated symbols
SPARKLINE_POINTS = 32                               # mini-chart sample size
NEAR_PCT = 5.0                  # within 5% (|distancePct|) of threshold → "near"
CHANGE_LOOKBACK_HOURS = 24
MARKET_POLL_ID = "market-poll"  # run_log routine_id alert events are recorded under


def _now() -> datetime:
    return datetime.now(timezone.utc)


def tracked_assets() -> list[dict]:
    """The flat tracked-asset list from config (no asset-mgmt API)."""
    return list(settings.market_assets or [])


def get_quote(symbol: str) -> AssetQuote | None:
    """Single-asset quote for cross-module callers (e.g. finance pricing).

    Reuses the reader (fail-open: CoinGecko down → last-known/mock). Looks the
    symbol up in the tracked universe for its assetClass/cgId; if it's not tracked,
    treats it as a crypto-by-symbol best-effort (cgId=symbol lowercased) so an
    ad-hoc holding can still be priced. Returns None only if the reader yields
    nothing. Does NOT re-fetch beyond the reader's own one batched call.
    """
    asset = next((a for a in tracked_assets() if a.get("symbol") == symbol), None)
    if asset is None:
        # Best-effort: assume crypto, cgId = lowercased symbol. Reader fail-opens
        # to mock/last-known if that id is unknown to CoinGecko.
        asset = {"symbol": symbol, "name": symbol, "assetClass": "crypto", "cgId": symbol.lower()}
    quotes, _ = reader.read_quotes([asset])
    return quotes[0] if quotes else None


# --------------------------------------------------------------------------- #
# changePct — derived server-side from price_history                            #
# --------------------------------------------------------------------------- #
def derive_change_pct(symbol: str, latest_price: float, feed_fallback: float | None) -> float | None:
    """% change vs the price ≥CHANGE_LOOKBACK_HOURS ago from our own series.

    Falls back to the feed's 24h change when our series lacks a point that old.
    Returns None only when neither source is available. Never divides by zero.
    """
    cutoff = (_now() - timedelta(hours=CHANGE_LOOKBACK_HOURS)).isoformat()
    row = db.price_at_or_before(symbol, cutoff)
    if row is not None:
        old = float(row["price"])
        if old > 0:
            return round((latest_price - old) / old * 100.0, 2)
    # Series too short → fall back to the feed's own 24h change (if present).
    if isinstance(feed_fallback, (int, float)):
        return round(float(feed_fallback), 2)
    return None


def _apply_change_pct(quotes: list[AssetQuote]) -> list[AssetQuote]:
    """Fill changePct on each quote from price_history (feed fallback)."""
    out: list[AssetQuote] = []
    for q in quotes:
        feed_fallback = getattr(q, "_feed_change_pct", None)
        pct = derive_change_pct(q.symbol, q.price, feed_fallback)
        out.append(q.model_copy(update={"changePct": pct}))
    return out


# --------------------------------------------------------------------------- #
# Alert rules — persistence (md_store) + evaluation                             #
# --------------------------------------------------------------------------- #
def _parse_rules(content: str | None) -> list[AlertRule]:
    """Parse the alerts.md front-matter `rules:` list into AlertRule objects."""
    if not content:
        return []
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return []
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        logger.warning("malformed alerts.md, ignoring: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    rules: list[AlertRule] = []
    for item in data.get("rules", []) or []:
        try:
            rules.append(AlertRule(**item))
        except Exception as exc:  # one bad rule never breaks the rest
            logger.warning("skipping invalid alert rule %r: %s", item, exc)
    return rules


def list_rules() -> list[AlertRule]:
    """All persisted alert rules ([] if none)."""
    try:
        content = md_store.read(ALERTS_MD)
    except Exception as exc:
        logger.warning("alerts.md read failed: %s", exc)
        return []
    return _parse_rules(content)


def _write_rules(rules: list[AlertRule]) -> None:
    """Persist the full rule list to alerts.md as one md_store commit."""
    payload = {"rules": [r.model_dump() for r in rules]}
    body = "---\n" + yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).strip() + "\n---\n"
    md_store.write_file(ALERTS_MD, body, "update market alert rules")


def _new_rule_id(symbol: str, existing: list[AlertRule]) -> str:
    """Server-assigned id = slug(symbol)+counter, unique within the rule set."""
    base = re.sub(r"[^a-z0-9]+", "-", symbol.lower()).strip("-") or "rule"
    taken = {r.id for r in existing}
    n = 1
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def add_rule(symbol: str, op: str, threshold: float, enabled: bool = True) -> AlertRule:
    """UPSERT an alert rule by (symbol, op): one threshold per symbol+op.

    If a rule with the same (symbol, op) exists, REPLACE it (keeping its id) —
    re-setting a "BTC above" threshold updates the existing rule rather than
    creating a duplicate (correct UX, and keeps delete-by-id unambiguous).
    Otherwise create a new rule with a server-assigned id. Persists + returns it.
    """
    rules = list_rules()
    existing = next((r for r in rules if r.symbol == symbol and r.op == op), None)
    rule = AlertRule(
        id=existing.id if existing else _new_rule_id(symbol, rules),
        symbol=symbol, op=op,  # type: ignore[arg-type]
        threshold=threshold, enabled=enabled,
    )
    others = [r for r in rules if not (r.symbol == symbol and r.op == op)]
    others.append(rule)
    _write_rules(others)
    return rule


def delete_rule(rule_id: str) -> bool:
    """Delete the rule with the given id. Returns True if one was removed."""
    rules = list_rules()
    kept = [r for r in rules if r.id != rule_id]
    removed = len(kept) != len(rules)
    if removed:
        _write_rules(kept)
    return removed


def eval_alerts(quotes: list[AssetQuote], rules: list[AlertRule]) -> list[AlertTrigger]:
    """Evaluate each rule against the matching quote → triggers with hit/near/far state.

    above: price≥threshold = hit; below: price≤threshold = hit. distance =
    (threshold-price)/price. |distance|≤5% (and not hit) → near, else far.
    Rules whose symbol has no quote are skipped.
    """
    by_symbol = {q.symbol: q for q in quotes}
    triggers: list[AlertTrigger] = []
    for rule in rules:
        q = by_symbol.get(rule.symbol)
        if q is None:
            continue
        if not rule.enabled:
            continue
        price = q.price
        distance_pct = (rule.threshold - price) / price * 100.0 if price > 0 else 0.0
        state: AlertState
        if (rule.op == "above" and price >= rule.threshold) or (
            rule.op == "below" and price <= rule.threshold
        ):
            state = "hit"
        elif abs(distance_pct) <= NEAR_PCT:
            state = "near"
        else:
            state = "far"
        triggers.append(
            AlertTrigger(
                symbol=rule.symbol, op=rule.op, threshold=rule.threshold,
                price=price, state=state, distancePct=round(distance_pct, 2),
            )
        )
    return triggers


# --------------------------------------------------------------------------- #
# Indicator alerts — TA-condition rules (persistence + eval via ta.py)          #
# --------------------------------------------------------------------------- #
def _parse_indicator_rules(content: str | None) -> list[IndicatorAlertRule]:
    if not content:
        return []
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return []
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        logger.warning("malformed indicator_alerts.md, ignoring: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    rules: list[IndicatorAlertRule] = []
    for item in data.get("rules", []) or []:
        try:
            rules.append(IndicatorAlertRule(**item))
        except Exception as exc:  # one bad rule never breaks the rest (fail-open)
            logger.warning("skipping invalid indicator rule %r: %s", item, exc)
    return rules


def list_indicator_rules() -> list[IndicatorAlertRule]:
    """All persisted indicator alert rules ([] if none)."""
    try:
        content = md_store.read(INDICATOR_ALERTS_MD)
    except Exception as exc:
        logger.warning("indicator_alerts.md read failed: %s", exc)
        return []
    return _parse_indicator_rules(content)


def _write_indicator_rules(rules: list[IndicatorAlertRule]) -> None:
    payload = {"rules": [r.model_dump() for r in rules]}
    body = "---\n" + yaml.safe_dump(payload, sort_keys=True, allow_unicode=True).strip() + "\n---\n"
    md_store.write_file(INDICATOR_ALERTS_MD, body, "update market indicator-alert rules")


def add_indicator_rule(symbol: str, kind: str, value: float = 0.0, period: int = 14,
                       enabled: bool = True) -> IndicatorAlertRule:
    """UPSERT an indicator rule by (symbol, kind, period): one rule per that triple
    (re-setting the same condition updates rather than duplicating). Persists + returns."""
    rules = list_indicator_rules()
    existing = next(
        (r for r in rules if r.symbol == symbol and r.kind == kind and r.period == period),
        None,
    )
    rule = IndicatorAlertRule(
        id=existing.id if existing else _new_indicator_rule_id(symbol, rules),
        symbol=symbol, kind=kind, value=value, period=period, enabled=enabled,  # type: ignore[arg-type]
    )
    others = [
        r for r in rules
        if not (r.symbol == symbol and r.kind == kind and r.period == period)
    ]
    others.append(rule)
    _write_indicator_rules(others)
    return rule


def _new_indicator_rule_id(symbol: str, existing: list[IndicatorAlertRule]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", symbol.lower()).strip("-") or "ind"
    taken = {r.id for r in existing}
    n = 1
    while f"ind-{base}-{n}" in taken:
        n += 1
    return f"ind-{base}-{n}"


def delete_indicator_rule(rule_id: str) -> bool:
    rules = list_indicator_rules()
    kept = [r for r in rules if r.id != rule_id]
    removed = len(kept) != len(rules)
    if removed:
        _write_indicator_rules(kept)
    return removed


def _eval_one_indicator(rule: IndicatorAlertRule, closes: list[float]) -> tuple[bool, str]:
    """Evaluate ONE indicator rule against an asset's close series via ta.py.
    Returns ``(fired, detail)``. Insufficient data → (False, '<reason>')."""
    from . import ta

    if rule.kind in ("rsi_below", "rsi_above"):
        r = ta.rsi(closes, rule.period)
        if r.latest is None:
            return False, f"RSI not computable ({r.warning})"
        if rule.kind == "rsi_below":
            return (r.latest <= rule.value), f"RSI {r.latest} {'≤' if r.latest <= rule.value else '>'} {rule.value}"
        return (r.latest >= rule.value), f"RSI {r.latest} {'≥' if r.latest >= rule.value else '<'} {rule.value}"

    if rule.kind in ("price_cross_sma_above", "price_cross_sma_below"):
        s = ta.sma(closes, rule.period).series
        # need the last two points where SMA is defined + the matching closes.
        idxs = [i for i, v in enumerate(s) if v is not None]
        if len(idxs) < 2:
            return False, f"SMA{rule.period} needs ≥2 points (have {len(idxs)})"
        i_prev, i_now = idxs[-2], idxs[-1]
        sma_prev, sma_now = s[i_prev], s[i_now]
        c_prev, c_now = closes[i_prev], closes[i_now]
        assert sma_prev is not None and sma_now is not None
        if rule.kind == "price_cross_sma_above":
            fired = c_prev <= sma_prev and c_now > sma_now
            return fired, f"close {c_now} vs SMA{rule.period} {round(sma_now, 4)} ({'crossed above' if fired else 'no cross'})"
        fired = c_prev >= sma_prev and c_now < sma_now
        return fired, f"close {c_now} vs SMA{rule.period} {round(sma_now, 4)} ({'crossed below' if fired else 'no cross'})"

    if rule.kind in ("macd_cross_bull", "macd_cross_bear"):
        m = ta.macd(closes)
        # last two points where BOTH macd + signal are defined.
        idxs = [i for i in range(len(m.macd)) if m.macd[i] is not None and m.signal[i] is not None]
        if len(idxs) < 2:
            return False, "MACD/signal needs ≥2 defined points"
        i_prev, i_now = idxs[-2], idxs[-1]
        md_prev, sg_prev = m.macd[i_prev], m.signal[i_prev]
        md_now, sg_now = m.macd[i_now], m.signal[i_now]
        assert None not in (md_prev, sg_prev, md_now, sg_now)
        if rule.kind == "macd_cross_bull":
            fired = md_prev <= sg_prev and md_now > sg_now  # type: ignore[operator]
            return fired, f"MACD {md_now} vs signal {sg_now} ({'bull cross' if fired else 'no cross'})"
        fired = md_prev >= sg_prev and md_now < sg_now  # type: ignore[operator]
        return fired, f"MACD {md_now} vs signal {sg_now} ({'bear cross' if fired else 'no cross'})"

    return False, f"unknown indicator kind {rule.kind!r}"


def eval_indicator_alerts(rules: list[IndicatorAlertRule] | None = None, *,
                          hours: int = 720) -> list[IndicatorTrigger]:
    """Evaluate each ENABLED indicator rule against its asset's close series (ta.py).
    Returns a trigger per rule with ``fired`` + a human ``detail``. Reads the series
    once per symbol (cached) so N rules on one asset = 1 history read."""
    if rules is None:
        rules = list_indicator_rules()
    series_cache: dict[str, list[float]] = {}
    out: list[IndicatorTrigger] = []
    for rule in rules:
        if not rule.enabled:
            continue
        if rule.symbol not in series_cache:
            series_cache[rule.symbol] = [p.price for p in history(rule.symbol, hours=hours, limit=10000)]
        fired, detail = _eval_one_indicator(rule, series_cache[rule.symbol])
        out.append(IndicatorTrigger(
            id=rule.id, symbol=rule.symbol, kind=rule.kind, value=rule.value,
            period=rule.period, fired=fired, detail=detail,
        ))
    return out


# --------------------------------------------------------------------------- #
# Watchlist — user-curated symbols + a one-shot quick view (price/spark/TA)      #
# --------------------------------------------------------------------------- #
def _parse_watchlist(content: str | None) -> list[str]:
    """Parse watchlist.md front-matter `symbols:` → de-duped uppercased symbol list."""
    if not content:
        return []
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return []
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        logger.warning("malformed watchlist.md, ignoring: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for s in data.get("symbols", []) or []:
        if isinstance(s, str) and s.strip():
            sym = s.strip().upper()
            if sym not in seen:
                seen.add(sym)
                out.append(sym)
    return out


def list_watchlist() -> list[str]:
    """The watchlisted symbols ([] if none), in insertion order."""
    try:
        content = md_store.read(WATCHLIST_MD)
    except Exception as exc:
        logger.warning("watchlist.md read failed: %s", exc)
        return []
    return _parse_watchlist(content)


def _write_watchlist(symbols: list[str]) -> None:
    body = "---\n" + yaml.safe_dump({"symbols": symbols}, sort_keys=False,
                                     allow_unicode=True).strip() + "\n---\n"
    md_store.write_file(WATCHLIST_MD, body, "update market watchlist")


def add_watchlist(symbol: str) -> list[str]:
    """Add a symbol to the watchlist (idempotent, uppercased). If it's not in the
    tracked universe, also REGISTER it as a best-effort crypto asset so it gets
    polled + priced (mirrors get_quote's by-symbol fallback). Returns the new list."""
    sym = symbol.strip().upper()
    symbols = list_watchlist()
    if sym not in symbols:
        symbols.append(sym)
        _write_watchlist(symbols)
    # ensure it's tracked (so the poll routine fetches it + change/spark have a series)
    tracked = {a.get("symbol") for a in tracked_assets()}
    if sym not in tracked:
        assets = list(settings.market_assets or [])
        assets.append({"symbol": sym, "name": sym, "assetClass": "crypto", "cgId": sym.lower()})
        settings.market_assets = assets  # in-process registration (config-level)
        logger.info("watchlist: registered untracked symbol %s as best-effort crypto", sym)
    return symbols


def delete_watchlist(symbol: str) -> bool:
    """Remove a symbol from the watchlist. Returns True if it was present. Does NOT
    un-track the asset (other features may still use it) — just drops the watch."""
    sym = symbol.strip().upper()
    symbols = list_watchlist()
    if sym not in symbols:
        return False
    _write_watchlist([s for s in symbols if s != sym])
    return True


def _sparkline(symbol: str, hours: int = 24, points: int = SPARKLINE_POINTS) -> list[float]:
    """A short, evenly-downsampled close-price array (oldest→newest) for a mini chart.
    Empty if no series. Downsamples to EXACTLY ``points`` (the last sample is always
    the most-recent close) so the payload stays small + bounded."""
    closes = [p.price for p in history(symbol, hours=hours, limit=10000)]
    n = len(closes)
    if n <= points:
        return closes
    # Even stride over ``points`` slots; force the final slot to the most-recent close.
    step = (n - 1) / (points - 1)
    idxs = [int(round(i * step)) for i in range(points)]
    idxs[-1] = n - 1
    return [closes[i] for i in idxs]


def watchlist_data(hours: int = 168) -> tuple[list[dict], list[str]]:
    """Build the rich watchlist view: one row per symbol with price + %change +
    sparkline + a quick RSI/trend read (ta.py). Returns ``(items, warnings)``. A
    symbol with no series → row still present (price from quote, spark [], rsi None),
    flagged in its own ``warning`` — never a 500.
    """
    from . import ta

    symbols = list_watchlist()
    items: list[dict] = []
    warnings: list[str] = []
    asset_by_symbol = {a.get("symbol"): a for a in tracked_assets()}

    for sym in symbols:
        quote = get_quote(sym)  # fail-open: CoinGecko down → last-known/mock
        name = (asset_by_symbol.get(sym) or {}).get("name") or sym
        closes = [p.price for p in history(sym, hours=hours, limit=10000)]
        spark = _sparkline(sym, hours=24)
        rsi_res = ta.rsi(closes, 14)
        summ = ta.summarize(closes) if closes else None
        row_warn: str | None = None
        if quote is None:
            row_warn = f"{sym}: no quote available"
        elif not closes:
            row_warn = f"{sym}: no price history yet (sparkline empty, RSI/trend pending)"

        # changePct: prefer our own series (24h lookback); fall back to the quote's.
        change_pct: float | None = None
        if quote is not None:
            change_pct = derive_change_pct(sym, quote.price, quote.changePct)

        item = WatchlistItem(
            symbol=sym,
            name=name,
            price=quote.price if quote is not None else 0.0,
            changePct=change_pct,
            source=quote.source if quote is not None else "unavailable",
            sparkline=spark,
            rsi=rsi_res.latest,
            trend=(summ["signals"]["trend"] if summ else "flat"),
            warning=row_warn,
        )
        if row_warn:
            warnings.append(row_warn)
        items.append(item.model_dump())
    return items, warnings


# --------------------------------------------------------------------------- #
# Macro stub + alert history (run_log)                                          #
# --------------------------------------------------------------------------- #
def macro_signals() -> list[MacroSignal]:
    """Stub macro block this build (Fear&Greed/BTC Dominance/Brent). Deterministic.

    value is a display-ready STRING (mixed units). Real feed swaps in later
    (data-fallback: mock-first, never block on a paid source).
    """
    return [
        MacroSignal(name="Fear & Greed", value="38", status="fear", note="thị trường sợ hãi"),
        MacroSignal(name="BTC Dominance", value="54%", status="neutral", note=""),
        MacroSignal(name="Brent Oil", value="$72", status="neutral", note=""),
    ]


def alert_history(limit: int = 50) -> list[AlertEvent]:
    """Fired alerts from run_log (recorded by the market-poll routine, T3)."""
    events: list[AlertEvent] = []
    for row in db.recent_runs(MARKET_POLL_ID, limit=limit):
        detail = row["detail"]
        if not detail:
            continue
        try:
            payload = json.loads(detail)
        except (json.JSONDecodeError, TypeError):
            continue
        if payload.get("kind") != "alert":
            continue
        try:
            events.append(
                AlertEvent(
                    symbol=payload["symbol"], op=payload["op"],
                    threshold=payload["threshold"], price=payload["price"],
                    ts=row["started_at"],
                )
            )
        except (KeyError, Exception):  # malformed history row → skip, never crash
            continue
    return events


# --------------------------------------------------------------------------- #
# Composite market view + history endpoint                                      #
# --------------------------------------------------------------------------- #
def get_market() -> tuple[dict, list[str]]:
    """The live market view: {quotes, triggers, macro, alertHistory} + warnings."""
    raw_quotes, warnings = reader.read_quotes(tracked_assets())
    quotes = _apply_change_pct(raw_quotes)
    rules = list_rules()
    triggers = eval_alerts(quotes, rules)
    data = {
        "quotes": [q.model_dump() for q in quotes],
        "triggers": [t.model_dump() for t in triggers],
        "macro": [m.model_dump() for m in macro_signals()],
        "alertHistory": [e.model_dump() for e in alert_history()],
    }
    return data, warnings


def history(asset: str, hours: int = 24, limit: int = 1000) -> list[PricePoint]:
    """price_history points for an asset over the last ``hours`` (oldest→newest).

    ``hours`` windows the series (default 24h); ``limit`` caps the row count.
    """
    since = (_now() - timedelta(hours=max(1, hours))).isoformat()
    rows = db.prices_for(asset, since=since, limit=limit)
    return [PricePoint(asset=r["asset"], price=float(r["price"]), ts=r["ts"]) for r in rows]


def price_at(asset: str, ts: str) -> PricePoint | None:
    """Point-in-time price for ``asset`` AS OF ``ts`` (ISO-8601 UTC) — the most recent
    OWNED price_history point at or before ``ts``. Returns None when we have no point
    that old (HONEST: we do NOT fabricate or interpolate — the caller learns the series
    doesn't cover that instant). This is the building block for "what was X worth on
    date D" without guessing. ``ts`` is taken as given (the DB stores ISO-8601 UTC).
    """
    row = db.price_at_or_before(asset, ts)
    if row is None:
        return None
    return PricePoint(asset=row["asset"], price=float(row["price"]), ts=row["ts"])


def backfill(symbols: list[str] | None = None, days: int = 365) -> dict:
    """Backfill HISTORICAL daily prices from CoinGecko market_chart — fixes the
    "only ~9 days of history" gap (the 5-min poller only accumulates forward).

    IDEMPOTENT + DEDUP: for each asset, fetch ``days`` of daily history, then insert
    ONLY the days the asset doesn't already have a point on (``db.price_days``). Re-running
    fills genuine gaps and never duplicates an existing day. Fail-open PER symbol: a
    feed error for one asset is logged + summarized, never aborts the rest. Only assets
    with a ``cgId`` (crypto + gold) can be backfilled — mock assets (etf/vn) have no
    historical source and are reported as skipped with a reason.

    ``symbols`` = which tracked assets to backfill (default: ALL with a cgId). Returns
    ``{symbol: {inserted, skipped, error?}}`` so the caller sees exactly what happened.
    """
    assets = tracked_assets()
    by_symbol = {a.get("symbol"): a for a in assets}
    if symbols:
        targets: list[str] = list(symbols)
    else:
        targets = [s for a in assets if (s := a.get("symbol"))]  # drop any symbol-less entry

    summary: dict[str, dict] = {}
    for sym in targets:
        asset = by_symbol.get(sym)
        if asset is None:
            summary[sym] = {"inserted": 0, "skipped": 0, "error": "not a tracked asset"}
            continue
        cg_id = asset.get("cgId")
        if not cg_id:
            summary[sym] = {"inserted": 0, "skipped": 0,
                            "error": f"no cgId — {asset.get('assetClass')} has no historical source"}
            continue
        try:
            points = reader.fetch_market_chart(cg_id, days=days)
        except Exception as exc:  # one asset's feed failing must not abort the rest
            logger.warning("backfill: market_chart %r failed: %s", sym, exc)
            summary[sym] = {"inserted": 0, "skipped": 0, "error": f"{type(exc).__name__}: {exc}"}
            continue
        existing_days = db.price_days(sym)
        inserted = 0
        skipped = 0
        for ts_iso, price in points:
            day = ts_iso[:10]
            if day in existing_days:
                skipped += 1  # dedup: this day already has a point — don't duplicate
                continue
            db.record_price(sym, price, ts_iso, source="backfill")
            existing_days.add(day)  # guard against duplicate days WITHIN this fetch too
            inserted += 1
        summary[sym] = {"inserted": inserted, "skipped": skipped}
    return summary


# --------------------------------------------------------------------------- #
# OHLC candles — HONEST: built from the close-tick series (NO fabricated bars)   #
# --------------------------------------------------------------------------- #
# The data source (CoinGecko /simple/price) gives ONE price per poll; price_history
# stores close-only. There is NO real high/low/open from the feed. So a candle here
# is the open/high/low/close of the ACTUAL close-ticks that fell inside each time
# bucket: open = first tick, high = max tick, low = min tick, close = last tick. This
# is genuine observed price action aggregated to an interval (the standard way to
# build candles from a tick/trade stream) — NOT fabricated OHLC. A bucket with a
# single tick yields o==h==l==c (honest: one observation).
def candles(asset: str, hours: int = 168, interval_minutes: int = 60,
            limit: int = 10000) -> tuple[list[dict], list[str]]:
    """Bucket the close-tick series into OHLC candles of ``interval_minutes``.

    Returns ``(candles, warnings)`` where each candle is
    ``{ts, open, high, low, close, ticks}`` (ts = bucket start, ISO-8601 UTC; ``ticks``
    = how many real observations the bar aggregates — 1 = a degenerate single-tick bar).
    ``warnings`` always carries the close-derived disclaimer so the FE renders honestly.
    """
    warnings = [
        "OHLC is derived from the close-tick series (CoinGecko /simple/price is close-only) "
        "— each bar's O/H/L/C are the first/max/min/last observed close in the interval, "
        "NOT exchange candles. A bar with ticks=1 is a single observation."
    ]
    if interval_minutes <= 0:
        return [], ["interval_minutes must be > 0"]
    points = history(asset, hours=hours, limit=limit)
    if not points:
        return [], warnings + ["no price history for this asset yet"]

    bucket_ms = interval_minutes * 60
    buckets: dict[int, list[float]] = {}
    order: list[int] = []
    for p in points:
        try:
            dt = datetime.fromisoformat(p.ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue  # skip an unparseable timestamp (defensive)
        epoch = int(dt.timestamp())
        key = (epoch // bucket_ms) * bucket_ms  # floor to the interval start
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(p.price)

    out: list[dict] = []
    for key in order:
        ticks = buckets[key]
        bar_ts = datetime.fromtimestamp(key, tz=timezone.utc).isoformat()
        out.append({
            "ts": bar_ts,
            "open": ticks[0],
            "high": max(ticks),
            "low": min(ticks),
            "close": ticks[-1],
            "ticks": len(ticks),
        })
    return out, warnings


# --------------------------------------------------------------------------- #
# Technical analysis — indicators over the close series (price_history)          #
# --------------------------------------------------------------------------- #
# Map a requested indicator name → (callable, how to project its result to JSON).
# Each projector returns a plain dict (latest value(s) + warning); ``full=True``
# additionally attaches the aligned series. price_history is close-only, so ATR
# runs in its close-only mode (the result carries that as a warning).
_TA_NAMES = ("sma", "ema", "rsi", "macd", "bollinger", "atr", "summary")


def compute_indicators(asset: str, names: list[str], *, hours: int = 720,
                       full: bool = False, limit: int = 5000) -> tuple[dict, list[str]]:
    """Compute the requested technical indicators for an asset's close series.

    Returns ``(data, warnings)``. ``data`` = ``{symbol, points, asOf, indicators:{...}}``.
    Unknown indicator names are skipped + warned (never an error). An empty/short
    series yields each indicator's own short-series warning, not a crash.
    """
    from . import ta

    closes = [p.price for p in history(asset, hours=hours, limit=limit)]
    warnings: list[str] = []
    out: dict[str, object] = {}

    wanted = [n.strip().lower() for n in names if n and n.strip()]
    if not wanted:
        wanted = ["summary"]

    for name in wanted:
        if name not in _TA_NAMES:
            warnings.append(f"unknown indicator {name!r} — skipped (valid: {', '.join(_TA_NAMES)})")
            continue
        if name == "sma":
            rs = ta.sma(closes, 20)
            out["sma"] = {"period": rs.period, "latest": rs.latest, "warning": rs.warning,
                          **({"series": rs.series} if full else {})}
        elif name == "ema":
            re_ = ta.ema(closes, 20)
            out["ema"] = {"period": re_.period, "latest": re_.latest, "warning": re_.warning,
                          **({"series": re_.series} if full else {})}
        elif name == "rsi":
            rr = ta.rsi(closes, 14)
            out["rsi"] = {"period": rr.period, "latest": rr.latest, "warning": rr.warning,
                          **({"series": rr.series} if full else {})}
        elif name == "macd":
            rm = ta.macd(closes)
            out["macd"] = {
                "fast": rm.fast, "slow": rm.slow, "signalPeriod": rm.signal_period,
                "latestMacd": rm.latest_macd, "latestSignal": rm.latest_signal,
                "latestHistogram": rm.latest_histogram, "warning": rm.warning,
                **({"macd": rm.macd, "signal": rm.signal, "histogram": rm.histogram} if full else {}),
            }
        elif name == "bollinger":
            rb = ta.bollinger(closes, 20, 2.0)
            out["bollinger"] = {
                "period": rb.period, "numStd": rb.num_std,
                "latestUpper": rb.latest_upper, "latestMiddle": rb.latest_middle,
                "latestLower": rb.latest_lower, "warning": rb.warning,
                **({"upper": rb.upper, "middle": rb.middle, "lower": rb.lower} if full else {}),
            }
        elif name == "atr":
            ra = ta.atr(closes=closes, period=14)  # close-only (price_history has no OHLC)
            out["atr"] = {"period": ra.period, "latest": ra.latest, "warning": ra.warning,
                          **({"series": ra.series} if full else {})}
        elif name == "summary":
            out["summary"] = ta.summarize(closes)

    data = {
        "symbol": asset,
        "points": len(closes),
        "asOf": _now().isoformat(),
        "indicators": out,
    }
    if len(closes) == 0:
        warnings.append("no price history for this asset yet — indicators are empty")
    return data, warnings


# --------------------------------------------------------------------------- #
# Multi-symbol analytics — correlation + comparison (over the close series)      #
# --------------------------------------------------------------------------- #
MAX_COMPARE_SYMBOLS = 10  # cap so a request stays bounded (N² for correlation)


def _series_for(symbols: list[str], hours: int) -> tuple[dict[str, list[float]], list[str]]:
    """Fetch + SANITIZE the close series for each symbol. Returns ``(series_by_symbol,
    warnings)``. The series is robustly de-outliered (ta.sanitize_series — drops stray
    seed/test points orders of magnitude off the median) BEFORE the analytics math, so
    a $0.5 artifact among $60k closes can't blow up changePct/correlation. The DB is
    NOT mutated — this is read-time filtering only. A symbol with no series yields [];
    a filtered symbol carries an honest per-symbol warning (how many points dropped)."""
    from . import ta

    series: dict[str, list[float]] = {}
    warnings: list[str] = []
    for sym in symbols:
        raw = [p.price for p in history(sym, hours=hours, limit=10000)]
        cleaned, warn = ta.sanitize_series(raw)
        series[sym] = cleaned
        if not raw:
            warnings.append(f"{sym}: no price history")
        elif warn:
            warnings.append(f"{sym}: {warn}")
    return series, warnings


def correlation(symbols: list[str], hours: int = 720) -> tuple[dict, list[str]]:
    """Pairwise Pearson correlation matrix over the symbols' close series. Needs ≥2
    symbols (caller enforces); series are tail-aligned per pair. Returns ``(data,
    warnings)``; a pair with no overlap / a flat series → None (honest, not 0)."""
    from . import ta

    series, warnings = _series_for(symbols, hours)
    result = ta.correlation_matrix(series)
    warnings += [w for w in result["warnings"] if w not in warnings]
    data = {
        "symbols": result["symbols"],
        "matrix": result["matrix"],
        "window_hours": hours,
        "asOf": _now().isoformat(),
    }
    return data, warnings


def compare(symbols: list[str], hours: int = 720) -> tuple[dict, list[str]]:
    """Side-by-side comparison table: each symbol's {changePct, volatility, rsi, trend}
    over the window, for relative ranking. NEUTRAL numbers — no advice. A symbol with
    a short/absent series gets honest None fields, never fabricated values."""
    from . import ta

    series, warnings = _series_for(symbols, hours)
    rows = []
    for sym in symbols:
        m = ta.compare_metrics(series[sym])
        rows.append({"symbol": sym, **{k: m[k] for k in ("changePct", "volatility", "rsi", "trend", "points")}})
    data = {"window_hours": hours, "asOf": _now().isoformat(), "comparison": rows}
    return data, warnings


def relative_strength(symbol: str, vs: str = "BTC", hours: int = 720) -> tuple[dict, list[str]]:
    """``symbol`` vs a ``vs`` benchmark: the price-ratio trend + % change over the
    window. ratioTrend 'up' = OUTPERFORMING the benchmark (NEUTRAL observation, NOT a
    recommendation). Returns ``(data, warnings)``; None fields when data is thin."""
    from . import ta

    raw_sym = [p.price for p in history(symbol, hours=hours, limit=10000)]
    raw_bench = [p.price for p in history(vs, hours=hours, limit=10000)]
    warnings: list[str] = []
    sym_series, sym_warn = ta.sanitize_series(raw_sym)
    bench_series, bench_warn = ta.sanitize_series(raw_bench)
    if not raw_sym:
        warnings.append(f"{symbol}: no price history")
    elif sym_warn:
        warnings.append(f"{symbol}: {sym_warn}")
    if not raw_bench:
        warnings.append(f"benchmark {vs}: no price history")
    elif bench_warn:
        warnings.append(f"benchmark {vs}: {bench_warn}")
    rs = ta.relative_strength(sym_series, bench_series)
    data = {"symbol": symbol, "benchmark": vs, "window_hours": hours,
            "asOf": _now().isoformat(), **rs}
    if rs.get("warning"):
        warnings.append(rs["warning"])
    return data, warnings


# --------------------------------------------------------------------------- #
# Poll (T3 routine code path): fetch → persist → eval → record fired alerts     #
# --------------------------------------------------------------------------- #
def _already_hit(symbol: str, op: str) -> bool:
    """True if the MOST RECENT recorded alert for (symbol, op) was a hit.

    Edge-trigger: we only record a NEW alert event when the rule transitions INTO
    hit (was not already the last-recorded hit), so a standing hit doesn't spam
    run_log every 5 minutes.
    """
    for ev in alert_history(limit=100):
        if ev.symbol == symbol and ev.op == op:
            return True  # most-recent matching event exists → already fired
    return False


def poll_once() -> dict:
    """One market-poll pass: persist each quote + record newly-fired alerts.

    Fail-open per asset (reader already degrades a bad feed; persistence of one
    asset failing never aborts the rest). Edge-triggered alert recording: a rule
    that is already in its last-recorded hit state is NOT re-recorded. Returns a
    small summary dict (also used as the run_log detail by the routine wrapper).
    Detection + record only — no notification side-effects.
    """
    import json

    quotes, warnings = reader.read_quotes(tracked_assets())
    persisted = 0
    for q in quotes:
        try:
            db.record_price(q.symbol, q.price, q.ts, currency=q.currency, source=q.source)
            persisted += 1
        except Exception as exc:  # one asset's persist failing must not abort the poll
            logger.error("market-poll: persist %r failed: %s", q.symbol, exc)
            warnings.append(f"{q.symbol}: persist failed ({exc})")

    quotes = _apply_change_pct(quotes)
    triggers = eval_alerts(quotes, list_rules())
    fired = 0
    for t in triggers:
        if t.state != "hit":
            continue
        if _already_hit(t.symbol, t.op):
            continue  # edge-trigger: standing hit, don't re-record
        db.record_run(
            MARKET_POLL_ID, "warn", _now().isoformat(),
            detail=json.dumps({
                "kind": "alert", "symbol": t.symbol, "op": t.op,
                "threshold": t.threshold, "price": t.price,
            }),
        )
        fired += 1
    return {"persisted": persisted, "fired": fired, "warnings": warnings}
