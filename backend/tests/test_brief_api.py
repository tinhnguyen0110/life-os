"""tests/test_brief_api.py — Brief router integration (S11).

Real app via TestClient (scheduler disabled). GET /brief always 200 (fail-soft per
source), GET /brief/history → [] when nothing persisted. Envelope shape + the locked
Brief fields.
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


def test_health_lists_brief_module(app_client):
    assert "brief" in app_client.get("/health").json()["data"]["modules"]


def test_get_brief_shape(app_client):
    body = app_client.get("/brief").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) >= {"generatedAt", "asOf", "source", "summary", "priorities", "stale", "warnings"}
    assert d["source"] == "template"  # NOT an AI model label
    assert set(d["summary"]) == {"netWorth", "projectsActive", "claudePct", "alertsToday"}
    assert isinstance(d["priorities"], list)


def test_get_brief_always_200_failsoft(app_client):
    """Empty env (no projects/holdings) → still 200, honest summary, no crash."""
    r = app_client.get("/brief")
    assert r.status_code == 200
    d = r.json()["data"]
    # no data → honest-empty priorities + zero/None summary
    assert d["priorities"] == [] or all("n" in p for p in d["priorities"])
    assert d["summary"]["projectsActive"] == 0


def test_get_brief_history_empty(app_client):
    r = app_client.get("/brief/history")
    assert r.status_code == 200
    assert r.json()["data"] == []  # nothing persisted yet → [], not 404
