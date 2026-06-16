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
# FINANCE-ASSISTANT P1 (#52): how many times to retry the no-key CSV fetch before falling
# open to mock. Some FRED series (T10Y2Y) intermittently HTTP-000/504; a couple of retries
# rescue a transient blip without demoting a real indicator to mock.
FRED_CSV_RETRIES = 3

# Plausible recent baselines per indicator for the deterministic mock (so a no-key
# install still shows sensible numbers, clearly tagged source='mock').
_MOCK_BASE = {
    "fed_funds_rate": 5.33,   # %
    "cpi": 314.0,             # index level
    "dxy": 121.0,             # broad USD index
    # FINANCE-ASSISTANT P1 (#52) — plausible recent baselines for the new indicators (mock
    # only fires when the no-key CSV is unreachable; clearly tagged source='mock').
    "yield_curve_10y2y": 0.35,        # % (10Y-2Y spread; ~slightly positive recently)
    "unemployment": 4.1,             # %
    "m2_liquidity": 21000.0,         # $B (M2SL ~ $21T)
    "industrial_production": 103.0,  # index
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


def _fetch_fred_csv(series_id: str, *, limit: int = 12) -> list[dict]:
    """FRED-MACRO: fetch a series via the NO-KEY public CSV (fredgraph.csv?id=<series>).
    Format: a header line ``observation_date,<SERIES_ID>`` then ``YYYY-MM-DD,<value>``
    rows (value ``.`` = missing). Returns the latest ``limit`` as [{date, value}]
    oldest→newest. Raises on any failure (caller fails open). No api_key needed."""
    resp = httpx.get(settings.fred_csv_base, params={"id": series_id}, timeout=FRED_TIMEOUT_S)
    resp.raise_for_status()
    text = resp.text or ""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or "," not in lines[0]:
        raise ValueError("unexpected FRED CSV body (no header)")
    out: list[dict] = []
    for ln in lines[1:]:  # skip header
        parts = ln.split(",")
        if len(parts) < 2:
            continue
        date, raw = parts[0].strip(), parts[1].strip()
        if raw in ("", "."):  # FRED uses "." for missing
            continue
        try:
            out.append({"date": date, "value": float(raw)})
        except (TypeError, ValueError):
            continue
    return out[-limit:]  # oldest→newest, last `limit`


# --------------------------------------------------------------------------- #
# FINANCE-ASSISTANT P1 (#52) — daily sentiment sources (free, no key).           #
# Each returns ``(value, source)``: a real number + 'live', or (None, 'mock')    #
# on any failure (fail-soft — the caller records what it can, warns on None).     #
# --------------------------------------------------------------------------- #
FNG_URL = "https://api.alternative.me/fng/"
COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"


def fetch_fear_greed() -> tuple[float | None, str]:
    """Crypto Fear & Greed index (0-100) from alternative.me (free, no key). Returns
    ``(value, 'live')`` or ``(None, 'mock')`` on any failure (fail-soft, never raises)."""
    try:
        resp = httpx.get(FNG_URL, params={"limit": "1"}, timeout=FRED_TIMEOUT_S)
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or []
        if data:
            return float(data[0]["value"]), "live"
    except Exception as exc:  # noqa: BLE001 — fail-soft
        logger.warning("fear_greed fetch failed: %s", exc)
    return None, "mock"


def fetch_btc_dominance() -> tuple[float | None, str]:
    """BTC market-cap dominance % from coingecko /global (free). Returns ``(value, 'live')``
    or ``(None, 'mock')`` on any failure (fail-soft, never raises)."""
    try:
        resp = httpx.get(COINGECKO_GLOBAL_URL, timeout=FRED_TIMEOUT_S)
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        btc = (data.get("market_cap_percentage") or {}).get("btc")
        if btc is not None:
            return float(btc), "live"
    except Exception as exc:  # noqa: BLE001 — fail-soft
        logger.warning("btc_dominance fetch failed: %s", exc)
    return None, "mock"


def fetch_latest(indicator: str) -> tuple[list[dict], str | None]:
    """Fetch recent observations for one indicator. Returns ``(points, warning)``:
    points are [{indicator, value, ts, source}] oldest→newest. PRIMARY path = the
    no-KEY public FRED CSV (Fed/CPI are REAL with no key); fail-soft to mock. Fail-open:
      - CSV ok                 → real points, source='fred', no warning
      - CSV empty/err          → mock points + "macro ... — mock" (e.g. DXY/DTWEXBGS,
                                 which the public CSV doesn't serve cleanly)
      - unknown indicator      → ([], "unknown macro indicator <ind>")
    NEVER raises. (The JSON API path with an api_key is retained as a secondary fallback
    if a key is configured AND the CSV failed — but the no-key CSV is the default real
    source, so most installs need no key.)"""
    series_id = settings.fred_series.get(indicator)
    if series_id is None:
        return [], f"unknown macro indicator {indicator!r}"

    # PRIMARY: no-key public CSV → real Fed/CPI without an api_key.
    # FINANCE-ASSISTANT P1 (#52): RETRY the CSV (up to FRED_CSV_RETRIES) before falling open —
    # some series (T10Y2Y) intermittently return HTTP-000/504, and a transient blip should not
    # demote a real indicator to mock. The retries are bounded + only on the exception path.
    last_exc: Exception | None = None
    for attempt in range(FRED_CSV_RETRIES):
        try:
            raw = _fetch_fred_csv(series_id)
            if raw:
                pts = [
                    {"indicator": indicator, "value": r["value"], "ts": r["date"], "source": "fred"}
                    for r in raw
                ]
                return pts, None
            # CSV reachable but no usable points (e.g. DTWEXBGS) → stop retrying, fall to mock.
            logger.info("FRED CSV for %s (%s) returned no usable points — mock", indicator, series_id)
            break
        except Exception as exc:  # noqa: BLE001 — retry, then keyed API / mock
            last_exc = exc
            logger.warning("FRED CSV fetch failed for %s (%s) attempt %d/%d: %s",
                           indicator, series_id, attempt + 1, FRED_CSV_RETRIES, exc)
    if last_exc is not None:
        # SECONDARY: if a key is configured, try the JSON API before giving up to mock.
        if settings.fred_api_key:
            try:
                raw = _fetch_fred_series(series_id)
                pts = [
                    {"indicator": indicator, "value": r["value"], "ts": r["date"], "source": "fred"}
                    for r in raw
                ]
                if pts:
                    return pts, None
            except Exception as exc2:  # noqa: BLE001 — fall through to mock
                logger.warning("FRED JSON API also failed for %s: %s", indicator, exc2)

    # FAIL-SOFT: honest mock, clearly tagged source='mock'.
    return _mock_points(indicator), f"macro mock for {indicator} (no real FRED data)"
