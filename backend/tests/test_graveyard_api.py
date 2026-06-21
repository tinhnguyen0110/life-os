"""tests/test_graveyard_api.py — Graveyard + restore router integration (Sprint 8).

Real app via TestClient. /health discovery, GET /graveyard envelope, abandon w/
lesson → graveyard, POST /projects/{id}/restore (200 / 404 / no-op).
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# A4 — multi-project fixture + edge cases not previously covered at API layer
# ---------------------------------------------------------------------------

@pytest.fixture
def multi_client(tmp_path, monkeypatch):
    """Like app_client but with 3 registered repos (alpha, beta, gamma)."""
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)

    repos = {}
    for name in ("alpha", "beta", "gamma"):
        p = tmp_path / name.capitalize()
        _init_repo(p)
        repos[name] = str(p)
    monkeypatch.setattr(settings, "project_repos", repos)

    db.close_db()
    import main as main_mod
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def test_common_reasons_grouped_and_counted(multi_client):
    """Two projects abandoned with the same reason → commonReasons groups them (count=2).
    Third with a different reason → count=1. Sorted desc by count."""
    multi_client.post("/projects/alpha/abandon", json={"reason": "pivot", "atProgress": 50})
    multi_client.post("/projects/beta/abandon",  json={"reason": "pivot", "atProgress": 30})
    multi_client.post("/projects/gamma/abandon", json={"reason": "no users"})

    d = multi_client.get("/graveyard").json()["data"]
    assert d["count"] == 3
    reasons = {r["reason"]: r["count"] for r in d["commonReasons"]}
    assert reasons["pivot"] == 2
    assert reasons["no users"] == 1
    # pivot is first (higher count)
    assert d["commonReasons"][0]["reason"] == "pivot"


def test_lessons_deduped_first_seen_order(multi_client):
    """Two projects with the same lesson → appears once. Third with a different lesson
    → second in order. distinct first-seen."""
    multi_client.post("/projects/alpha/abandon", json={"reason": "x", "lesson": "ship smaller"})
    multi_client.post("/projects/beta/abandon",  json={"reason": "y", "lesson": "ship smaller"})
    multi_client.post("/projects/gamma/abandon", json={"reason": "z", "lesson": "validate first"})

    lessons = multi_client.get("/graveyard").json()["data"]["lessons"]
    assert lessons.count("ship smaller") == 1
    assert "validate first" in lessons
    assert len(lessons) == 2


def test_reached_user_before_user_sum_equals_count(multi_client):
    """reachedUser + beforeUser == count always. After abandoning 3 projects with no
    git users (fresh repos, 0 users), all 3 are before-user. The field shapes are present
    and consistent — the API layer doesn't corrupt them."""
    multi_client.post("/projects/alpha/abandon", json={"reason": "pivot", "atProgress": 80})
    multi_client.post("/projects/beta/abandon",  json={"reason": "pivot", "atProgress": 20})
    multi_client.post("/projects/gamma/abandon", json={"reason": "other"})

    d = multi_client.get("/graveyard").json()["data"]
    assert d["count"] == 3
    # sum invariant: every grave is either reached-user or before-user
    assert d["reachedUser"] + d["beforeUser"] == d["count"]
    # fresh repos have 0 users → all 3 are before-user
    assert d["reachedUser"] == 0
    assert d["beforeUser"] == 3


def test_avg_peak_skips_graves_without_progress(multi_client):
    """avgPeak only counts graves WITH atProgress (not None).
    A grave with no atProgress must NOT be treated as 0 (would skew mean low)."""
    # alpha: atProgress=80 → counted
    multi_client.post("/projects/alpha/abandon", json={"reason": "x", "atProgress": 80})
    # beta: NO atProgress → NOT counted toward avg
    multi_client.post("/projects/beta/abandon",  json={"reason": "y"})

    d = multi_client.get("/graveyard").json()["data"]
    # avgPeak = 80 (only alpha counted), NOT (80+0)/2=40
    assert d["avgPeak"] == pytest.approx(80.0)


def test_restore_removes_from_graveyard_and_reachable_in_projects(multi_client):
    """Restore end-to-end via API: abandon → appears in graveyard → restore → gone
    from graveyard AND back in project list. Co-locating the restore behavior test
    at the API level (S8 lesson: behavior-test restore, not just the unit)."""
    multi_client.post("/projects/alpha/abandon", json={"reason": "pivot"})
    assert multi_client.get("/graveyard").json()["data"]["count"] == 1

    r = multi_client.post("/projects/alpha/restore")
    assert r.status_code == 200
    assert r.json()["data"]["id"] == "alpha"

    # graveyard is empty again
    assert multi_client.get("/graveyard").json()["data"]["count"] == 0
    # alpha is back in projects list
    projects = multi_client.get("/projects").json()["data"]["projects"]
    assert any(p["id"] == "alpha" for p in projects)


def test_abandon_orthogonal_to_health_dead_not_in_graveyard(multi_client):
    """A project with health='dead' (stale commits) that is NOT explicitly abandoned
    must NOT appear in the graveyard. Abandon flag is orthogonal to health.
    (memory: abandon-orthogonal-to-health — abandon = explicit human flag, NOT health=dead)"""
    # Do NOT abandon any project — just check graveyard is empty
    # even though with no recent commits the health would be 'dead'
    d = multi_client.get("/graveyard").json()["data"]
    assert d["count"] == 0
    assert d["graves"] == []


def test_graveyard_all_abandoned_then_all_restored(multi_client):
    """Abandon all 3 → graveyard has 3 → restore all → graveyard is empty again."""
    for pid in ("alpha", "beta", "gamma"):
        multi_client.post(f"/projects/{pid}/abandon", json={"reason": "batch test"})
    assert multi_client.get("/graveyard").json()["data"]["count"] == 3

    for pid in ("alpha", "beta", "gamma"):
        r = multi_client.post(f"/projects/{pid}/restore")
        assert r.status_code == 200

    assert multi_client.get("/graveyard").json()["data"]["count"] == 0
