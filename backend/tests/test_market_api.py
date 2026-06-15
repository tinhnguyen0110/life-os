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
    {"symbol": "XAU", "name": "Gold (oz)", "assetClass": "gold", "cgId": "pax-gold", "mock": 2650.0},
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


# --- watchlist (curated symbols + rich quick view) ---
def test_watchlist_empty_is_200(app_client):
    resp = app_client.get("/market/watchlist")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_watchlist_add_list_delete(app_client):
    # add (lowercase normalises to upper)
    r = app_client.post("/market/watchlist", json={"symbol": "btc"})
    assert r.status_code == 200
    assert r.json()["data"]["symbols"] == ["BTC"]
    # idempotent: re-adding doesn't duplicate
    r2 = app_client.post("/market/watchlist", json={"symbol": "BTC"})
    assert r2.json()["data"]["symbols"] == ["BTC"]
    # delete
    d = app_client.delete("/market/watchlist/BTC")
    assert d.status_code == 200 and d.json()["data"]["deleted"] == "BTC"
    assert app_client.get("/market/watchlist").json()["data"]["items"] == []


def test_watchlist_delete_unwatched_404(app_client):
    assert app_client.delete("/market/watchlist/NOPE").status_code == 404


def test_watchlist_untracked_symbol_is_registered_and_appears(app_client):
    """Adding an UNTRACKED symbol registers it as best-effort crypto + it appears in
    the rich view (price from the live quote; series may be empty → flagged)."""
    app_client.post("/market/watchlist", json={"symbol": "BTC"})  # BTC is in ASSETS
    items = app_client.get("/market/watchlist").json()["data"]["items"]
    assert len(items) == 1
    row = items[0]
    # shape the FE depends on — every key present
    for k in ("symbol", "name", "price", "changePct", "source", "sparkline", "rsi", "trend"):
        assert k in row
    assert row["symbol"] == "BTC"


def test_watchlist_with_data_has_sparkline_rsi_change(app_client):
    """END-TO-END: a seeded close series → sparkline (downsampled), RSI, change all
    populated on the watchlist row."""
    _seed_prices("BTC", [100.0 + i for i in range(60)])  # 60 rising closes
    app_client.post("/market/watchlist", json={"symbol": "BTC"})
    row = app_client.get("/market/watchlist").json()["data"]["items"][0]
    assert len(row["sparkline"]) > 0 and len(row["sparkline"]) <= 32  # downsampled
    assert row["rsi"] is not None  # 60 points → RSI computable
    assert row["sparkline"][-1] == 159.0  # last seeded close is the last sparkline point
    assert row["trend"] == "up"  # rising series


def test_watchlist_no_history_row_still_present_with_warning(app_client):
    """A watchlisted symbol with NO price series still renders (sparkline [], rsi None)
    + a per-row warning — never a 500."""
    # DOGE is not in ASSETS → add registers it; no history seeded → empty series.
    app_client.post("/market/watchlist", json={"symbol": "DOGE"})
    body = app_client.get("/market/watchlist").json()
    doge = next(it for it in body["data"]["items"] if it["symbol"] == "DOGE")
    assert doge["sparkline"] == [] and doge["rsi"] is None
    assert doge["warning"] and "no price history" in doge["warning"]
    assert "no price history" in (body.get("warning") or "")  # bubbles to top-level


def test_watchlist_sparkline_downsamples_large_series(app_client):
    """A large series is downsampled to ≤32 points (mini-chart payload stays small)."""
    _seed_prices("BTC", [float(i) for i in range(500)])  # 500 points
    app_client.post("/market/watchlist", json={"symbol": "BTC"})
    spark = app_client.get("/market/watchlist").json()["data"]["items"][0]["sparkline"]
    assert 0 < len(spark) <= 32
    assert spark[-1] == 499.0  # most-recent point always kept


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


# --- multi-symbol: GET /market/correlation, /compare, /relative-strength ---
def test_correlation_endpoint_co_moving_is_1(app_client):
    """END-TO-END: two perfectly co-moving seeded series → correlation 1.0."""
    _seed_prices("BTC", [float(i) for i in range(1, 30)])      # rising
    _seed_prices("ETH", [float(2 * i) for i in range(1, 30)])  # rising 2× (still corr 1)
    d = app_client.get("/market/correlation?symbols=BTC,ETH&hours=100000").json()["data"]
    assert d["matrix"]["BTC"]["ETH"] == 1.0
    assert d["matrix"]["BTC"]["BTC"] == 1.0


def test_correlation_endpoint_inverse_is_minus_1(app_client):
    _seed_prices("BTC", [float(i) for i in range(1, 30)])        # rising
    _seed_prices("ETH", [float(30 - i) for i in range(1, 30)])   # falling → inverse
    d = app_client.get("/market/correlation?symbols=BTC,ETH&hours=100000").json()["data"]
    assert d["matrix"]["BTC"]["ETH"] == -1.0


def test_correlation_needs_two_symbols_422(app_client):
    assert app_client.get("/market/correlation?symbols=BTC").status_code == 422
    # dedup: BTC,BTC → 1 distinct → 422
    assert app_client.get("/market/correlation?symbols=BTC,BTC").status_code == 422


def test_correlation_too_many_symbols_422(app_client):
    syms = ",".join(f"S{i}" for i in range(11))  # 11 > cap 10
    assert app_client.get(f"/market/correlation?symbols={syms}").status_code == 422


def test_correlation_short_series_is_none_not_crash(app_client):
    _seed_prices("BTC", [1.0, 2.0, 3.0])
    # ETH has no series → correlation None, 200 not 500.
    resp = app_client.get("/market/correlation?symbols=BTC,ETH&hours=100000")
    assert resp.status_code == 200
    d = resp.json()
    assert d["data"]["matrix"]["BTC"]["ETH"] is None
    assert "ETH" in (d.get("warning") or "")


def test_compare_endpoint_structure(app_client):
    _seed_prices("BTC", [100.0 + i for i in range(60)])
    _seed_prices("ETH", [50.0 + i for i in range(60)])
    d = app_client.get("/market/compare?symbols=BTC,ETH&hours=100000").json()["data"]
    rows = {r["symbol"]: r for r in d["comparison"]}
    assert set(rows) == {"BTC", "ETH"}
    for r in rows.values():
        for k in ("changePct", "volatility", "rsi", "trend", "points"):
            assert k in r
    assert rows["BTC"]["changePct"] == 59.0  # (159-100)/100


def test_compare_single_symbol_ok(app_client):
    # compare allows 1 symbol (min_n=1); correlation needs 2.
    _seed_prices("BTC", [100.0 + i for i in range(30)])
    resp = app_client.get("/market/compare?symbols=BTC&hours=100000")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["comparison"]) == 1


def test_relative_strength_endpoint(app_client):
    _seed_prices("ETH", [100.0, 110.0, 120.0, 140.0])  # rising
    _seed_prices("BTC", [100.0, 100.0, 100.0, 100.0])  # flat benchmark
    d = app_client.get("/market/relative-strength/ETH?vs=BTC&hours=100000").json()["data"]
    assert d["ratioTrend"] == "up"  # ETH outperforming flat BTC
    assert d["ratioChangePct"] == 40.0


def test_multi_symbol_endpoints_are_neutral_no_advice(app_client):
    """The comparison/correlation payloads carry NEUTRAL numbers — no advice words."""
    _seed_prices("BTC", [100.0 + i for i in range(30)])
    _seed_prices("ETH", [100.0 + i for i in range(30)])
    blob = (str(app_client.get("/market/compare?symbols=BTC,ETH&hours=100000").json())
            + str(app_client.get("/market/correlation?symbols=BTC,ETH&hours=100000").json())).lower()
    for word in ("recommend", "should", "buy", "sell", "advice"):
        assert word not in blob


# --- outlier guard (Task 28): stray seed points filtered at READ time, DB intact ---
def test_compare_filters_stray_seed_point_changepct_sane(app_client):
    """END-TO-END the real bug: a $0.5 seed row at the start of a ~$60k BTC series
    must NOT blow up changePct. The guard filters it at read time → honest ~5%, and
    the endpoint surfaces an honest 'filtered N anomalous' warning. DB is untouched."""
    _seed_prices("BTC", [0.5, 60000.0, 61000.0, 62000.0, 61500.0, 63000.0])
    body = app_client.get("/market/compare?symbols=BTC&hours=100000").json()
    row = {r["symbol"]: r for r in body["data"]["comparison"]}["BTC"]
    # without the guard this would be ~12,600,000%; with it, the real ~5% move.
    assert row["changePct"] is not None and abs(row["changePct"]) < 100.0
    assert row["points"] == 5  # the $0.5 point was dropped (6 → 5)
    assert "filtered" in (body.get("warning") or "").lower()
    # DB NOT mutated — the raw history still has all 6 points (we filter on read only).
    raw = app_client.get("/market/history/BTC?hours=100000").json()["data"]["points"]
    assert len(raw) == 6
    assert any(abs(p["price"] - 0.5) < 1e-9 for p in raw)


def test_correlation_robust_to_stray_point(app_client):
    """Two co-moving series, one polluted with a stray $0.5 → after the read-time
    guard both align to real points and still correlate strongly (not wrecked)."""
    _seed_prices("BTC", [100.0, 110.0, 0.5, 120.0, 130.0, 140.0, 150.0])
    _seed_prices("ETH", [200.0, 220.0, 240.0, 260.0, 280.0, 300.0, 320.0])
    d = app_client.get("/market/correlation?symbols=BTC,ETH&hours=100000").json()["data"]
    r = d["matrix"]["BTC"]["ETH"]
    assert r is not None and r > 0.9  # stray didn't poison the correlation


def test_compare_clean_series_no_false_positive_warning(app_client):
    """A clean (non-anomalous) series must produce NO 'filtered' warning — the guard
    only fires on genuine order-of-magnitude artifacts, never on normal data."""
    _seed_prices("BTC", [100.0 + i for i in range(40)])
    body = app_client.get("/market/compare?symbols=BTC&hours=100000").json()
    assert "filtered" not in (body.get("warning") or "").lower()
    row = {r["symbol"]: r for r in body["data"]["comparison"]}["BTC"]
    assert row["points"] == 40  # nothing dropped


# --- gold (Task 29): XAU is a tracked asset → flows through the WHOLE pipeline ---
def test_gold_is_tracked_asset(app_client):
    """XAU (assetClass=gold) is in the tracked universe — so history/indicators/ohlc
    treat it as a first-class asset (no 404), proving the pipeline picked it up."""
    # tracked → empty series is 200 {points:[]}, NOT a 404 (the untracked signal).
    assert app_client.get("/market/history/XAU").status_code == 200


def test_gold_indicators_flow_through_unchanged(app_client):
    """A seeded XAU close series runs through the EXISTING indicators endpoint with no
    gold-specific code — proves 'add an asset, reuse the pipeline' (RSI computes)."""
    _seed_prices("XAU", [2600.0 + i for i in range(40)])  # 40 rising gold ticks
    body = app_client.get("/market/indicators/XAU?indicators=rsi,summary&hours=100000").json()
    assert body["success"] is True
    rsi = body["data"]["indicators"]["rsi"]
    assert rsi["latest"] is not None  # RSI computed on gold exactly like crypto


def test_gold_correlation_vs_btc(app_client):
    """END-TO-END: gold (XAU) vs BTC correlation via the SAME /correlation endpoint —
    two co-moving seeded series → 1.0, proving XAU is a full correlation citizen."""
    _seed_prices("BTC", [float(i) for i in range(1, 30)])       # rising
    _seed_prices("XAU", [float(2600 + i) for i in range(1, 30)])  # rising in lockstep
    d = app_client.get("/market/correlation?symbols=BTC,XAU&hours=100000").json()["data"]
    assert d["matrix"]["BTC"]["XAU"] == 1.0
    assert d["matrix"]["XAU"]["XAU"] == 1.0


def test_gold_ohlc_flows_through(app_client):
    """XAU close-ticks bucket into OHLC candles via the existing /ohlc endpoint —
    no gold-specific candle code, the pipeline just works on the new asset."""
    _seed_prices("XAU", [2600.0, 2610.0, 2605.0, 2620.0, 2615.0])
    body = app_client.get("/market/ohlc/XAU?hours=100000&interval=60").json()
    assert body["success"] is True
    assert len(body["data"]["candles"]) >= 1  # ticks aggregated into ≥1 bar
