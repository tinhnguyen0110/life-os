"""tests/test_finance_api.py — Finance router integration (Sprint 4 T2).

Drives the real app via TestClient with finance auto-mounted. Market quotes are
mocked at the service layer (no network). Covers all endpoints, envelope, status
codes, /health discovery, and the static-vs-dynamic route precedence.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from modules.market.schema import AssetQuote


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()

    # Mock market pricing so finance never hits the network.
    from modules.finance import service as fin_service

    def fake_get_quote(symbol):
        book = {"BTC": 60000.0, "VOO": 450.0}
        if symbol in book:
            return AssetQuote(symbol=symbol, name=symbol, assetClass="crypto",
                              price=book[symbol], currency="USD",
                              ts="2026-06-06T00:00:00+00:00", source="coingecko")
        return None

    monkeypatch.setattr(fin_service.market_service, "get_quote", fake_get_quote)

    # Disable the live OKX crypto override — these integration tests hand-calc the
    # crypto channel from manual holdings. If OKX is configured in the local env
    # (it is — live snapshot), _okx_crypto_value() would override crypto value and
    # break every assertion (e.g. alloc.value 60000 → live ~10626). Same isolation
    # as test_finance.py's no_okx_override fixture.
    monkeypatch.setattr(fin_service, "_okx_crypto_value", lambda: (None, None))

    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


# --- discovery ---
def test_health_lists_finance_module(app_client):
    assert "finance" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped_modules(app_client):
    assert not app_client.get("/health").json().get("warning")


# --- GET /finance overview ---
def test_overview_envelope(app_client):
    body = app_client.get("/finance").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) >= {"totalValue", "allocations", "dryPowder", "pnlTotal"}


def test_overview_handcalc_after_holdings(app_client):
    app_client.post("/finance/holdings", json={"channel": "crypto", "symbol": "BTC", "qty": 1, "avgCost": 50000})
    d = app_client.get("/finance").json()["data"]
    assert d["totalValue"] == 60000.0  # 1 * 60000 (mocked)
    assert d["pnlTotal"]["abs"] == 10000.0  # 60000 - 50000
    crypto = next(a for a in d["allocations"] if a["channel"] == "crypto")
    assert crypto["pnl"]["abs"] == 10000.0


# --- holdings CRUD ---
def test_holdings_crud(app_client):
    r = app_client.post("/finance/holdings", json={"channel": "etf", "symbol": "VOO", "qty": 10, "avgCost": 400})
    assert r.status_code == 200 and r.json()["success"] is True
    holdings = app_client.get("/finance/holdings").json()["data"]
    assert any(h["symbol"] == "VOO" for h in holdings)
    d = app_client.delete("/finance/holdings/VOO")
    assert d.status_code == 200
    assert app_client.get("/finance/holdings").json()["data"] == []


def test_holding_delete_404(app_client):
    assert app_client.delete("/finance/holdings/NOPE").status_code == 404


def test_holding_422_bad_body(app_client):
    # qty must be >= 0
    assert app_client.post("/finance/holdings", json={"channel": "etf", "symbol": "X", "qty": -1, "avgCost": 1}).status_code == 422
    # channel must be a valid Literal
    assert app_client.post("/finance/holdings", json={"channel": "bogus", "symbol": "X", "qty": 1, "avgCost": 1}).status_code == 422


# --- golden path get/set ---
def test_golden_path_baseline_then_set(app_client):
    gp = app_client.get("/finance/golden-path").json()
    assert gp["data"]["targets"]["crypto"] == 38.0  # baseline
    assert gp.get("warning")  # baseline warning
    put = app_client.put("/finance/golden-path", json={"targets": {"crypto": 50, "dry": 50}, "ladder": {"crypto": {"reference": 60000, "rungs": [-10]}}})
    assert put.status_code == 200
    gp2 = app_client.get("/finance/golden-path").json()
    assert gp2["data"]["targets"] == {"crypto": 50.0, "dry": 50.0}
    # get/set symmetric: response carries `ladder` (same key as the PUT body), a dict
    assert gp2["data"]["ladder"]["crypto"]["reference"] == 60000
    assert "ladderRungs" not in gp2["data"]  # old asymmetric key gone
    assert not gp2.get("warning")


# --- GET /finance/{channel} detail (+ route precedence) ---
def test_channel_detail(app_client):
    app_client.post("/finance/holdings", json={"channel": "crypto", "symbol": "BTC", "qty": 1, "avgCost": 50000})
    body = app_client.get("/finance/crypto").json()
    assert body["success"] is True
    assert body["data"]["channel"] == "crypto"
    assert body["data"]["alloc"]["value"] == 60000.0


def test_channel_detail_404(app_client):
    assert app_client.get("/finance/NoSuchChannel").status_code == 404


def test_static_routes_win_over_channel_param(app_client):
    """/holdings, /golden-path, /analytics must NOT be captured by /{channel}."""
    # /holdings → list (200, list), NOT a 404 'channel holdings not found'
    assert isinstance(app_client.get("/finance/holdings").json()["data"], list)
    # /golden-path → targets dict, NOT channel detail
    assert "targets" in app_client.get("/finance/golden-path").json()["data"]
    # /analytics → analytics payload (has 'rebalance'), NOT a 404 channel lookup
    body = app_client.get("/finance/analytics")
    assert body.status_code == 200 and "rebalance" in body.json()["data"]


# --- GET /finance/analytics ---
def test_analytics_envelope_and_shape(app_client):
    resp = app_client.get("/finance/analytics")
    assert resp.status_code == 200
    d = resp.json()["data"]
    for k in ("totalValue", "rebalance", "risk", "returns", "asOf"):
        assert k in d
    # 4 channels in rebalance (crypto/etf/vn/dry) even with an empty portfolio.
    assert {r["channel"] for r in d["rebalance"]} == {"crypto", "etf", "vn", "dry"}


def test_analytics_rebalance_amounts_end_to_end(app_client):
    """Through the real endpoint: BTC 1 @ $60000 = $60000 all-crypto; baseline target
    crypto 38% → target value $22800 → SELL $37200."""
    app_client.post("/finance/holdings", json={"channel": "crypto", "symbol": "BTC", "qty": 1, "avgCost": 50000})
    d = app_client.get("/finance/analytics").json()["data"]
    assert d["totalValue"] == 60000.0
    crypto = next(r for r in d["rebalance"] if r["channel"] == "crypto")
    assert crypto["targetValue"] == 22800.0  # 38% of 60000
    assert crypto["action"] == "sell" and crypto["amount"] == 37200.0
    # concentration: single holding → 100%, HHI 1.0
    assert d["risk"]["topHoldingPct"] == 100.0 and d["risk"]["hhi"] == 1.0


# --- POST /finance/snapshot + GET /finance/history (equity curve) ---
def test_snapshot_endpoint_records_and_history_reads(app_client):
    app_client.post("/finance/holdings", json={"channel": "crypto", "symbol": "BTC", "qty": 1, "avgCost": 50000})
    snap = app_client.post("/finance/snapshot")
    assert snap.status_code == 200
    d = snap.json()["data"]
    assert d["totalValue"] == 60000.0 and "day" in d and d["byChannel"]["crypto"] == 60000.0
    # history reads it back
    hist = app_client.get("/finance/history?days=90").json()["data"]
    assert len(hist["points"]) == 1 and hist["points"][0]["totalValue"] == 60000.0


def test_history_empty_is_200_with_warning(app_client):
    resp = app_client.get("/finance/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["points"] == []
    assert "no portfolio snapshots" in (body.get("warning") or "")


def test_history_days_validation(app_client):
    assert app_client.get("/finance/history?days=0").status_code == 422     # >0 required
    assert app_client.get("/finance/history?days=999").status_code == 422   # ≤365 cap
    assert app_client.get("/finance/history?days=30").status_code == 200    # valid


def test_snapshot_history_win_over_channel_param(app_client):
    """/snapshot and /history must NOT be captured by /{channel}."""
    # /history → has 'points' key, NOT a 404 channel lookup
    assert "points" in app_client.get("/finance/history").json()["data"]
    # /snapshot is POST → a GET would 405, but POST routes to the snapshot handler.
    assert app_client.post("/finance/snapshot").status_code == 200


def test_returns_available_after_two_snapshots_via_api(app_client):
    """End-to-end: ≥2 snapshots (seeded across days) → analytics returns.available=True."""
    from datetime import datetime, timedelta, timezone

    from store import db
    base = datetime.now(timezone.utc)
    db.record_snapshot((base - timedelta(days=1)).isoformat(), 100.0)
    db.record_snapshot(base.isoformat(), 120.0)
    returns = app_client.get("/finance/analytics").json()["data"]["returns"]
    assert returns["available"] is True
    assert returns["totalReturnPct"] == 20.0  # (120-100)/100


# --- POST /finance/simulate (what-if scenario) ---
def test_simulate_endpoint_shape_and_hhi(app_client):
    """End-to-end: a hypothetical 60/20/20 allocation → HHI 0.44, current+delta present."""
    body = app_client.post("/finance/simulate",
                           json={"allocation": {"crypto": 60, "etf": 20, "vn": 20}}).json()
    assert body["success"] is True
    d = body["data"]
    for k in ("hypothetical", "current", "hhiDelta", "normalized", "asOf"):
        assert k in d
    assert d["hypothetical"]["hhi"] == 0.44
    assert d["hypothetical"]["concentrationTopChannel"] == "crypto"


def test_simulate_compares_against_current(app_client):
    """With a current all-crypto portfolio, simulate shows current HHI 1.0 + the delta."""
    app_client.post("/finance/holdings", json={"channel": "crypto", "symbol": "BTC", "qty": 1, "avgCost": 50000})
    d = app_client.post("/finance/simulate",
                        json={"allocation": {"crypto": 60, "etf": 20, "vn": 20}}).json()["data"]
    assert d["current"]["hhi"] == 1.0       # current is 100% crypto
    assert d["hhiDelta"] == -0.56           # 0.44 - 1.0 (hypothetical more diversified)


def test_simulate_empty_allocation_422(app_client):
    assert app_client.post("/finance/simulate", json={"allocation": {}}).status_code == 422


def test_simulate_negative_weight_422(app_client):
    assert app_client.post("/finance/simulate",
                           json={"allocation": {"crypto": 60, "etf": -20}}).status_code == 422


def test_simulate_unknown_channel_422(app_client):
    assert app_client.post("/finance/simulate",
                           json={"allocation": {"crypto": 50, "bogus": 50}}).status_code == 422


def test_simulate_normalizes_and_flags(app_client):
    """Weights that don't sum to 100 are normalized → normalized=True + warning."""
    body = app_client.post("/finance/simulate",
                           json={"allocation": {"crypto": 6000, "etf": 4000}}).json()
    assert body["data"]["normalized"] is True
    assert "normalized" in (body.get("warning") or "").lower()
    assert body["data"]["hypothetical"]["hhi"] == 0.52  # .6²+.4² = .36+.16


def test_simulate_wins_over_channel_param(app_client):
    """POST /finance/simulate routes to the simulate handler, not /{channel} (which is GET)."""
    r = app_client.post("/finance/simulate", json={"allocation": {"crypto": 100}})
    assert r.status_code == 200 and "hypothetical" in r.json()["data"]


def test_simulate_endpoint_neutral_no_advice(app_client):
    blob = str(app_client.post("/finance/simulate",
               json={"allocation": {"crypto": 40, "etf": 30, "vn": 20, "dry": 10}}).json()).lower()
    for word in ("recommend", "should", "buy", "sell", "advice"):
        assert word not in blob
