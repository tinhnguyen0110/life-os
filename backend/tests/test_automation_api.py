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
    assert d["total"] == 6
    ids = {r["id"] for r in d["routines"]}
    assert ids == {"market-poll", "wiki-refresh", "idle-hunter", "pattern-check", "journal-nudge", "morning-pull"}
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
    assert app_client.get("/routines").json()["data"]["activeCount"] == 5  # one off


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
