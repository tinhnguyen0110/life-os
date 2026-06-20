"""tests/test_automation_api.py — Automation router integration (S10A).

Real app via TestClient (scheduler enabled=False — routines register but DON'T fire
on a timer). GET /routines, PATCH toggle, POST run (records run_log), 404s.
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
    monkeypatch.setattr(settings, "scheduler_enabled", False)  # no timers in tests
    monkeypatch.setattr(settings, "project_repos", {})
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_health_lists_routines_module(app_client):
    assert "routines" in app_client.get("/health").json()["data"]["modules"]


def test_health_routines_include_morning_pull(app_client):
    # morning-pull (cron) registers via the automation module; /health lists routine ids
    assert "morning-pull" in app_client.get("/health").json()["data"]["routines"]


def test_get_routines_shape(app_client):
    body = app_client.get("/routines").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) == {"routines", "activeCount", "total", "runsToday", "lastRunAt"}
    # JOURNAL-NUDGE (#14) Part 3: +macro-poll +news-capture (routine attribution). Was 8 (#62).
    assert d["total"] == 10
    ids = {r["id"] for r in d["routines"]}
    assert ids == {"market-poll", "wiki-refresh", "idle-hunter", "pattern-check",
                   "journal-nudge", "morning-pull", "macro-snapshot", "held-history",
                   "macro-poll", "news-capture"}
    # each routine has the full RoutineInfo shape
    r0 = d["routines"][0]
    assert set(r0) >= {"id", "name", "trigger", "triggerLabel", "desc", "action", "enabled", "lastRun", "lastResult", "runs"}


def test_get_routines_empty_stats(app_client):
    d = app_client.get("/routines").json()["data"]
    assert d["runsToday"] == 0 and d["lastRunAt"] is None
    assert all(r["lastRun"] is None and r["runs"] == 0 for r in d["routines"])


def test_patch_toggle(app_client):
    r = app_client.patch("/routines/idle-hunter", json={"enabled": False})
    assert r.status_code == 200 and r.json()["data"]["enabled"] is False
    # persisted: GET reflects it
    routines = {x["id"]: x for x in app_client.get("/routines").json()["data"]["routines"]}
    assert routines["idle-hunter"]["enabled"] is False
    assert app_client.get("/routines").json()["data"]["activeCount"] == 9  # 10 total, one off


def test_patch_unknown_404(app_client):
    assert app_client.patch("/routines/ghost", json={"enabled": True}).status_code == 404


def test_post_run_records(app_client):
    r = app_client.post("/routines/idle-hunter/run")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["id"] == "idle-hunter" and d["status"] in ("ok", "warn")
    assert d["startedAt"] and d["finishedAt"]
    # run_log row landed → GET shows runs>=1
    routines = {x["id"]: x for x in app_client.get("/routines").json()["data"]["routines"]}
    assert routines["idle-hunter"]["runs"] >= 1 and routines["idle-hunter"]["lastResult"] is not None


def test_post_run_unknown_404(app_client):
    assert app_client.post("/routines/ghost/run").status_code == 404


def test_post_run_failed_dep_still_200_logged_error(app_client, monkeypatch):
    """A run whose deps blow up → 200 with an error-status run (logged), NOT a 500."""
    from modules.automation import service as auto
    monkeypatch.setitem(auto._CATALOG_BY_ID["idle-hunter"], "func",
                        lambda: (_ for _ in ()).throw(RuntimeError("dep down")))
    r = app_client.post("/routines/idle-hunter/run")
    assert r.status_code == 200  # the run HAPPENED + is logged
    assert r.json()["data"]["status"] == "error" and "dep down" in r.json()["data"]["detail"]


# ---------------------------------------------------------------------------
# A4 — edge cases / error paths not previously covered
# ---------------------------------------------------------------------------

def test_toggle_disable_enable_cycle_observable(app_client):
    """Disable a routine then re-enable it — both states observable in GET /routines."""
    # disable pattern-check
    r = app_client.patch("/routines/pattern-check", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["data"]["enabled"] is False

    d = app_client.get("/routines").json()["data"]
    assert d["activeCount"] == 9  # 10 total, one off
    routines = {x["id"]: x for x in d["routines"]}
    assert routines["pattern-check"]["enabled"] is False

    # re-enable
    r2 = app_client.patch("/routines/pattern-check", json={"enabled": True})
    assert r2.status_code == 200
    assert r2.json()["data"]["enabled"] is True

    d2 = app_client.get("/routines").json()["data"]
    assert d2["activeCount"] == 10  # restored (10 total)
    routines2 = {x["id"]: x for x in d2["routines"]}
    assert routines2["pattern-check"]["enabled"] is True


def test_toggle_two_off_active_count_drops_by_two(app_client):
    """Disable two separate routines → activeCount drops by 2 (10 total → 8)."""
    app_client.patch("/routines/idle-hunter", json={"enabled": False})
    app_client.patch("/routines/journal-nudge", json={"enabled": False})
    d = app_client.get("/routines").json()["data"]
    assert d["activeCount"] == 8  # 10 total, two off
    routines = {x["id"]: x for x in d["routines"]}
    assert routines["idle-hunter"]["enabled"] is False
    assert routines["journal-nudge"]["enabled"] is False


def test_run_scheduled_returns_none_when_automation_off(app_client, monkeypatch):
    """run_scheduled gates on automationEnabled — when OFF, returns None + no run_log row."""
    from modules.automation import service as auto
    from modules.settings import service as cfg_svc
    from modules.settings.schema import AppConfig

    # flip the master switch OFF
    monkeypatch.setattr(cfg_svc, "get_config", lambda: AppConfig(automationEnabled=False))

    result = auto.run_scheduled("idle-hunter", lambda: ("ok", "should not run"))
    assert result is None

    # run_log must NOT have received a row (observable via list_routines)
    from store import db
    rows = db.recent_runs("idle-hunter", limit=10)
    assert len(rows) == 0


def test_run_scheduled_runs_when_automation_on(app_client, monkeypatch):
    """run_scheduled with automationEnabled=True executes the func + logs the row."""
    from modules.automation import service as auto
    from modules.settings import service as cfg_svc
    from modules.settings.schema import AppConfig
    from store import db

    monkeypatch.setattr(cfg_svc, "get_config", lambda: AppConfig(automationEnabled=True))

    result = auto.run_scheduled("journal-nudge", lambda: ("warn", "test fired"))
    assert result is not None
    assert result["status"] == "warn"
    assert result["detail"] == "test fired"
    rows = db.recent_runs("journal-nudge", limit=5)
    assert len(rows) >= 1
    assert rows[0]["status"] == "warn"


def test_automation_on_fail_open_when_settings_raises(monkeypatch):
    """automation_on() fails OPEN (returns True) when settings raises — never disables by accident."""
    from modules.automation import service as auto
    from modules.settings import service as cfg_svc

    monkeypatch.setattr(cfg_svc, "get_config", lambda: (_ for _ in ()).throw(RuntimeError("config down")))
    assert auto.automation_on() is True


def test_record_routine_run_tuple_result_propagated():
    """func() returning (status, detail) tuple → status + detail surfaced in the result."""
    from modules.automation import service as auto

    result = auto.record_routine_run("idle-hunter", lambda: ("warn", "3 dự án đứng"))
    assert result["status"] == "warn"
    assert result["detail"] == "3 dự án đứng"
    assert result["startedAt"] and result["finishedAt"]


def test_record_routine_run_non_tuple_maps_to_ok():
    """func() returning None or a non-tuple → status='ok', detail=''."""
    from modules.automation import service as auto

    result = auto.record_routine_run("idle-hunter", lambda: None)
    assert result["status"] == "ok"
    assert result["detail"] == ""


def test_record_routine_run_invalid_status_clamped_to_ok():
    """func() returning a tuple with an unrecognised status string → clamped to 'ok'."""
    from modules.automation import service as auto

    result = auto.record_routine_run("idle-hunter", lambda: ("WEIRD_STATUS", "info"))
    assert result["status"] == "ok"


def test_journal_nudge_with_explicit_alert_returns_warn():
    """journal_nudge(alert={symbol:...}) uses the provided alert directly → 'warn'."""
    from modules.automation.service import journal_nudge

    status, detail = journal_nudge(alert={"symbol": "BTC", "price": 65000})
    assert status == "warn"
    assert "BTC" in detail


def test_journal_nudge_no_alert_empty_log_returns_ok(app_client):
    """journal_nudge() with no arg + empty run_log → no recent alert → 'ok'."""
    from modules.automation.service import journal_nudge

    status, detail = journal_nudge()
    assert status == "ok"
    assert "chưa có" in detail.lower() or "journal" in detail.lower()


def test_post_run_records_warn_status_in_get(app_client, monkeypatch):
    """A run that returns 'warn' is recorded + GET /routines reflects lastResult='warn'."""
    from modules.automation import service as auto
    monkeypatch.setitem(auto._CATALOG_BY_ID["pattern-check"], "func",
                        lambda: ("warn", "1 dự án build-to-90"))
    r = app_client.post("/routines/pattern-check/run")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "warn"
    routines = {x["id"]: x for x in app_client.get("/routines").json()["data"]["routines"]}
    assert routines["pattern-check"]["lastResult"] == "warn"
