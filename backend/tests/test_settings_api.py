"""tests/test_settings_api.py — Settings router integration (S12).

Real app via TestClient. GET /settings (defaults), PATCH /settings (partial + round-trip),
per-field 422 (bad briefHour/idleThreshold/enum/unknown-field).
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
    monkeypatch.setattr(settings, "project_repos", {})
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_health_lists_settings_module(app_client):
    assert "settings" in app_client.get("/health").json()["data"]["modules"]


def test_get_settings_defaults(app_client):
    body = app_client.get("/settings").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) == {"automationEnabled", "briefHour", "idleThresholdDays",
                      "patternCheckEnabled", "errorChannel", "timezone", "displayName"}
    assert d["briefHour"] == 8 and d["idleThresholdDays"] == 7 and d["automationEnabled"] is True


def test_patch_settings_round_trip(app_client):
    r = app_client.patch("/settings", json={"idleThresholdDays": 14, "briefHour": 6})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["idleThresholdDays"] == 14 and d["briefHour"] == 6
    # persisted: a fresh GET reflects it
    g = app_client.get("/settings").json()["data"]
    assert g["idleThresholdDays"] == 14 and g["briefHour"] == 6
    assert g["timezone"] == "Asia/Ho_Chi_Minh"  # untouched default


def test_patch_bad_briefhour_422(app_client):
    r = app_client.patch("/settings", json={"briefHour": 25})
    assert r.status_code == 422
    assert "briefHour" in r.text  # error echoes the field


def test_patch_bad_idle_threshold_422(app_client):
    assert app_client.patch("/settings", json={"idleThresholdDays": 0}).status_code == 422


def test_patch_bad_error_channel_422(app_client):
    assert app_client.patch("/settings", json={"errorChannel": "email"}).status_code == 422


def test_patch_unknown_field_422(app_client):
    assert app_client.patch("/settings", json={"bogus": True}).status_code == 422


def test_patch_blank_displayname_allowed(app_client):
    """displayName may be empty (dispatch default "", stored-only) — 200, not 422."""
    r = app_client.patch("/settings", json={"displayName": ""})
    assert r.status_code == 200 and r.json()["data"]["displayName"] == ""
