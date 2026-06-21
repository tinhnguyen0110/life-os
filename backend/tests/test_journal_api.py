"""tests/test_journal_api.py — Journal router integration (Sprint 9).

Real app via TestClient. /health discovery, GET /journal (entries+stats), CRUD,
422s, filters. Writes fail-CLOSED (covered at the service layer in test_journal.py).
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_health_lists_journal(app_client):
    assert "journal" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped(app_client):
    assert not app_client.get("/health").json().get("warning")


def test_empty_journal_envelope(app_client):
    body = app_client.get("/journal").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) == {"entries", "count", "winRate", "avgPnl", "ladderDiscipline", "thisMonth", "calibration"}
    assert d["count"] == 0 and d["winRate"] is None and d["calibration"] == []


def test_create_get_round_trip(app_client):
    r = app_client.post("/journal", json={
        "action": "BUY", "asset": "BTC", "size": "$2,000", "px": "$68,240",
        "tag": "ladder", "reason": "DCA", "confidence": 70})
    assert r.status_code == 200
    eid = r.json()["data"]["id"]
    assert eid.startswith("btc-")
    got = app_client.get(f"/journal/{eid}").json()["data"]
    assert got["asset"] == "BTC" and got["outcome"] == "open" and got["confidence"] == 70


def test_create_then_stats(app_client):
    app_client.post("/journal", json={"action": "BUY", "asset": "A", "reason": "x", "pnl": "+10%"})
    app_client.post("/journal", json={"action": "BUY", "asset": "B", "reason": "x", "pnl": "-5%"})
    d = app_client.get("/journal").json()["data"]
    assert d["count"] == 2
    assert d["winRate"] == 50.0  # 1 win / 2 closed
    assert d["avgPnl"] == round((10 - 5) / 2, 2)


def test_get_404(app_client):
    r = app_client.get("/journal/nope-000000")
    assert r.status_code == 404
    j = r.json()  # #46-P5: flat agent_error, not {detail}
    assert "detail" not in j and j["error"]["code"] == "NOT_FOUND" and j["error"]["hint"]


def test_update_close(app_client):
    eid = app_client.post("/journal", json={"action": "BUY", "asset": "BTC", "reason": "x"}).json()["data"]["id"]
    r = app_client.put(f"/journal/{eid}", json={"action": "BUY", "asset": "BTC", "reason": "x", "pnl": "+15%", "lesson": "patience"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["outcome"] == "right" and d["pnl"] == "+15%" and d["lesson"] == "patience"


def test_update_404(app_client):
    assert app_client.put("/journal/nope-000000", json={"action": "BUY", "asset": "X", "reason": "x"}).status_code == 404


def test_delete(app_client):
    eid = app_client.post("/journal", json={"action": "BUY", "asset": "BTC", "reason": "x"}).json()["data"]["id"]
    assert app_client.delete(f"/journal/{eid}").status_code == 200
    assert app_client.get(f"/journal/{eid}").status_code == 404


def test_delete_404(app_client):
    assert app_client.delete("/journal/ghost-000000").status_code == 404


def test_422_bad_input(app_client):
    assert app_client.post("/journal", json={"action": "HOLD", "asset": "X", "reason": "x"}).status_code == 422  # bad action
    assert app_client.post("/journal", json={"action": "BUY", "asset": "", "reason": "x"}).status_code == 422   # empty asset
    assert app_client.post("/journal", json={"action": "BUY", "asset": "X", "reason": ""}).status_code == 422    # empty reason
    assert app_client.post("/journal", json={"action": "BUY", "asset": "X", "reason": "x", "confidence": 150}).status_code == 422


def test_filters(app_client):
    app_client.post("/journal", json={"action": "BUY", "asset": "BTC", "reason": "x", "tag": "ladder"})
    app_client.post("/journal", json={"action": "SELL", "asset": "ETH", "reason": "x", "tag": "dca"})
    buys = app_client.get("/journal?action=BUY").json()["data"]["entries"]
    assert [e["asset"] for e in buys] == ["BTC"]
    ladder = app_client.get("/journal?tag=ladder").json()["data"]["entries"]
    assert [e["asset"] for e in ladder] == ["BTC"]
