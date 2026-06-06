"""tests/test_graveyard_api.py — Graveyard + restore router integration (Sprint 8).

Real app via TestClient. /health discovery, GET /graveyard envelope, abandon w/
lesson → graveyard, POST /projects/{id}/restore (200 / 404 / no-op).
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)

    repo = tmp_path / "DemoProj"
    _init_repo(repo)
    monkeypatch.setattr(settings, "project_repos", {"demo": str(repo)})

    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


# --- discovery ---
def test_health_lists_graveyard(app_client):
    assert "graveyard" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped(app_client):
    assert not app_client.get("/health").json().get("warning")


# --- GET /graveyard ---
def test_graveyard_empty_envelope(app_client):
    body = app_client.get("/graveyard").json()
    assert body["success"] is True
    d = body["data"]
    assert set(d) == {"graves", "count", "avgPeak", "commonReasons", "reachedUser", "beforeUser", "lessons"}
    assert d["count"] == 0 and d["graves"] == []


def test_abandon_with_lesson_then_graveyard(app_client):
    r = app_client.post("/projects/demo/abandon", json={"reason": "pivot", "atProgress": 60, "lesson": "ship smaller"})
    assert r.status_code == 200
    d = app_client.get("/graveyard").json()["data"]
    assert d["count"] == 1
    g = d["graves"][0]
    assert g["id"] == "demo" and g["reason"] == "pivot" and g["lesson"] == "ship smaller" and g["peak"] == 60
    assert d["lessons"] == ["ship smaller"]


def test_abandon_without_lesson_null_in_graveyard(app_client):
    app_client.post("/projects/demo/abandon", json={"reason": "pivot"})
    g = app_client.get("/graveyard").json()["data"]["graves"][0]
    assert g["lesson"] is None


# --- POST /projects/{id}/restore ---
def test_restore_round_trip(app_client):
    app_client.post("/projects/demo/abandon", json={"reason": "x", "lesson": "y"})
    assert app_client.get("/graveyard").json()["data"]["count"] == 1
    r = app_client.post("/projects/demo/restore")
    assert r.status_code == 200 and r.json()["data"]["id"] == "demo"
    # gone from graveyard, back in projects list
    assert app_client.get("/graveyard").json()["data"]["count"] == 0
    assert any(p["id"] == "demo" for p in app_client.get("/projects").json()["data"]["projects"])


def test_restore_404_unknown(app_client):
    assert app_client.post("/projects/ghost/restore").status_code == 404


def test_restore_non_abandoned_noop_200(app_client):
    # demo is registered but not abandoned → no-op 200
    assert app_client.post("/projects/demo/restore").status_code == 200


def test_abandon_422_empty_reason(app_client):
    assert app_client.post("/projects/demo/abandon", json={"reason": ""}).status_code == 422
