"""tests/test_notes_api.py — Notes router integration (Sprint 6 T2).

Real app via TestClient, notes auto-mounted. All 5 endpoints, envelope, status
codes (404/422), /health discovery, filter query params.
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
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as main_mod
    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


# --- discovery ---
def test_health_lists_notes_module(app_client):
    assert "notes" in app_client.get("/health").json()["data"]["modules"]


def test_health_no_skipped_modules(app_client):
    assert not app_client.get("/health").json().get("warning")


# --- CRUD ---
def test_create_get_roundtrip(app_client):
    r = app_client.post("/notes", json={"title": "Hello", "body": "world", "tags": ["x"]})
    assert r.status_code == 200 and r.json()["success"] is True
    nid = r.json()["data"]["id"]
    assert nid.startswith("hello-")
    got = app_client.get(f"/notes/{nid}").json()["data"]
    assert got["title"] == "Hello" and got["body"] == "world" and got["tags"] == ["x"]


def test_get_404(app_client):
    r = app_client.get("/notes/nope-000000")
    assert r.status_code == 404
    j = r.json()  # #46-P5: flat agent_error, not {detail}
    assert "detail" not in j and j["error"]["code"] == "NOT_FOUND" and j["error"]["hint"]


def test_create_422_empty_title(app_client):
    assert app_client.post("/notes", json={"title": ""}).status_code == 422


def test_create_422_attached_without_id(app_client):
    assert app_client.post("/notes", json={"title": "X", "attach": {"type": "project"}}).status_code == 422


def test_update_in_place(app_client):
    nid = app_client.post("/notes", json={"title": "Edit", "body": "v1"}).json()["data"]["id"]
    r = app_client.put(f"/notes/{nid}", json={"title": "Edit", "body": "v2"})
    assert r.status_code == 200
    assert app_client.get(f"/notes/{nid}").json()["data"]["body"] == "v2"


def test_update_404(app_client):
    assert app_client.put("/notes/nope-000000", json={"title": "X"}).status_code == 404


def test_delete(app_client):
    nid = app_client.post("/notes", json={"title": "Doomed"}).json()["data"]["id"]
    assert app_client.delete(f"/notes/{nid}").status_code == 200
    assert app_client.get(f"/notes/{nid}").status_code == 404


def test_delete_404(app_client):
    assert app_client.delete("/notes/ghost-000000").status_code == 404


# --- list + filters ---
def test_list_and_filters(app_client):
    app_client.post("/notes", json={"title": "Alpha", "body": "quick fox", "tags": ["zebra"]})
    app_client.post("/notes", json={"title": "Beta", "attach": {"type": "project", "ref": "devcrew"}})
    all_notes = app_client.get("/notes").json()["data"]
    assert len(all_notes) == 2
    assert [n["title"] for n in app_client.get("/notes?q=quick").json()["data"]] == ["Alpha"]
    assert [n["title"] for n in app_client.get("/notes?tag=zebra").json()["data"]] == ["Alpha"]
    assert [n["title"] for n in app_client.get("/notes?attached=project:devcrew").json()["data"]] == ["Beta"]


def test_get_by_id_wins_over_list(app_client):
    """GET /notes/{id} must not be shadowed; /notes (no id) is the list."""
    nid = app_client.post("/notes", json={"title": "Solo"}).json()["data"]["id"]
    assert app_client.get(f"/notes/{nid}").json()["data"]["id"] == nid
    assert isinstance(app_client.get("/notes").json()["data"], list)
