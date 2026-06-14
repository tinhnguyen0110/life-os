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
                      "patternCheckEnabled", "errorChannel", "timezone", "displayName",
                      "wikiAgentAutonomous"}  # W4d toggle exposed in GET /settings
    assert d["briefHour"] == 8 and d["idleThresholdDays"] == 7 and d["automationEnabled"] is True
    assert d["wikiAgentAutonomous"] is False  # W4d safe default OFF


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


# ---------------------------------------------------------------------------
# A4 — edge cases / error paths not previously covered
# ---------------------------------------------------------------------------

def test_briefhour_lower_boundary_zero_valid(app_client):
    """briefHour=0 is valid (midnight, lower bound ge=0) — 200, not 422."""
    r = app_client.patch("/settings", json={"briefHour": 0})
    assert r.status_code == 200
    assert r.json()["data"]["briefHour"] == 0


def test_briefhour_upper_boundary_23_valid(app_client):
    """briefHour=23 is valid (11pm, upper bound le=23) — 200, not 422."""
    r = app_client.patch("/settings", json={"briefHour": 23})
    assert r.status_code == 200
    assert r.json()["data"]["briefHour"] == 23


def test_briefhour_24_invalid_422(app_client):
    """briefHour=24 is above le=23 — 422 (existing test used 25; this tests the exact boundary)."""
    r = app_client.patch("/settings", json={"briefHour": 24})
    assert r.status_code == 422


def test_briefhour_negative_invalid_422(app_client):
    """briefHour=-1 is below ge=0 — 422."""
    r = app_client.patch("/settings", json={"briefHour": -1})
    assert r.status_code == 422


def test_idlethresholddays_min_boundary_1_valid(app_client):
    """idleThresholdDays=1 (minimum valid, ge=1) — 200, not 422."""
    r = app_client.patch("/settings", json={"idleThresholdDays": 1})
    assert r.status_code == 200
    assert r.json()["data"]["idleThresholdDays"] == 1


def test_pattern_check_enabled_false_observable_in_automation(app_client):
    """patternCheckEnabled=False → pattern_check_on() returns False.
    Exercises the live runtime read path (automation reads settings at runtime)."""
    from modules.automation import service as auto_svc
    from modules.settings import service as cfg_svc

    app_client.patch("/settings", json={"patternCheckEnabled": False})
    # automation's pattern_check_on() reads the live config — must reflect the PATCH
    assert cfg_svc.get_config().patternCheckEnabled is False
    assert auto_svc.pattern_check_on() is False


def test_pattern_check_enabled_true_observable(app_client):
    """patternCheckEnabled=True (default) → pattern_check_on() returns True."""
    from modules.automation import service as auto_svc

    app_client.patch("/settings", json={"patternCheckEnabled": True})
    assert auto_svc.pattern_check_on() is True


def test_wiki_agent_autonomous_toggle_on_persists(app_client):
    """wikiAgentAutonomous=True persists → GET /settings reflects True. (W4d field)"""
    r = app_client.patch("/settings", json={"wikiAgentAutonomous": True})
    assert r.status_code == 200
    assert r.json()["data"]["wikiAgentAutonomous"] is True
    # persisted: fresh GET reflects it
    g = app_client.get("/settings").json()["data"]
    assert g["wikiAgentAutonomous"] is True


def test_wiki_agent_autonomous_off_is_default(app_client):
    """wikiAgentAutonomous default is False (safe proposals-only mode). W4d trust boundary."""
    d = app_client.get("/settings").json()["data"]
    assert d["wikiAgentAutonomous"] is False


def test_wiki_agent_autonomous_round_trip_on_then_off(app_client):
    """Toggle wikiAgentAutonomous ON then back OFF — both states observable."""
    app_client.patch("/settings", json={"wikiAgentAutonomous": True})
    assert app_client.get("/settings").json()["data"]["wikiAgentAutonomous"] is True

    app_client.patch("/settings", json={"wikiAgentAutonomous": False})
    assert app_client.get("/settings").json()["data"]["wikiAgentAutonomous"] is False


def test_get_config_fail_open_malformed_yaml_returns_defaults():
    """get_config() with a malformed config.md → fails OPEN to defaults, never raises.
    Tests the service-layer fail-open path (not via the HTTP client — direct call)."""
    import importlib
    from unittest.mock import patch
    from modules.settings import service as cfg_svc

    # Simulate md_store.read returning malformed YAML front-matter
    with patch.object(cfg_svc.md_store, "read", return_value="---\n: bad: yaml: {{{\n---\n"):
        config = cfg_svc.get_config()

    # Must not raise; returns defaults
    assert config.briefHour == 8
    assert config.automationEnabled is True
    assert config.idleThresholdDays == 7


def test_automation_enabled_false_persists_and_readable(app_client):
    """automationEnabled=False persists and GET reflects it (master switch round-trip)."""
    r = app_client.patch("/settings", json={"automationEnabled": False})
    assert r.status_code == 200
    assert r.json()["data"]["automationEnabled"] is False
    assert app_client.get("/settings").json()["data"]["automationEnabled"] is False
