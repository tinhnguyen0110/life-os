"""tests/test_claude_usage_api.py — Claude Usage router integration (Sprint 7 T2).

Real app via TestClient, claude-usage auto-mounted. Stats-cache points at a
fixture (NEVER real ~/.claude). Envelope + /health discovery + override PUT.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)

    # stats-cache fixture (NOT real ~/.claude)
    fix = tmp_path / "stats-cache.json"
    fix.write_text(json.dumps({
        "lastComputedDate": _today(),
        "dailyModelTokens": [{"date": _today(), "tokensByModel": {"claude-opus-4-7": 50_000}}],
        "modelUsage": {"claude-opus-4-7": {"inputTokens": 1_000_000, "outputTokens": 0,
                                           "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0}},
    }))
    monkeypatch.setattr(settings, "claude_stats_path", fix)

    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        c._stats_fixture = fix  # type: ignore[attr-defined]
        yield c
    db.close_db()


# --- discovery ---
def test_health_lists_claude_usage_module(app_client):
    assert "claude-usage" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped_modules(app_client):
    assert not app_client.get("/health").json().get("warning")


# --- GET /claude-usage ---
def test_get_usage_envelope(app_client):
    body = app_client.get("/claude-usage").json()
    assert body["success"] is True
    d = body["data"]
    required = {"model", "used", "cap", "pct", "remaining", "resetIn", "weekly", "series",
                "today", "avgPerDay", "peak", "byModel", "costUSD", "byProject", "asOf",
                "stale", "source"}
    assert not (required - set(d)), f"missing keys: {required - set(d)}"
    assert d["source"] == "stats-cache"
    assert d["used"] == 50_000 and d["today"] == 50_000
    assert d["byModel"][0]["costUSD"] == 15.0  # 1M opus input @ 15/1M


def test_get_usage_pct_self_describing(app_client):
    d = app_client.get("/claude-usage").json()["data"]
    assert d["pct"] == round(d["used"] / d["cap"] * 100, 1)  # checkable from payload


# --- fail-open manual mode (200, not 500) ---
def test_get_usage_manual_mode_when_no_stats(app_client, monkeypatch, tmp_path):
    from core.config import settings
    monkeypatch.setattr(settings, "claude_stats_path", tmp_path / "gone.json")
    resp = app_client.get("/claude-usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["source"] == "manual"
    assert body.get("warning") and "manual mode" in body["warning"]


# --- PUT /claude-usage/override ---
def test_put_override(app_client):
    r = app_client.put("/claude-usage/override", json={"cap": 500_000, "resetIn": "2h 30m", "weekly": 1_000_000})
    assert r.status_code == 200 and r.json()["success"] is True
    d = r.json()["data"]
    assert d["cap"] == 500_000 and d["resetIn"] == "2h 30m" and d["weekly"] == 1_000_000
    # persisted: a fresh GET reflects it
    g = app_client.get("/claude-usage").json()["data"]
    assert g["cap"] == 500_000 and g["resetIn"] == "2h 30m"


def test_put_override_422_negative_cap(app_client):
    assert app_client.put("/claude-usage/override", json={"cap": -1}).status_code == 422


def test_put_override_empty_ok(app_client):
    # all-None override is valid (clears nothing, uses defaults)
    assert app_client.put("/claude-usage/override", json={}).status_code == 200
