"""tests/test_projects_api.py — Projects router integration tests (Sprint 1 T2/T3).

Drives the real FastAPI app via TestClient with the projects module auto-mounted
through the registry. Covers all 5 endpoints + the locked envelope, status codes,
the health summary, /health discovery, and the wiki-refresh routine registration.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# --------------------------------------------------------------------------- #
# Fixtures — isolated DATA_DIR + a real registered git repo + a live app.       #
# --------------------------------------------------------------------------- #
def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "app.py").write_text("print('hi')\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """A TestClient with isolated DATA_DIR + one real repo registered as 'demo'."""
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)

    repo = tmp_path / "demo"
    _init_repo(repo)
    monkeypatch.setattr(settings, "project_repos", {"demo": str(repo)})

    db.close_db()
    import main as main_mod

    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        c._repo_path = str(repo)  # type: ignore[attr-defined]
        yield c
    db.close_db()


# --------------------------------------------------------------------------- #
# Discovery — module + routine appear in /health (auto-mount, no core edit)      #
# --------------------------------------------------------------------------- #
def test_health_lists_projects_module(app_client):
    body = app_client.get("/health").json()
    assert "projects" in body["data"]["modules"]


def test_health_lists_wiki_refresh_routine(app_client):
    body = app_client.get("/health").json()
    assert "wiki-refresh" in body["data"]["routines"]


def test_health_no_skipped_modules(app_client):
    body = app_client.get("/health").json()
    assert not body.get("warning"), f"module skipped at boot: {body.get('warning')}"


# --------------------------------------------------------------------------- #
# GET /projects — list + summary + envelope                                     #
# --------------------------------------------------------------------------- #
def test_list_envelope_and_summary(app_client):
    resp = app_client.get("/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"]["projects"], list)
    summary = body["data"]["summary"]
    assert set(summary) == {"act", "slow", "stall", "dead", "total"}
    assert summary["total"] == len(body["data"]["projects"])


def test_list_item_has_frozen_shape_and_routine(app_client):
    body = app_client.get("/projects").json()
    items = body["data"]["projects"]
    assert items, "demo project should be listed"
    required = {"id", "name", "desc", "health", "progress", "users", "last",
                "lastDays", "next", "repo", "metrics", "routines", "lastAuto"}
    for item in items:
        assert not (required - set(item)), f"missing keys: {required - set(item)}"
        assert "wiki-refresh" in item["routines"]
        assert item["health"] in {"act", "slow", "stall", "dead"}


# --------------------------------------------------------------------------- #
# GET /projects/{id} — detail + 404                                             #
# --------------------------------------------------------------------------- #
def test_get_detail_200(app_client):
    body = app_client.get("/projects/demo").json()
    assert body["success"] is True
    assert body["data"]["id"] == "demo"
    assert body["data"]["health"] == "act"


def test_get_detail_404(app_client):
    resp = app_client.get("/projects/nope-not-here")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# POST /projects — register, 400 non-git, 409 collision, 422 bad body           #
# --------------------------------------------------------------------------- #
def test_register_201_style(app_client, tmp_path):
    newrepo = tmp_path / "Fresh App"
    _init_repo(newrepo)
    resp = app_client.post("/projects", json={"name": "Fresh App", "repo": str(newrepo), "goal": "ship"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == "fresh-app"
    assert body["data"]["desc"] == "ship"
    assert body["data"]["health"] == "act"


def test_register_400_non_git(app_client, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    resp = app_client.post("/projects", json={"name": "Plain", "repo": str(plain)})
    assert resp.status_code == 400


def test_register_409_collision(app_client, tmp_path):
    repo = tmp_path / "Dup"
    _init_repo(repo)
    first = app_client.post("/projects", json={"name": "Dup", "repo": str(repo)})
    assert first.status_code == 200
    second = app_client.post("/projects", json={"name": "Dup", "repo": str(repo)})
    assert second.status_code == 409


def test_register_422_missing_field(app_client):
    resp = app_client.post("/projects", json={"name": "NoRepo"})  # missing repo
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# POST /projects/{id}/refresh — lastAuto + 404                                  #
# --------------------------------------------------------------------------- #
def test_refresh_sets_last_auto(app_client):
    body = app_client.post("/projects/demo/refresh").json()
    assert body["success"] is True
    assert body["data"]["lastAuto"] is not None


def test_refresh_404(app_client):
    resp = app_client.post("/projects/ghost/refresh")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# POST /projects/{id}/abandon — graveyard flag, orthogonal to health, 404       #
# --------------------------------------------------------------------------- #
def test_abandon_then_excluded_from_list_but_detail_works(app_client):
    resp = app_client.post("/projects/demo/abandon", json={"reason": "pivot", "atProgress": 40})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    # health is NOT forced to dead by abandon (orthogonal)
    assert body["data"]["health"] == "act"
    # excluded from list
    listing = app_client.get("/projects").json()
    assert all(p["id"] != "demo" for p in listing["data"]["projects"])
    # but detail still returns it
    detail = app_client.get("/projects/demo")
    assert detail.status_code == 200


def test_abandon_404(app_client):
    resp = app_client.post("/projects/ghost/abandon", json={"reason": "x"})
    assert resp.status_code == 404


def test_abandon_422_missing_reason(app_client):
    resp = app_client.post("/projects/demo/abandon", json={})  # reason required
    assert resp.status_code == 422
