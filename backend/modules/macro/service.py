"""modules/macro/service.py — macro business logic (MACRO-1).

Capture → store → read, mirroring market. NEUTRAL by contract: trend is a DESCRIPTIVE
direction (latest vs prior observation), never a forecast.

  refresh()      — fetch each tracked indicator (FRED or fail-open mock) → persist.
  get_overview() — every indicator's latest value + descriptive trend.
  get_history()  — one indicator's time-series over a window.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.config import settings

from . import reader, store
from .schema import (
    MacroHistory,
    MacroIndicatorView,
    MacroOverview,
    MacroPoint,
    Trend,
)

logger = logging.getLogger("life-os.macro.service")

# Human labels + units per indicator (presentation only; keeps the API self-describing).
_LABELS = {
    "fed_funds_rate": ("Fed Funds Rate", "%"),
    "cpi": ("US CPI", "index"),
    "dxy": ("US Dollar Index (DXY)", "index"),
    # FINANCE-ASSISTANT P1 (#52) — the macro-cycle substrate.
    "yield_curve_10y2y": ("10Y-2Y Treasury Spread", "%"),   # negative = inverted (recession signal)
    "unemployment": ("US Unemployment Rate", "%"),
    "m2_liquidity": ("US M2 Money Supply", "$B"),
    "industrial_production": ("US Industrial Production", "index"),
    # daily sentiment (snapshot routine → macro_history; NOT FRED, so not in get_overview's
    # FRED-driven loop — read via get_history).
    "fear_greed": ("Crypto Fear & Greed", "index"),
    "btc_dominance": ("BTC Dominance", "%"),
}

# Below this absolute change the trend is reported "flat" (avoids calling float noise a
# move). Per-indicator-agnostic small epsilon; macro values are O(1)-O(100).
_FLAT_EPS = 1e-9


def tracked_indicators() -> list[str]:
    """The macro indicators tracked (keys of the configured FRED series map)."""
    return list(settings.fred_series.keys())


# FINANCE-ASSISTANT P1 (#52): Phase-1 source-based confidence STUB. A real FRED CSV point →
# high (0.9); a fail-open mock placeholder → low (0.2). This is the SEAM:
# Phase-2: replace with compute_q() (freshness × coverage × agreement) — the call-site
# (_indicator_view) stays unchanged; only this fn's body swaps for the real q.
_CONF_FRED = 0.9
_CONF_MOCK = 0.2


def _confidence_for(source: str) -> float:
    """Source-based confidence (Phase-1 stub): 'fred' (real) → 0.9, else (mock) → 0.2."""
    # Phase-2: replace with compute_q() (freshness × coverage × agreement).
    return _CONF_FRED if source == "fred" else _CONF_MOCK


def _trend(latest: float | None, previous: float | None) -> Trend:
    """Descriptive direction of the latest move (NOT a forecast). <2 points → flat."""
    if latest is None or previous is None:
        return "flat"
    delta = latest - previous
    if delta > _FLAT_EPS:
        return "up"
    if delta < -_FLAT_EPS:
        return "down"
    return "flat"


def refresh() -> tuple[int, list[str]]:
    """Fetch + persist the latest observations for every tracked indicator. Returns
    ``(points_written, warnings)``. Fail-open per indicator (a fetch failure → mock
    points + warning, never aborts the others)."""
    store.init_macro_tables()
    written = 0
    warnings: list[str] = []
    for indicator in tracked_indicators():
        points, warning = reader.fetch_latest(indicator)
        if warning:
            warnings.append(warning)
        for p in points:
            try:
                store.record_point(p["indicator"], p["value"], p["ts"], p.get("source", "fred"))
                written += 1
            except Exception as exc:  # noqa: BLE001 — one bad row must not abort the rest
                logger.error("macro persist failed for %s @ %s: %s", indicator, p.get("ts"), exc)
                warnings.append(f"{indicator}: persist failed for {p.get('ts')}")
    return written, warnings


def _indicator_view(indicator: str) -> MacroIndicatorView:
    """Build one indicator's view from stored points. Auto-refreshes on first read if
    the indicator has no data yet (so an unprimed install still returns numbers)."""
    label, unit = _LABELS.get(indicator, (indicator, ""))
    rows = store.recent(indicator, limit=2)  # newest-first
    if not rows:
        # cold start: fetch + persist once, then re-read
        refresh()
        rows = store.recent(indicator, limit=2)

    n = store.count(indicator)
    if not rows:
        return MacroIndicatorView(indicator=indicator, label=label, unit=unit, points=0)

    latest_row = rows[0]
    prev_row = rows[1] if len(rows) > 1 else None
    latest_val = float(latest_row["value"])
    prev_val = float(prev_row["value"]) if prev_row is not None else None
    change = round(latest_val - prev_val, 4) if prev_val is not None else None
    return MacroIndicatorView(
        indicator=indicator,
        label=label,
        unit=unit,
        latest=latest_val,
        asOf=latest_row["ts"],
        previous=prev_val,
        change=change,
        trend=_trend(latest_val, prev_val),
        source=latest_row["source"],
        points=n,
        confidence=_confidence_for(latest_row["source"]),
    )


def get_overview() -> tuple[MacroOverview, list[str]]:
    """Every tracked indicator's latest value + descriptive trend. NEUTRAL — no
    forecast. Fail-open: an empty/unreachable source yields honest mock + a warning.
    ``asOf`` = freshest point across indicators; source='fred' if ANY indicator's
    latest is live, else 'mock'."""
    store.init_macro_tables()
    views: list[MacroIndicatorView] = []
    warnings: list[str] = []
    for indicator in tracked_indicators():
        try:
            views.append(_indicator_view(indicator))
        except Exception as exc:  # noqa: BLE001 — one bad indicator must not 500 the overview
            logger.error("macro overview failed for %s: %s", indicator, exc)
            warnings.append(f"{indicator}: overview read failed ({exc})")

    as_ofs = [v.asOf for v in views if v.asOf]
    as_of = max(as_ofs) if as_ofs else None
    source = "fred" if any(v.source == "fred" for v in views if v.latest is not None) else "mock"
    if source == "mock" and views:
        warnings.append("macro data is mock (no live FRED source) — values are placeholders")
    return MacroOverview(indicators=views, asOf=as_of, source=source), warnings


# --------------------------------------------------------------------------- #
# FINANCE-ASSISTANT P1 (#52) — daily macro+sentiment snapshot routine.           #
# Snapshots the DAILY-CHANGING signals (Fear&Greed, yield-curve, BTC dominance)  #
# into macro_history each day. The MONTHLY FRED fields (CPI/UNRATE/M2/INDPRO)     #
# self-dedupe: record_point upserts by (indicator, ts), and a monthly value keeps #
# its month-start FRED ts — so re-running refresh() daily NEVER duplicates a       #
# monthly row (it upserts the same ts). The daily signals carry TODAY's ts (a new  #
# row per day = the daily series). Fail-soft per signal (one source down → warn,   #
# the others still land). Mirrors morning_pull's add-on discipline.               #
# --------------------------------------------------------------------------- #
# Daily-cadence sentiment indicators (NOT FRED — their own free sources).
DAILY_SENTIMENT = ("fear_greed", "btc_dominance")


def macro_sentiment_snapshot() -> tuple[str, str]:
    """Daily routine: snapshot the daily-changing macro+sentiment signals into macro_history.

    - Fear & Greed index (alternative.me, free) → indicator 'fear_greed' (today's ts).
    - BTC dominance (coingecko /global, free) → indicator 'btc_dominance' (today's ts).
    - yield_curve_10y2y (FRED T10Y2Y, daily) → refreshed via the normal FRED path (its own
      daily ts; retried + fail-open to mock if HTTP-000).
    The MONTHLY FRED fields are NOT re-snapshotted here (they self-dedupe by month-ts via
    refresh()'s upsert; re-storing an unchanged monthly value daily would be noise).

    Returns ``(status, summary)`` for the run_log. Fail-soft per signal — a down source warns
    but never aborts the others. ``status`` = 'warn' if any signal failed, else 'ok'."""
    store.init_macro_tables()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parts: list[str] = []
    warned = False

    # Fear & Greed (daily)
    try:
        fng, fng_src = reader.fetch_fear_greed()
        if fng is not None:
            store.record_point("fear_greed", float(fng), ts, fng_src)
            parts.append(f"F&G {int(fng)}")
        else:
            parts.append("F&G n/a"); warned = True
    except Exception as exc:  # noqa: BLE001 — one signal down must not abort the others
        logger.error("macro snapshot: fear_greed failed: %s", exc)
        parts.append(f"F&G ERR ({type(exc).__name__})"); warned = True

    # BTC dominance (daily)
    try:
        btcd, btcd_src = reader.fetch_btc_dominance()
        if btcd is not None:
            store.record_point("btc_dominance", float(btcd), ts, btcd_src)
            parts.append(f"BTC.d {btcd:.1f}%")
        else:
            parts.append("BTC.d n/a"); warned = True
    except Exception as exc:  # noqa: BLE001
        logger.error("macro snapshot: btc_dominance failed: %s", exc)
        parts.append(f"BTC.d ERR ({type(exc).__name__})"); warned = True

    # yield_curve (FRED daily) — refresh just this one (its own daily ts; retried+fail-open)
    try:
        points, warning = reader.fetch_latest("yield_curve_10y2y")
        for p in points:
            store.record_point(p["indicator"], p["value"], p["ts"], p.get("source", "fred"))
        if warning:
            parts.append("yield mock"); warned = True
        elif points:
            parts.append(f"yield {points[-1]['value']:+.2f}")
    except Exception as exc:  # noqa: BLE001
        logger.error("macro snapshot: yield_curve failed: %s", exc)
        parts.append(f"yield ERR ({type(exc).__name__})"); warned = True

    status = "warn" if warned else "ok"
    return status, "Macro snapshot: " + ", ".join(parts)


def get_history(indicator: str, days: int = 365, limit: int = 1000) -> MacroHistory | None:
    """One indicator's time-series over the last ``days`` (oldest→newest). None if the
    indicator is not tracked (→ 404). Empty series → honest empty points list.

    FINANCE-ASSISTANT P1 (#52): the daily-sentiment indicators (fear_greed/btc_dominance) are
    valid here too — they live in macro_history (snapshot routine), not fred_series, so they're
    NOT cold-start-refreshed (no FRED series to pull); an unprimed sentiment series is honest-
    empty until the snapshot routine runs."""
    from datetime import timedelta

    is_fred = indicator in settings.fred_series
    if not (is_fred or indicator in DAILY_SENTIMENT):
        return None
    store.init_macro_tables()
    # cold start: prime FRED series so history isn't spuriously empty. Sentiment indicators
    # have no FRED series to pull — they fill via the daily snapshot routine, honest-empty
    # until then (don't refresh()).
    if is_fred and store.count(indicator) == 0:
        refresh()

    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    rows = store.history(indicator, since=since, limit=limit)
    points = [
        MacroPoint(indicator=r["indicator"], value=float(r["value"]), ts=r["ts"], source=r["source"])
        for r in rows
    ]
    return MacroHistory(indicator=indicator, points=points)
