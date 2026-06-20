"""tests/test_macro.py — Macro module tests (MACRO-1).

Coverage:
  - overview: every tracked indicator present, latest + DESCRIPTIVE trend, honest mock
    + warning when no FRED key (fail-open, never crash).
  - NEUTRAL: no forecast language/fields leak — the module describes, never predicts.
  - trend logic: up/down/flat derived from latest vs prior (descriptive only).
  - history: time-series for an indicator; unknown indicator → None (404 at router).
  - store: record_point upserts (re-recording same (indicator, ts) does NOT duplicate).
  - fail-open: no FRED key → mock points tagged source='mock'; fetch errors → mock.
  - router: GET /macro/overview + /macro/history envelopes; unknown indicator → 404.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.macro import reader, service, store


@pytest.fixture
def macro_db(isolated_paths, monkeypatch):
    store.init_macro_tables()
    # FRED-MACRO: the no-key CSV is now the PRIMARY path → cold-start refresh would hit
    # the live network. Neutralize it by default (CSV fails → deterministic mock), so the
    # suite stays hermetic. Tests that exercise the real CSV path override reader.httpx.get.
    def _no_network(*a, **k):
        raise RuntimeError("network disabled in tests (default macro_db)")
    monkeypatch.setattr(reader.httpx, "get", _no_network)
    return isolated_paths


@pytest.fixture
def client(macro_db):
    from modules.macro.router import router

    app = FastAPI()
    app.include_router(router, prefix="/macro")
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Store — upsert (no duplication)                                               #
# --------------------------------------------------------------------------- #
def test_record_point_upserts_same_ts(macro_db):
    store.record_point("cpi", 300.0, "2026-01-01", "fred")
    store.record_point("cpi", 305.0, "2026-01-01", "fred")  # same (indicator, ts)
    assert store.count("cpi") == 1, "same (indicator, ts) must upsert, not duplicate"
    assert float(store.latest("cpi")["value"]) == 305.0  # updated to the new value


def test_history_oldest_to_newest(macro_db):
    store.record_point("dxy", 100.0, "2026-01-01", "fred")
    store.record_point("dxy", 101.0, "2026-02-01", "fred")
    rows = store.history("dxy")
    assert [r["ts"] for r in rows] == ["2026-01-01", "2026-02-01"]


# --------------------------------------------------------------------------- #
# Fail-open fetch — no FRED key → mock                                          #
# --------------------------------------------------------------------------- #
def _csv_fails(monkeypatch):
    """Make the no-key CSV path fail (so fetch falls through to mock)."""
    def boom(*a, **k):
        raise RuntimeError("network down")
    monkeypatch.setattr(reader.httpx, "get", boom)


def test_fetch_csv_failure_returns_mock(macro_db, monkeypatch):
    """FRED-MACRO: when the no-key CSV is UNREACHABLE → fail-soft to mock (no key set)."""
    from core.config import settings
    monkeypatch.setattr(settings, "fred_api_key", "")
    _csv_fails(monkeypatch)
    points, warning = reader.fetch_latest("fed_funds_rate")
    assert points, "mock must return points even when the CSV fails"
    assert all(p["source"] == "mock" for p in points)
    assert warning and "mock" in warning.lower()


def test_fetch_unknown_indicator(macro_db):
    points, warning = reader.fetch_latest("not-a-real-indicator")
    assert points == []
    assert warning and "unknown" in warning.lower()


# --------------------------------------------------------------------------- #
# FRED-MACRO distinguishing cases: real CSV → source='fred' (not mock); DXY     #
# empty → mock; fail-soft never 500s.                                           #
# --------------------------------------------------------------------------- #
class _FakeResp:
    def __init__(self, text):
        self.text = text
    def raise_for_status(self):
        pass


def _mock_csv(monkeypatch, body):
    monkeypatch.setattr(reader.httpx, "get", lambda *a, **k: _FakeResp(body))


def test_d_real_csv_is_fred_not_mock(macro_db, monkeypatch):
    """DISTINGUISHING: a real CSV payload → points tagged source='fred' with the REAL
    values (NOT the mock baseline), no warning. Proves the no-key CSV is the real path."""
    _mock_csv(monkeypatch,
              "observation_date,FEDFUNDS\n2026-03-01,3.64\n2026-04-01,3.64\n2026-05-01,3.63\n")
    points, warning = reader.fetch_latest("fed_funds_rate")
    assert points and all(p["source"] == "fred" for p in points)   # REAL, not mock
    assert warning is None
    assert points[-1]["value"] == 3.63 and points[-1]["ts"] == "2026-05-01"
    # the real value differs from the mock baseline (proves it's not the deterministic mock)
    assert points[-1]["value"] != reader._MOCK_BASE.get("fed_funds_rate")


def test_d_dxy_is_feedless_mock_not_fred(macro_db, monkeypatch):
    """DXY-HONEST (#15 corrective): dxy is FEED-LESS (no fred_series entry — FRED's DTWEXBGS is a
    DIFFERENT instrument from the ICE DXY index; mapping it would mislabel). So fetch_latest('dxy')
    takes the feed-less path → honest mock (source='mock', NEVER 'fred') + a clear 'no live feed'
    warning. Even if a CSV were served, dxy has no series_id to fetch. NEVER presents a proxy as DXY."""
    points, warning = reader.fetch_latest("dxy")
    assert points and all(p["source"] == "mock" for p in points), "dxy must read source='mock', never 'fred'"
    assert warning and "no live dxy feed" in warning.lower(), f"honest feed-less warning expected, got {warning!r}"


def test_d_fail_soft_never_raises(macro_db, monkeypatch):
    """fail-soft: a CSV that 504s / garbage body → mock, NEVER raises (no 500 to caller)."""
    def boom(*a, **k):
        raise RuntimeError("504 gateway timeout")
    monkeypatch.setattr(reader.httpx, "get", boom)
    # must not raise:
    points, warning = reader.fetch_latest("cpi")
    assert points and all(p["source"] == "mock" for p in points)
    assert warning and "mock" in warning.lower()


def test_fetch_network_error_falls_open_to_mock(macro_db, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "fake-key")  # force the fetch path

    def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(reader.httpx, "get", boom)
    points, warning = reader.fetch_latest("cpi")
    assert points and all(p["source"] == "mock" for p in points)
    assert warning and "mock" in warning.lower()


# --------------------------------------------------------------------------- #
# Trend logic — descriptive direction (NOT forecast)                            #
# --------------------------------------------------------------------------- #
def test_trend_up_down_flat(macro_db):
    assert service._trend(5.0, 4.0) == "up"
    assert service._trend(4.0, 5.0) == "down"
    assert service._trend(5.0, 5.0) == "flat"
    assert service._trend(5.0, None) == "flat"   # <2 points → flat
    assert service._trend(None, None) == "flat"


# --------------------------------------------------------------------------- #
# Overview — shape, mock fail-open, neutral                                     #
# --------------------------------------------------------------------------- #
def test_overview_has_all_tracked_indicators(macro_db):
    overview, warnings = service.get_overview()
    got = {v.indicator for v in overview.indicators}
    assert got == set(service.tracked_indicators())
    # cold start (network off → all mock) STILL returns DISPLAY numbers + a descriptive trend.
    # DXY-REAL (#15): mock is no longer PERSISTED (record_point skips it), so points==0 here —
    # the numbers come from service._indicator_view's reader display-fallback, not the store. The
    # contract is "empty-series path still returns numbers", NOT "mock is persisted".
    for v in overview.indicators:
        assert v.latest is not None, f"{v.indicator}: cold-start must still show a display number"
        assert v.trend in ("up", "down", "flat")
        assert v.points == 0, f"{v.indicator}: mock must NOT be persisted (display-only), got points={v.points}"
        assert v.source == "mock", "network off → display values are honestly tagged mock"


def test_overview_mock_is_honest(macro_db, monkeypatch):
    """When the real source is unreachable → overview is honestly tagged source='mock'."""
    from core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "")
    _csv_fails(monkeypatch)                     # CSV down → fall-soft to mock
    overview, warnings = service.get_overview()
    assert overview.source == "mock"
    assert any("mock" in w.lower() for w in warnings), "must flag mock data honestly"
    assert all(v.source == "mock" for v in overview.indicators)


def test_overview_is_neutral_no_forecast(macro_db):
    """The macro view must DESCRIBE, never PREDICT — no forecast term leaks into the
    payload (the module reports observed data; the agent reasons)."""
    overview, _ = service.get_overview()
    flat = json.dumps(overview.model_dump()).lower()
    for banned in ("forecast", "will cut", "will rise", "predict", "expect", "outlook",
                   "recommend", "should buy", "should sell"):
        assert banned not in flat, f"macro overview leaked a forecast/advice term: {banned}"


def test_overview_change_matches_latest_minus_previous(macro_db):
    # Seed ALL tracked indicators so no cold-start auto-refresh fires (refresh fetches
    # every indicator, which would add mock points dated today and supersede the seed).
    for ind in service.tracked_indicators():
        store.record_point(ind, 100.0, "2026-01-01", "fred")
    store.record_point("cpi", 300.0, "2026-05-01", "fred")
    store.record_point("cpi", 312.0, "2026-06-01", "fred")  # latest for cpi
    overview, _ = service.get_overview()
    cpi = next(v for v in overview.indicators if v.indicator == "cpi")
    assert cpi.latest == 312.0
    assert cpi.previous == 300.0
    assert cpi.change == 12.0
    assert cpi.trend == "up"


# --------------------------------------------------------------------------- #
# History service                                                              #
# --------------------------------------------------------------------------- #
def test_get_history_unknown_indicator_is_none(macro_db):
    assert service.get_history("not-tracked") is None


def test_get_history_returns_points(macro_db):
    store.record_point("dxy", 120.0, "2026-05-01", "fred")
    hist = service.get_history("dxy", days=3650)
    assert hist is not None and hist.indicator == "dxy"
    assert any(p.value == 120.0 for p in hist.points)


# --------------------------------------------------------------------------- #
# Router endpoints                                                             #
# --------------------------------------------------------------------------- #
def test_endpoint_overview(client):
    resp = client.get("/macro/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]["indicators"]) == len(service.tracked_indicators())


def test_endpoint_history(client):
    resp = client.get("/macro/history", params={"indicator": "cpi", "days": 400})
    assert resp.status_code == 200
    assert resp.json()["data"]["indicator"] == "cpi"


def test_endpoint_history_unknown_404(client):
    resp = client.get("/macro/history", params={"indicator": "NOPE"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Refresh persists — REAL points only (DXY-REAL #15: mock is never persisted)    #
# --------------------------------------------------------------------------- #
def test_refresh_persists_real_points(macro_db, monkeypatch):
    """With a REAL CSV payload, refresh() persists fred points for every FRED-BACKED indicator.
    DXY-REAL (#15): refresh only persists REAL data now — so this FEEDS a real CSV. DXY-HONEST
    (#15 corrective): the FEED-LESS indicators (dxy) get mock from refresh → NOT persisted → 0
    rows (honest — no live DXY feed); so scope the per-indicator assertion to the FRED-backed
    set, and assert the feed-less ones persist nothing."""
    from core.config import settings
    _mock_csv(monkeypatch,
              "observation_date,X\n2026-03-01,3.64\n2026-04-01,3.65\n2026-05-01,3.66\n")
    written, warnings = service.refresh()
    assert written > 0
    # every FRED-BACKED indicator now has stored REAL points
    for ind in settings.fred_series:
        assert store.count(ind) > 0, f"FRED-backed {ind} must persist real points"
    # the feed-less indicators (dxy) persist NOTHING (mock, not stored) — honestly feed-less
    for ind in service._FEEDLESS_INDICATORS:
        assert store.count(ind) == 0, f"feed-less {ind} must NOT persist (mock only)"
    # and the persisted source is all real ('fred'), zero mock
    assert store.count_by_source("mock") == 0, "no mock row may be persisted by refresh"
    assert store.count_by_source("fred") > 0


# =========================================================================== #
# DXY-REAL (#15) — mock is NEVER persisted into macro_history (+ one-shot purge) #
# =========================================================================== #
# THE BUG: refresh() persisted source='mock' rows with a today-ts that SHADOW the real
# (naturally-lagged) FRED row → get_overview reads newest-first → returns the frozen mock; a
# fresh refresh can't dislodge it (real ts < frozen mock ts). Extends the LOCKED S1 "mock =
# absence of real data, never counts" rule to the WRITE path.

# --- (a) record_point skips a mock-sourced point (no row written) ---
def test_DXY_record_point_skips_mock(macro_db):
    """record_point('...','mock') writes NOTHING — the single chokepoint that makes mock
    un-persistable across ALL callers (refresh + snapshot)."""
    store.record_point("dxy", 100.0, "2026-06-16", "mock")
    assert store.count("dxy") == 0, "a mock point must not be persisted"
    assert store.latest("dxy") is None
    # a real point IS persisted (the guard is mock-only, not a blanket block)
    store.record_point("dxy", 119.5, "2026-06-12", "fred")
    assert store.count("dxy") == 1 and store.latest("dxy")["source"] == "fred"


def test_DXY_record_point_mock_cannot_shadow_real(macro_db):
    """The exact bug shape: a real (lagged) row exists; a later mock row with a NEWER ts is
    offered → it must NOT persist, so get_overview's newest-first read still returns the REAL
    row (not a frozen mock). This is the shadowing the fix prevents."""
    store.record_point("dxy", 119.5, "2026-06-12", "fred")     # real, lagged ts
    store.record_point("dxy", 100.0, "2026-06-16", "mock")     # newer ts, mock → must be skipped
    rows = store.recent("dxy", limit=2)
    assert len(rows) == 1, "the mock row must not have been written"
    assert rows[0]["source"] == "fred" and rows[0]["value"] == 119.5, "the REAL row still wins"


# --- (b) FORCE-FRED-FAIL distinguishing: a fetch failure persists NO new mock row,
#         and the prior REAL point still surfaces in get_overview (THE durable-root spine) ---
def test_DXY_GATEb_fred_failure_persists_no_mock_real_survives(macro_db, monkeypatch):
    """THE SPINE (a 'just purge once' fix FAILS this): seed a REAL dxy point, then make the FRED
    fetch FAIL (network off via macro_db → fetch_latest returns mock). A refresh persists NO new
    mock row; get_overview still surfaces the prior REAL point (source='fred'), NOT a frozen mock
    with a today-ts. This is what makes the fix durable across every future outage."""
    # seed a real point (macro_db disables network, so do it directly via the store)
    store.record_point("dxy", 119.5, "2026-06-12", "fred")
    assert store.count("dxy") == 1

    # refresh while FRED is down (macro_db's _no_network → fetch_latest falls open to mock)
    written, warnings = service.refresh()
    # no NEW mock row landed for dxy — count is still exactly the one real row
    assert store.count("dxy") == 1, "a failed FRED fetch must persist NO new mock row"
    assert store.count_by_source("mock") == 0, "no mock row may exist after a failed refresh"

    # get_overview surfaces the REAL point (not a frozen mock with today's ts)
    overview, _ = service.get_overview()
    dxy = next(v for v in overview.indicators if v.indicator == "dxy")
    assert dxy.source == "fred", "the prior REAL point must still surface, not a frozen mock"
    assert dxy.value == 119.5 if hasattr(dxy, "value") else dxy.latest == 119.5
    assert dxy.asOf == "2026-06-12", "asOf is the real point's ts, not a today-stamped mock"


# --- (c) purge_mock deletes ONLY mock rows; real count unchanged; idempotent ---
def test_DXY_purge_mock_deletes_only_mock(macro_db):
    """purge_mock removes every source='mock' row and leaves real rows untouched (the live-store
    guard); returns the count; idempotent (re-run → 0)."""
    # seed real rows (via the guard-respecting path) + stuck mock rows (direct insert to bypass
    # the new guard, simulating the historical pollution this purge cleans).
    store.record_point("cpi", 300.0, "2026-06-01", "fred")
    store.record_point("dxy", 119.5, "2026-06-12", "fred")
    conn = store.db.get_conn()
    conn.execute("INSERT INTO macro_history(indicator,value,ts,source) VALUES('dxy',100.0,'2026-06-16','mock')")
    conn.execute("INSERT INTO macro_history(indicator,value,ts,source) VALUES('cpi',1.0,'2026-06-15','mock')")
    conn.commit()

    before_real = store.count_by_source("fred")
    before_mock = store.count_by_source("mock")
    assert before_real == 2 and before_mock == 2

    purged = store.purge_mock()
    assert purged == 2, f"must purge exactly the 2 mock rows, got {purged}"
    assert store.count_by_source("fred") == before_real, "REAL row count must be UNCHANGED"
    assert store.count_by_source("mock") == 0, "all mock rows gone"
    # the real rows are intact + readable
    assert store.latest("cpi")["value"] == 300.0 and store.latest("dxy")["value"] == 119.5
    # idempotent: a re-run on a clean store deletes 0
    assert store.purge_mock() == 0, "purge must be idempotent (clean store → 0)"


# --- (d) cold-start (empty series) still returns DISPLAY numbers (mock-tagged, NOT persisted) ---
def test_DXY_GATEd_cold_start_still_returns_numbers(macro_db):
    """An UNPRIMED install (empty store, network off → all mock): get_overview still returns
    display numbers for each indicator (the reader display-fallback) — but persists NOTHING
    (points==0). The 'empty-series path still returns numbers' contract survives the no-persist
    guard."""
    # store is empty (macro_db just created the table); network is off → fetch_latest → mock
    assert store.count("dxy") == 0
    overview, warnings = service.get_overview()
    dxy = next(v for v in overview.indicators if v.indicator == "dxy")
    assert dxy.latest is not None, "cold-start must still show a display number"
    assert dxy.source == "mock", "honestly tagged mock"
    assert dxy.points == 0, "display-only — nothing persisted"
    # and nothing leaked into the store
    assert store.count("dxy") == 0, "the display-fallback must NOT persist"
    assert store.count_by_source("mock") == 0, "no mock row anywhere in the store"


# =========================================================================== #
# DXY-HONEST (#15 corrective) — dxy is feed-less mock, NEVER a mislabeled FRED  #
# proxy. FRED's DTWEXBGS (broad trade-weighted dollar) ≠ the ICE DXY index.     #
# =========================================================================== #
def test_DXYHONEST_dxy_not_in_fred_series():
    """The config no longer maps dxy → DTWEXBGS (the honest-mirror breach). dxy is feed-less."""
    from core.config import settings
    assert "dxy" not in settings.fred_series, "dxy must NOT be a FRED series (DTWEXBGS ≠ ICE DXY)"
    # but it's still TRACKED + displayed (feed-less), so it doesn't vanish
    assert "dxy" in service.tracked_indicators(), "dxy must still be tracked (feed-less, not dropped)"
    assert "dxy" in service._FEEDLESS_INDICATORS


def test_DXYHONEST_dxy_overview_is_mock_with_warning(macro_db):
    """TEETH (T1b — the test now asserts what its NAME claims): in the overview dxy reads
    source='mock' (NEVER 'fred') AND carries a NON-EMPTY honest warning surfaced WHERE THE AGENT
    READS (the view, not just the dropped reader return). The warning is FEED-LESS-SPECIFIC: a
    REAL indicator (cpi) on the SAME overview has warning=None — proving it's not a blanket label.
    (network off → cpi is mock-by-outage, but its `warning` field stays None because warning is
    feed-less-specific, NOT source-specific — the distinguishing.)"""
    overview, warnings = service.get_overview()
    dxy = next(v for v in overview.indicators if v.indicator == "dxy")
    assert dxy.source == "mock", "dxy must be source='mock', never a mislabeled 'fred' proxy"
    assert dxy.latest is not None, "dxy still shows a (mock) display number — doesn't vanish"
    # TEETH: the honest warning IS surfaced on the view (was dropped before T1b)
    assert dxy.warning is not None and dxy.warning != "", "dxy must carry an honest warning on the view"
    low = dxy.warning.lower()
    assert ("no live" in low and "feed" in low) or "dxy" in low, \
        f"the warning must name the feed-less reality, got {dxy.warning!r}"
    # DISTINGUISHING: the warning is feed-less-SPECIFIC, not blanket — a REAL indicator is None.
    cpi = next(v for v in overview.indicators if v.indicator == "cpi")
    assert cpi.warning is None, (
        f"a real (FRED-backed) indicator must have warning=None — feed-less-specific, not "
        f"blanket; cpi.warning={cpi.warning!r}")


def test_DXYHONEST_dxy_fetch_warning_is_honest(macro_db):
    """The reader warning for dxy names the feed-less reality (no live DXY feed / dedicated API),
    not a generic 'fetch failed' — so the user knows it's PARKED, not broken."""
    points, warning = reader.fetch_latest("dxy")
    assert warning is not None and "no live dxy feed" in warning.lower()
    assert all(p["source"] == "mock" for p in points)
