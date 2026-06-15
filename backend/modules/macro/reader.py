"""modules/macro/reader.py — macro data fetch (FRED), fail-open to honest mock (MACRO-1).

Fetches the latest observations for each tracked indicator from FRED (St. Louis Fed,
free JSON API). FRED requires an api_key — so:
  - key configured (``settings.fred_api_key``) → real fetch; returns (points, source='fred').
  - NO key, OR network/HTTP/parse failure → honest MOCK series + a warning
    ("macro mock (no FRED key)" / "macro fetch failed — mock"). NEVER raises, never
    blocks (mock-first per the dispatch — a missing paid/keyed source ships a stub).

The mock is DETERMINISTIC (seeded per indicator) so tests + repeated calls are stable,
and it is clearly tagged source='mock' so the overview can flag it honestly.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import httpx

from core.config import settings

logger = logging.getLogger("life-os.macro.reader")

FRED_TIMEOUT_S = 8.0

# Plausible recent baselines per indicator for the deterministic mock (so a no-key
# install still shows sensible numbers, clearly tagged source='mock').
_MOCK_BASE = {
    "fed_funds_rate": 5.33,   # %
    "cpi": 314.0,             # index level
    "dxy": 121.0,             # broad USD index
}


def _today() -> datetime:
    return datetime.now(timezone.utc)


def _det_jitter(indicator: str, day_offset: int, scale: float) -> float:
    """Deterministic small offset seeded by (indicator, day) — stable across calls so
    tests + repeated mocks don't drift (no Math.random)."""
    h = hashlib.sha256(f"{indicator}:{day_offset}".encode()).hexdigest()
    # map first 4 hex chars → [-1, 1]
    frac = (int(h[:4], 16) / 0xFFFF) * 2 - 1
    return round(frac * scale, 4)


def _mock_points(indicator: str, n: int = 6) -> list[dict]:
    """Deterministic mock series for one indicator (oldest→newest), monthly cadence.
    Clearly source='mock'. n points so trend (latest vs previous) is meaningful."""
    base = _MOCK_BASE.get(indicator, 100.0)
    scale = base * 0.01  # ~1% wobble
    pts: list[dict] = []
    for i in range(n):
        # i from oldest (n-1 months ago) to newest (this month)
        months_ago = (n - 1) - i
        ts = (_today() - timedelta(days=30 * months_ago)).strftime("%Y-%m-%d")
        value = round(base + _det_jitter(indicator, months_ago, scale), 4)
        pts.append({"indicator": indicator, "value": value, "ts": ts, "source": "mock"})
    return pts


def _fetch_fred_series(series_id: str, *, limit: int = 12) -> list[dict]:
    """Fetch the latest ``limit`` observations of a FRED series. Returns raw
    [{date, value}] oldest→newest. Raises on any failure (caller fails open)."""
    url = f"{settings.fred_base}/series/observations"
    params = {
        "series_id": series_id,
        "api_key": settings.fred_api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(limit),
    }
    resp = httpx.get(url, params=params, timeout=FRED_TIMEOUT_S)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, dict) or "observations" not in body:
        raise ValueError("unexpected FRED body (no observations)")
    out: list[dict] = []
    for obs in reversed(body["observations"]):  # desc → oldest-first
        raw = obs.get("value")
        if raw in (None, "", "."):  # FRED uses "." for missing
            continue
        try:
            out.append({"date": obs["date"], "value": float(raw)})
        except (TypeError, ValueError):
            continue
    return out


def fetch_latest(indicator: str) -> tuple[list[dict], str | None]:
    """Fetch recent observations for one indicator. Returns ``(points, warning)``:
    points are [{indicator, value, ts, source}] oldest→newest. Fail-open:
      - no FRED key            → mock points + "macro mock (no FRED key) for <ind>"
      - unknown indicator      → ([], "unknown macro indicator <ind>")
      - network/HTTP/parse err → mock points + "macro fetch failed for <ind> — mock"
    NEVER raises."""
    series_id = settings.fred_series.get(indicator)
    if series_id is None:
        return [], f"unknown macro indicator {indicator!r}"

    if not settings.fred_api_key:
        pts = _mock_points(indicator)
        return pts, f"macro mock (no FRED key) for {indicator}"

    try:
        raw = _fetch_fred_series(series_id)
        pts = [
            {"indicator": indicator, "value": r["value"], "ts": r["date"], "source": "fred"}
            for r in raw
        ]
        if not pts:
            return _mock_points(indicator), f"macro: FRED returned no usable points for {indicator} — mock"
        return pts, None
    except Exception as exc:  # noqa: BLE001 — fail-open to mock, never block
        logger.warning("FRED fetch failed for %s (%s): %s", indicator, series_id, exc)
        return _mock_points(indicator), f"macro fetch failed for {indicator} — mock"
