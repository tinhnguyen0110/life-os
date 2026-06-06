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
    """/holdings and /golden-path must NOT be captured by /{channel}."""
    # /holdings → list (200, list), NOT a 404 'channel holdings not found'
    assert isinstance(app_client.get("/finance/holdings").json()["data"], list)
    # /golden-path → targets dict, NOT channel detail
    assert "targets" in app_client.get("/finance/golden-path").json()["data"]
