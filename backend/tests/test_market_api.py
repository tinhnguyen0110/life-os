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


@pytest.fixture(autouse=True)
def _clear_market_feed_cache():
    """CoinGecko TTL cache must be cold for every test — a cached feed from a prior
    test would serve instead of the current test's respx mock (causing false fails)."""
    from modules.market import reader
    reader._FEED_CACHE.clear()
    yield
    reader._FEED_CACHE.clear()


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


# --- GET /market/indicators/{symbol} (technical analysis) ---
def _seed_prices(asset: str, prices: list[float]) -> None:
    """Seed a price series (oldest→newest) into price_history for an asset, ending at
    NOW (so default time-windows like the indicator-alert eval's 720h catch them)."""
    from datetime import datetime, timedelta, timezone

    from store import db
    n = len(prices)
    base = datetime.now(timezone.utc) - timedelta(minutes=n)  # series ends ~now
    for i, p in enumerate(prices):
        db.record_price(asset, float(p), (base + timedelta(minutes=i)).isoformat())


def test_indicators_untracked_symbol_is_404(app_client):
    assert app_client.get("/market/indicators/NOTATRACKEDSYM").status_code == 404


def test_indicators_empty_series_is_200_with_warning(app_client):
    """Tracked asset, no series → 200, indicators empty/short-warned, never a 500."""
    resp = app_client.get("/market/indicators/BTC?indicators=rsi")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["points"] == 0
    assert "no price history" in (body.get("warning") or "")


def test_indicators_rsi_all_up_is_100_over_endpoint(app_client):
    """END-TO-END value: a strictly-rising seeded series → endpoint returns RSI 100."""
    _seed_prices("BTC", list(range(1, 40)))  # 39 rising points
    resp = app_client.get("/market/indicators/BTC?indicators=rsi&hours=100000")
    assert resp.status_code == 200
    ind = resp.json()["data"]["indicators"]
    assert ind["rsi"]["latest"] == 100.0  # math correctness through the real endpoint


def test_indicators_default_is_summary(app_client):
    _seed_prices("BTC", [100.0 + i for i in range(30)])
    body = app_client.get("/market/indicators/BTC?hours=100000").json()
    inds = body["data"]["indicators"]
    assert list(inds.keys()) == ["summary"]
    # summary is the NEUTRAL signal contract — no buy/sell advice
    assert inds["summary"]["signals_only"] is True
    assert "buy" not in str(inds).lower() and "sell" not in str(inds).lower()


def test_indicators_multiple_and_unknown_skipped(app_client):
    _seed_prices("BTC", [100.0 + (i % 5) for i in range(60)])
    body = app_client.get("/market/indicators/BTC?indicators=sma,ema,bogus&hours=100000").json()
    inds = body["data"]["indicators"]
    assert "sma" in inds and "ema" in inds
    assert "unknown indicator 'bogus'" in (body.get("warning") or "")


def test_indicators_full_attaches_series(app_client):
    _seed_prices("BTC", [100.0 + i for i in range(30)])
    body = app_client.get("/market/indicators/BTC?indicators=sma&full=true&hours=100000").json()
    sma = body["data"]["indicators"]["sma"]
    assert "series" in sma and len(sma["series"]) == 30


def test_indicators_atr_close_only_warns(app_client):
    """price_history is close-only → ATR runs in close-only mode + says so honestly."""
    _seed_prices("BTC", [100.0 + i for i in range(30)])
    body = app_client.get("/market/indicators/BTC?indicators=atr&hours=100000").json()
    atr = body["data"]["indicators"]["atr"]
    assert atr["latest"] is not None
    assert "close-only" in atr["warning"]


# --- GET /market/ohlc/{symbol} (candles derived from close-ticks) ---
def _seed_prices_at(asset: str, points: list[tuple[int, float]]) -> None:
    """Seed (minute_offset, price) points — lets a test place ticks into known buckets."""
    from datetime import datetime, timedelta, timezone

    from store import db
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for minute, price in points:
        db.record_price(asset, float(price), (base + timedelta(minutes=minute)).isoformat())


def test_ohlc_untracked_is_404(app_client):
    assert app_client.get("/market/ohlc/NOPE").status_code == 404


def test_ohlc_empty_series_200_with_warning(app_client):
    resp = app_client.get("/market/ohlc/BTC")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["candles"] == []
    assert "close-tick" in (body.get("warning") or "")  # honest about close-derived


def test_ohlc_buckets_ticks_into_candles_handcalc(app_client):
    """Two 60-min buckets: bucket0 ticks [10,14,8,12] → o10 h14 l8 c12;
    bucket1 ticks [20,18] → o20 h20 l18 c18. O/H/L/C are REAL observed closes."""
    _seed_prices_at("BTC", [
        (0, 10), (15, 14), (30, 8), (45, 12),  # bucket 0 (00:00–00:59)
        (60, 20), (75, 18),                     # bucket 1 (01:00–01:59)
    ])
    body = app_client.get("/market/ohlc/BTC?hours=100000&interval=60").json()
    candles = body["data"]["candles"]
    assert len(candles) == 2
    b0, b1 = candles
    assert (b0["open"], b0["high"], b0["low"], b0["close"], b0["ticks"]) == (10, 14, 8, 12, 4)
    assert (b1["open"], b1["high"], b1["low"], b1["close"], b1["ticks"]) == (20, 20, 18, 18, 2)
    # OHLC invariant holds for every bar.
    for b in candles:
        assert b["high"] >= max(b["open"], b["close"]) and b["low"] <= min(b["open"], b["close"])
    assert "close-tick" in (body.get("warning") or "")  # always honest


def test_ohlc_single_tick_bucket_is_degenerate(app_client):
    """A bucket with one observation → o==h==l==c, ticks=1 (honest, not fabricated)."""
    _seed_prices_at("BTC", [(0, 100)])
    candles = app_client.get("/market/ohlc/BTC?hours=100000&interval=60").json()["data"]["candles"]
    assert len(candles) == 1
    c = candles[0]
    assert c["open"] == c["high"] == c["low"] == c["close"] == 100 and c["ticks"] == 1


# --- indicator alerts (TA-condition rules) ---
def test_indicator_alert_create_list_delete(app_client):
    # create an RSI rule
    r = app_client.post("/market/indicator-alerts",
                        json={"symbol": "BTC", "kind": "rsi_below", "value": 30, "period": 14})
    assert r.status_code == 200
    rule = r.json()["data"]
    assert rule["kind"] == "rsi_below" and rule["value"] == 30 and rule["id"]
    # list shows it
    listed = app_client.get("/market/indicator-alerts").json()["data"]
    assert any(x["id"] == rule["id"] for x in listed["rules"])
    # delete it
    d = app_client.delete(f"/market/indicator-alerts/{rule['id']}")
    assert d.status_code == 200
    assert app_client.get("/market/indicator-alerts").json()["data"]["rules"] == []


def test_indicator_alert_untracked_symbol_404(app_client):
    r = app_client.post("/market/indicator-alerts",
                        json={"symbol": "NOPE", "kind": "rsi_above", "value": 70})
    assert r.status_code == 404


def test_indicator_alert_delete_unknown_404(app_client):
    assert app_client.delete("/market/indicator-alerts/nope-1").status_code == 404


def test_indicator_alert_rsi_below_FIRES_on_downtrend(app_client):
    """END-TO-END: a strictly-falling series → RSI 0 ≤ 30 → the rule fires, with detail."""
    _seed_prices("BTC", list(range(40, 1, -1)))  # 39 falling points → RSI 0
    app_client.post("/market/indicator-alerts",
                    json={"symbol": "BTC", "kind": "rsi_below", "value": 30, "period": 14})
    triggers = app_client.get("/market/indicator-alerts").json()["data"]["triggers"]
    rsi_trig = next(t for t in triggers if t["kind"] == "rsi_below")
    assert rsi_trig["fired"] is True
    assert "RSI" in rsi_trig["detail"]


def test_indicator_alert_rsi_below_does_NOT_fire_on_uptrend(app_client):
    """Distinguishing: a RISING series → RSI 100 > 30 → the SAME rule does NOT fire."""
    _seed_prices("BTC", list(range(1, 40)))  # rising → RSI 100
    app_client.post("/market/indicator-alerts",
                    json={"symbol": "BTC", "kind": "rsi_below", "value": 30, "period": 14})
    triggers = app_client.get("/market/indicator-alerts").json()["data"]["triggers"]
    rsi_trig = next(t for t in triggers if t["kind"] == "rsi_below")
    assert rsi_trig["fired"] is False


def test_indicator_alert_upsert_by_symbol_kind_period(app_client):
    """Re-creating the same (symbol,kind,period) UPDATES (keeps id), not duplicates."""
    r1 = app_client.post("/market/indicator-alerts",
                         json={"symbol": "BTC", "kind": "rsi_below", "value": 30, "period": 14}).json()["data"]
    r2 = app_client.post("/market/indicator-alerts",
                         json={"symbol": "BTC", "kind": "rsi_below", "value": 25, "period": 14}).json()["data"]
    assert r1["id"] == r2["id"] and r2["value"] == 25  # updated in place
    rules = app_client.get("/market/indicator-alerts").json()["data"]["rules"]
    assert len([x for x in rules if x["kind"] == "rsi_below"]) == 1


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
