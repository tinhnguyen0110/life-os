"""tests/test_market_api.py — Market router + routine integration (S3 T2/T3).

Drives the real app via TestClient with market auto-mounted. CoinGecko is mocked
(respx) — never real. Covers all endpoints, envelope, status codes, /health
discovery of the market-poll routine, and the poll persist+alert path.
"""

from __future__ import annotations

import importlib

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

CG_URL = "https://api.coingecko.com/api/v3/simple/price"
ASSETS = [
    {"symbol": "BTC", "name": "Bitcoin", "assetClass": "crypto", "cgId": "bitcoin"},
    {"symbol": "FUEVFVND", "name": "ETF VFVND", "assetClass": "etf", "mock": 24.8},
]


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(settings, "market_assets", ASSETS)
    # Reset the module-level DB_PATH override so settings.db_path takes effect
    # (init_db(path) elsewhere leaks it; without this a prior test's DB bleeds in).
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as main_mod

    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


# --- discovery ---
def test_health_lists_market_module(app_client):
    body = app_client.get("/health").json()
    assert "market" in body["data"]["modules"]


def test_health_lists_market_poll_routine(app_client):
    body = app_client.get("/health").json()
    assert "market-poll" in body["data"]["routines"]


def test_health_no_skipped_modules(app_client):
    body = app_client.get("/health").json()
    assert not body.get("warning"), f"module skipped: {body.get('warning')}"


# --- GET /market ---
@respx.mock
def test_get_market_envelope(app_client):
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 60000.0, "usd_24h_change": 1.5}}))
    body = app_client.get("/market").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) == {"quotes", "triggers", "macro", "alertHistory"}
    syms = {q["symbol"] for q in d["quotes"]}
    assert {"BTC", "FUEVFVND"} <= syms


@respx.mock
def test_get_market_fail_open_still_200(app_client):
    # CoinGecko down → endpoint must still 200 with a warning, not 500.
    respx.get(CG_URL).mock(side_effect=httpx.TimeoutException("down"))
    resp = app_client.get("/market")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body.get("warning")  # surfaced the degradation


# --- GET /market/history/{asset} ---
def test_history_empty_tracked_asset_is_200_empty(app_client):
    """Tracked asset, no series yet → 200 + {points: []} (empty is valid, not 404)."""
    resp = app_client.get("/market/history/BTC")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True and body["data"]["points"] == []


def test_history_untracked_symbol_is_404(app_client):
    """A symbol NOT in the tracked universe is a true 404 (teeth)."""
    assert app_client.get("/market/history/NOTATRACKEDSYM").status_code == 404


@respx.mock
def test_history_after_poll(app_client):
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 60000.0, "usd_24h_change": 0.0}}))
    from modules.market import router as market_router
    market_router.market_poll()
    body = app_client.get("/market/history/BTC").json()
    assert body["success"] is True
    pts = body["data"]["points"]
    assert len(pts) >= 1 and pts[0]["asset"] == "BTC"


def test_history_hours_param(app_client):
    # endpoint accepts ?hours= ; tracked asset → 200 even with empty series
    resp = app_client.get("/market/history/BTC?hours=48")
    assert resp.status_code == 200
    assert resp.json()["data"]["points"] == []


# --- alert rules CRUD (id-based) ---
def test_alert_set_list_delete(app_client):
    # set → returns the created rule with a server id
    r = app_client.post("/market/alerts", json={"symbol": "BTC", "op": "above", "threshold": 70000})
    assert r.status_code == 200 and r.json()["success"] is True
    rule_id = r.json()["data"]["id"]
    assert rule_id
    # list
    rules = app_client.get("/market/alerts").json()["data"]
    assert any(x["id"] == rule_id and x["symbol"] == "BTC" for x in rules)
    # delete by id
    d = app_client.delete(f"/market/alerts/{rule_id}")
    assert d.status_code == 200
    assert app_client.get("/market/alerts").json()["data"] == []


def test_alert_delete_404(app_client):
    assert app_client.delete("/market/alerts/nope-9").status_code == 404


def test_alert_set_422_bad_body(app_client):
    # threshold must be > 0
    assert app_client.post("/market/alerts", json={"symbol": "BTC", "op": "above", "threshold": -5}).status_code == 422
    # op must be above|below
    assert app_client.post("/market/alerts", json={"symbol": "BTC", "op": "sideways", "threshold": 5}).status_code == 422


# --- routine poll path ---
@respx.mock
def test_poll_persists_and_records_alert(app_client):
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 75000.0, "usd_24h_change": 0.0}}))
    # rule that the 75000 price will hit
    app_client.post("/market/alerts", json={"symbol": "BTC", "op": "above", "threshold": 70000})
    from modules.market import router as market_router
    market_router.market_poll()
    # price persisted
    assert app_client.get("/market/history/BTC").json()["data"]
    # alert recorded in history
    hist = app_client.get("/market").json()["data"]["alertHistory"]
    assert any(e["symbol"] == "BTC" and e["price"] == 75000.0 for e in hist)


@respx.mock
def test_poll_edge_trigger_no_duplicate(app_client):
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 75000.0, "usd_24h_change": 0.0}}))
    app_client.post("/market/alerts", json={"symbol": "BTC", "op": "above", "threshold": 70000})
    from modules.market import router as market_router
    market_router.market_poll()
    market_router.market_poll()  # second poll, same standing hit
    hist = app_client.get("/market").json()["data"]["alertHistory"]
    btc_hits = [e for e in hist if e["symbol"] == "BTC"]
    assert len(btc_hits) == 1, f"edge-trigger must not duplicate a standing hit, got {len(btc_hits)}"
