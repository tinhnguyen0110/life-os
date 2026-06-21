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
                      "wikiAgentAutonomous",
                      # #55 FINANCE-ASSISTANT P3: user-configurable capital-size risk thresholds
                      "riskCapitalSmallUsd", "riskCapitalLargeUsd",
                      # #72 SIDEBAR-UX: backend-persisted pinned sidebar routes (multi-device)
                      "pinnedRoutes",
                      # #33 ALERT-ROUTING: the alert mail-threshold knob
                      "alertMailThreshold"}
    assert d["briefHour"] == 8 and d["idleThresholdDays"] == 7 and d["automationEnabled"] is True
    assert d["wikiAgentAutonomous"] is True  # WIKI-WRITE-THROUGH #25: default ON (was OFF, W4d)
    assert d["riskCapitalSmallUsd"] == 50000.0 and d["riskCapitalLargeUsd"] == 500000.0  # #55 defaults
    assert d["pinnedRoutes"] == []  # #72 default: no pins → empty list (not missing/null)
    assert d["alertMailThreshold"] == "high"  # #33 default: mail only on high severity


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


def test_wiki_agent_autonomous_on_is_default(app_client):
    """WIKI-WRITE-THROUGH #25: wikiAgentAutonomous default is now True (write-through — agent
    writes apply directly, audited + reversible). Was False (W4d proposals-only). The escape
    hatch (OFF → proposals-only) is the round-trip test below."""
    d = app_client.get("/settings").json()["data"]
    assert d["wikiAgentAutonomous"] is True


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


# --------------------------------------------------------------------------- #
# SIDEBAR-UX (#72) — pinnedRoutes: backend-persisted pinned sidebar routes that #
# SYNC across devices (Tailscale multi-device). PATCH→GET round-trip, ordered,  #
# []-clears, partial-patch-safe, default []. Exercise the REAL endpoint loop     #
# (built-but-not-wired: don't trust the schema — the sync point IS the round-trip).#
# --------------------------------------------------------------------------- #
def test_pinned_routes_default_empty(app_client):
    """(4) default: a fresh config → pinnedRoutes is [] (not missing/null)."""
    d = app_client.get("/settings").json()["data"]
    assert d["pinnedRoutes"] == []


def test_pinned_routes_patch_get_round_trip_ordered_and_persists(app_client):
    """(1) THE MULTI-DEVICE SYNC POINT: PATCH the pins → GET reflects them IN ORDER →
    a fresh GET (the '2nd device') still shows them (persisted backend, not localStorage)."""
    r = app_client.patch("/settings", json={"pinnedRoutes": ["/finance", "/projects", "/market"]})
    assert r.status_code == 200
    assert r.json()["data"]["pinnedRoutes"] == ["/finance", "/projects", "/market"]  # ordered
    # fresh GET = a 2nd device reading the synced config
    g = app_client.get("/settings").json()["data"]
    assert g["pinnedRoutes"] == ["/finance", "/projects", "/market"]


def test_pinned_routes_empty_list_clears_not_noop(app_client):
    """(2) clear: PATCH [] CLEARS the pins (empty list persists — NOT a no-op that
    leaves the old pins). The exclude_none merge keeps [] (only None is dropped)."""
    app_client.patch("/settings", json={"pinnedRoutes": ["/finance", "/projects"]})
    r = app_client.patch("/settings", json={"pinnedRoutes": []})
    assert r.status_code == 200
    assert r.json()["data"]["pinnedRoutes"] == []
    assert app_client.get("/settings").json()["data"]["pinnedRoutes"] == []  # persisted clear


def test_pinned_routes_partial_patch_does_not_touch_pins(app_client):
    """(3) partial-patch-safe BOTH ways: a PATCH WITHOUT pinnedRoutes leaves the stored
    pins intact (exclude_none); and a PATCH of ONLY pinnedRoutes doesn't touch other fields."""
    # set pins + a known briefHour
    app_client.patch("/settings", json={"pinnedRoutes": ["/finance"], "briefHour": 9})
    # patch ANOTHER field only → pins survive
    app_client.patch("/settings", json={"displayName": "owner"})
    g = app_client.get("/settings").json()["data"]
    assert g["pinnedRoutes"] == ["/finance"]  # pins untouched by a no-pin PATCH
    assert g["briefHour"] == 9 and g["displayName"] == "owner"
    # patch ONLY pins → other fields untouched
    app_client.patch("/settings", json={"pinnedRoutes": ["/projects"]})
    g2 = app_client.get("/settings").json()["data"]
    assert g2["pinnedRoutes"] == ["/projects"]
    assert g2["briefHour"] == 9 and g2["displayName"] == "owner"  # unchanged


def test_pinned_routes_stale_route_stored_as_is_no_422(app_client):
    """fail-soft: a stale/unknown route string is STORED AS-IS (no route validation) — a
    route the user pinned then we renamed must NOT 422 (the FE skips unresolved routes)."""
    r = app_client.patch("/settings", json={"pinnedRoutes": ["/renamed-gone", "/finance"]})
    assert r.status_code == 200  # not 422 — we don't validate route existence
    assert r.json()["data"]["pinnedRoutes"] == ["/renamed-gone", "/finance"]


def test_pinned_routes_unknown_field_still_422(app_client):
    """extra=forbid is intact even with the new field — an unknown key is still a 422."""
    assert app_client.patch("/settings", json={"pinnedRoute": ["/x"]}).status_code == 422  # typo'd key


# --------------------------------------------------------------------------- #
# PRIVACY VERIFY (#74) — env-based reveal-pass check. POST /settings/privacy/   #
# verify {pass} → {ok: bool}. The pass is env-stored (LIFEOS_PRIVACY_PASS), NEVER#
# sent to the FE; the FE sends the attempt, the BE compares (constant-time).     #
# Single-user localhost veil — public + unlimited (no auth/rate-limit).          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def known_privacy_pass(monkeypatch):
    """Pin the pass to a known value (don't depend on the real .env in tests)."""
    from core.config import settings
    monkeypatch.setattr(settings, "privacy_pass", "0110")


def test_privacy_verify_right_pass_ok_true(app_client, known_privacy_pass):
    """The correct pass → {ok: true} (the reveal succeeds)."""
    r = app_client.post("/settings/privacy/verify", json={"pass": "0110"})
    assert r.status_code == 200
    assert r.json()["data"] == {"ok": True}


def test_privacy_verify_wrong_pass_ok_false(app_client, known_privacy_pass):
    """A wrong pass → {ok: false} (200, not an error — the FE just stays hidden)."""
    r = app_client.post("/settings/privacy/verify", json={"pass": "9999"})
    assert r.status_code == 200
    assert r.json()["data"] == {"ok": False}


def test_privacy_verify_empty_pass_ok_false(app_client, known_privacy_pass):
    """An empty pass attempt → {ok: false} (never matches a non-empty stored pass)."""
    r = app_client.post("/settings/privacy/verify", json={"pass": ""})
    assert r.status_code == 200
    assert r.json()["data"] == {"ok": False}


def test_privacy_verify_missing_field_ok_false(app_client, known_privacy_pass):
    """No `pass` field at all → defaults to "" → {ok: false} (no 422 — a missing attempt
    is just a failed reveal, not a malformed request)."""
    r = app_client.post("/settings/privacy/verify", json={})
    assert r.status_code == 200
    assert r.json()["data"] == {"ok": False}


def test_privacy_pass_never_in_any_settings_response(app_client, known_privacy_pass):
    """The pass NEVER leaks to the FE: it's NOT in GET /settings (it's an env field on
    core.config, not AppConfig) and the verify endpoint returns only {ok}, never the pass."""
    g = app_client.get("/settings").json()["data"]
    assert "privacy_pass" not in g and "privacyPass" not in g
    body = app_client.post("/settings/privacy/verify", json={"pass": "0110"}).json()
    assert "0110" not in str(body)  # the response carries only {ok: true}, never the pass
