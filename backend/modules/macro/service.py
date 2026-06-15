"""modules/macro/service.py — macro business logic (MACRO-1).

Capture → store → read, mirroring market. NEUTRAL by contract: trend is a DESCRIPTIVE
direction (latest vs prior observation), never a forecast.

  refresh()      — fetch each tracked indicator (FRED or fail-open mock) → persist.
  get_overview() — every indicator's latest value + descriptive trend.
  get_history()  — one indicator's time-series over a window.
"""

from __future__ import annotations

import logging

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
}

# Below this absolute change the trend is reported "flat" (avoids calling float noise a
# move). Per-indicator-agnostic small epsilon; macro values are O(1)-O(100).
_FLAT_EPS = 1e-9


def tracked_indicators() -> list[str]:
    """The macro indicators tracked (keys of the configured FRED series map)."""
    return list(settings.fred_series.keys())


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


def get_history(indicator: str, days: int = 365, limit: int = 1000) -> MacroHistory | None:
    """One indicator's time-series over the last ``days`` (oldest→newest). None if the
    indicator is not tracked (→ 404). Empty series → honest empty points list."""
    if indicator not in settings.fred_series:
        return None
    store.init_macro_tables()
    # cold start: prime the series so history isn't spuriously empty
    if store.count(indicator) == 0:
        refresh()
    from datetime import datetime, timedelta, timezone

    since = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    rows = store.history(indicator, since=since, limit=limit)
    points = [
        MacroPoint(indicator=r["indicator"], value=float(r["value"]), ts=r["ts"], source=r["source"])
        for r in rows
    ]
    return MacroHistory(indicator=indicator, points=points)
