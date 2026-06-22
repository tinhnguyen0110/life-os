"""tests/test_reminders_channel.py — TRACING-UX T3 (#111): reminder delivery channel.

A reminder fires on a CHANNEL: in_app (default, the existing row/UI — NO external send), email, or
discord (route through the shared alerts engine's additive channels= override). The load-bearing teeth:
  - channel default = in_app; a bad channel → 422; a valid channel persists + reads back;
  - GET /reminders/channels available-flags REUSE the alerts engine's configured-detection;
  - an unavailable-but-set channel → fallback in_app + a warning (honest, not silent);
  - notify_scan: channel=in_app → NO alerts call (no double-fire); email/discord → alerts.notify(
    ..., channels=[that]); email-creds-missing → skip+log, no crash, scan continues;
  - tracing remindChannel → the linked reminder's channel;
  - migration idempotent; MCP reminders_channels ≡ REST.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from modules.alerts import service as alerts
from modules.reminders import service as svc, store
from modules.reminders.schema import ReminderInput


@pytest.fixture
def db(isolated_paths):
    store.init_reminders_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


@pytest.fixture
def all_configured(monkeypatch):
    """Both channels configured (so available + a set channel persists, doesn't fall back)."""
    monkeypatch.setattr(alerts, "_env_value",
                        lambda k: {"discord": "hook", "LIFEOS_SMTP_USER": "u",
                                   "LIFEOS_SMTP_APP_PASSWORD": "p"}.get(k, ""))


@pytest.fixture
def none_configured(monkeypatch):
    """No channel configured → email/discord unavailable (fall back to in_app)."""
    monkeypatch.setattr(alerts, "_env_value", lambda k: "")


def _due(mins: int = -1) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=mins)).isoformat()


# --------------------------------------------------------------------------- #
# schema/persist — default in_app; valid channel persists; bad → 422            #
# --------------------------------------------------------------------------- #
def test_channel_default_is_in_app(db):
    r = svc.create(ReminderInput(title="t", due_at=_due()))
    assert r.channel == "in_app"


def test_valid_channel_persists_and_reads_back(db, all_configured):
    r = svc.create(ReminderInput(title="t", due_at=_due(), channel="discord"))
    assert r.channel == "discord"
    assert svc.get(r.id).channel == "discord"  # reads back from the store


def test_bad_channel_is_422(api):
    r = api.post("/reminders", json={"title": "t", "due_at": _due(), "channel": "telegram"})
    assert r.status_code == 422  # not in the Literal


# --------------------------------------------------------------------------- #
# GET /reminders/channels — available REUSES alerts' configured-detection        #
# --------------------------------------------------------------------------- #
def test_channels_available_reflect_configured(db, all_configured):
    chans = {c["id"]: c for c in svc.list_channels()}
    assert chans["in_app"]["available"] is True
    assert chans["email"]["available"] is True and chans["discord"]["available"] is True


def test_channels_unavailable_when_creds_absent(db, none_configured):
    chans = {c["id"]: c for c in svc.list_channels()}
    assert chans["in_app"]["available"] is True  # always
    assert chans["email"]["available"] is False and "reason" in chans["email"]
    assert chans["discord"]["available"] is False and "reason" in chans["discord"]


def test_rest_channels_endpoint(api, all_configured):
    r = api.get("/reminders/channels")
    assert r.status_code == 200
    chans = r.json()["data"]["channels"]
    assert {c["id"] for c in chans} == {"in_app", "email", "discord"}
    assert all("available" in c for c in chans)


# --------------------------------------------------------------------------- #
# unavailable-but-set → fallback in_app + warning (honest, not silent)           #
# --------------------------------------------------------------------------- #
def test_unavailable_channel_falls_back_to_in_app_with_warning(api, none_configured):
    r = api.post("/reminders", json={"title": "t", "due_at": _due(), "channel": "discord"})
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["channel"] == "in_app", "unavailable channel must downgrade to in_app"
    assert body.get("warning") and "discord" in body["warning"]  # honest, not silent


def test_available_channel_no_fallback_no_warning(api, all_configured):
    r = api.post("/reminders", json={"title": "t", "due_at": _due(), "channel": "discord"})
    assert r.status_code == 201
    assert r.json()["data"]["channel"] == "discord"
    assert r.json().get("warning") is None


# --------------------------------------------------------------------------- #
# notify_scan routing — in_app=NO alerts call; email/discord→alerts; fail-soft   #
# --------------------------------------------------------------------------- #
def test_in_app_fire_does_NOT_call_alerts(db, monkeypatch):
    """🔴 NO DOUBLE-FIRE: an in_app reminder firing must NOT call alerts.notify (the row/UI is the
    surface). It still 'fires' (counter advances) — just no external send."""
    calls = []
    monkeypatch.setattr("modules.alerts.notify", lambda *a, **k: calls.append((a, k)))
    svc.create(ReminderInput(title="t", due_at=_due(), channel="in_app"))
    summary = svc.notify_scan()
    assert summary["fired"] == 1  # it DID fire (counter advances)
    assert calls == [], "in_app must NOT route through alerts (no double-fire)"


def test_discord_fire_calls_alerts_with_that_channel(db, all_configured, monkeypatch):
    """channel=discord firing → alerts.notify(..., channels=['discord']) — the additive override."""
    calls = []
    monkeypatch.setattr("modules.alerts.notify",
                        lambda severity, title, body, channels=None: calls.append(channels) or {})
    svc.create(ReminderInput(title="Ring", due_at=_due(), channel="discord"))
    svc.notify_scan()
    assert calls == [["discord"]], "discord reminder must route to exactly channels=['discord']"


def test_email_fire_calls_alerts_with_email(db, all_configured, monkeypatch):
    calls = []
    monkeypatch.setattr("modules.alerts.notify",
                        lambda severity, title, body, channels=None: calls.append(channels) or {})
    svc.create(ReminderInput(title="Mail me", due_at=_due(), channel="email"))
    svc.notify_scan()
    assert calls == [["email"]]


def test_scan_fail_soft_when_channel_send_raises(db, all_configured, monkeypatch):
    """A channel send raising must NOT crash the scan (fail-soft per reminder) — the scan completes."""
    def _boom(*a, **k):
        raise RuntimeError("smtp down")
    monkeypatch.setattr("modules.alerts.notify", _boom)
    svc.create(ReminderInput(title="t", due_at=_due(), channel="email"))
    summary = svc.notify_scan()  # must not raise
    assert summary["scanned"] == 1  # scan ran to completion despite the channel error


# --------------------------------------------------------------------------- #
# tracing remindChannel → the linked reminder's channel (#111 + #75 wire)        #
# --------------------------------------------------------------------------- #
def test_tracing_remind_channel_sets_linked_reminder_channel(db, all_configured):
    from modules.tracing import service as tsvc, store as tstore
    from modules.tracing.schema import ActivityInput
    tstore.init_tracing_tables()
    tsvc.create_activity(ActivityInput(id="run", name="Run", goal=5.0,
                                       remindAt="08:00", remindRepeat="daily", remindChannel="discord"))
    linked = store.find_by_activity("run", source="tracing")
    assert linked is not None and linked["channel"] == "discord"


# --------------------------------------------------------------------------- #
# migration idempotent (existing table — the ALTER guard)                        #
# --------------------------------------------------------------------------- #
def test_migration_idempotent_reinit(db, all_configured):
    svc.create(ReminderInput(title="t", due_at=_due(), channel="discord"))
    store.init_reminders_tables()  # re-run on the existing table
    store.init_reminders_tables()
    rows = store.list_reminders("all")
    assert any(r["channel"] == "discord" for r in rows), "channel survives a migration re-run"


# --------------------------------------------------------------------------- #
# MCP reminders_channels ≡ REST (#24)                                            #
# --------------------------------------------------------------------------- #
def test_mcp_reminders_channels_matches_rest(api, all_configured):
    from mcp_servers import read_server as rs
    rest = api.get("/reminders/channels").json()["data"]["channels"]
    mcp = rs.reminders_channels()["channels"]
    assert mcp == rest, "MCP reminders_channels must be byte-identical to REST"
