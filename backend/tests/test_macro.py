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
def macro_db(isolated_paths):
    store.init_macro_tables()
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
def test_fetch_no_key_returns_mock(macro_db, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "")
    points, warning = reader.fetch_latest("fed_funds_rate")
    assert points, "mock must return points even with no key"
    assert all(p["source"] == "mock" for p in points)
    assert warning and "mock" in warning.lower()


def test_fetch_unknown_indicator(macro_db):
    points, warning = reader.fetch_latest("not-a-real-indicator")
    assert points == []
    assert warning and "unknown" in warning.lower()


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
    # cold start auto-refreshed → each has data + a descriptive trend
    for v in overview.indicators:
        assert v.latest is not None
        assert v.trend in ("up", "down", "flat")
        assert v.points >= 1


def test_overview_mock_is_honest(macro_db, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "")  # no key → mock
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
# Refresh persists                                                             #
# --------------------------------------------------------------------------- #
def test_refresh_persists_points(macro_db):
    written, warnings = service.refresh()
    assert written > 0
    # every tracked indicator now has stored points
    for ind in service.tracked_indicators():
        assert store.count(ind) > 0
