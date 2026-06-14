"""tests/test_brief_api.py — Brief router integration (S11).

Real app via TestClient (scheduler disabled). GET /brief always 200 (fail-soft per
source), GET /brief/history → [] when nothing persisted. Envelope shape + the locked
Brief fields.

A4 additions: None sections (sources down), history round-trip via save_brief,
limit param, rule-raises-still-200, all-sources-down summary fields.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# A4 — edge cases / error paths not previously covered
# ---------------------------------------------------------------------------

def test_get_brief_all_sources_down_still_200(app_client):
    """When ALL source modules raise, the brief is still 200 + honest-empty summary."""
    from modules.brief import reader as brief_reader
    from modules.brief.reader import Sources

    # Make pull() return a Sources where every source is None (all failed)
    def _all_down():
        return Sources(warnings=["projects nguồn lỗi (RuntimeError)",
                                  "finance nguồn lỗi (RuntimeError)",
                                  "market nguồn lỗi (RuntimeError)",
                                  "claude nguồn lỗi (RuntimeError)"])

    with patch.object(brief_reader, "pull", side_effect=_all_down):
        r = app_client.get("/brief")

    assert r.status_code == 200
    d = r.json()["data"]
    # all sources None → honest zeros, not fabricated values
    assert d["summary"]["projectsActive"] == 0
    assert d["summary"]["netWorth"] is None
    assert d["summary"]["claudePct"] is None
    assert d["summary"]["alertsToday"] == 0
    assert d["priorities"] == []


def test_get_brief_source_down_warning_present(app_client):
    """A failing source results in a non-empty warning in the response."""
    from modules.brief import reader as brief_reader
    from modules.brief.reader import Sources

    def _one_down():
        return Sources(
            projects=None,
            warnings=["projects nguồn lỗi (ImportError)"],
        )

    with patch.object(brief_reader, "pull", side_effect=_one_down):
        r = app_client.get("/brief")

    assert r.status_code == 200
    body = r.json()
    # warning key present at the envelope level when any source fails
    assert body.get("warning") is not None
    assert "projects" in body["warning"]


def test_get_brief_rule_raises_still_200_rule_failure_in_warning(app_client):
    """A rule that raises internally does NOT abort the brief — still 200.
    The rule failure is captured in warnings."""
    from modules.brief import service as brief_svc

    original_market_priority = brief_svc._market_priority

    def _rule_explodes(market):
        raise RuntimeError("rule internal crash")

    with patch.object(brief_svc, "_market_priority", side_effect=_rule_explodes):
        r = app_client.get("/brief")

    assert r.status_code == 200
    d = r.json()["data"]
    # the rule failure is surfaced in warnings (not silently swallowed)
    combined_warnings = " ".join(d.get("warnings", []))
    assert "market" in combined_warnings


def test_get_brief_summary_projects_active_counts_act_and_slow(app_client):
    """projectsActive counts projects with health 'act' or 'slow', not 'dead' or abandoned."""
    from modules.brief import reader as brief_reader
    from modules.brief.reader import Sources

    class FakeProject:
        def __init__(self, name, health):
            self.name = name
            self.health = health
            self.progress = 0
            self.users = 0
            self.lastDays = 0
            self.abandoned = False

    def _with_projects():
        return Sources(projects=[
            FakeProject("active-proj", "act"),
            FakeProject("slow-proj", "slow"),
            FakeProject("dead-proj", "dead"),
        ])

    with patch.object(brief_reader, "pull", side_effect=_with_projects):
        r = app_client.get("/brief")

    assert r.status_code == 200
    # only act + slow count (2), not dead (1)
    assert r.json()["data"]["summary"]["projectsActive"] == 2


def test_brief_history_round_trip_save_and_read(tmp_path, monkeypatch):
    """save_brief() persists a brief; get_history() reads it back (newest-first)."""
    import importlib
    from core.config import settings
    from store import db, md_store

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(settings, "project_repos", {})
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()

    import main as main_mod
    importlib.reload(main_mod)
    main_mod.create_app()  # init the store

    from modules.brief import service as brief_svc
    importlib.reload(brief_svc)  # reload so it picks up the patched data_dir

    # save_brief writes to md_store and returns the path
    saved_path = brief_svc.save_brief()
    assert saved_path.startswith("brief/")
    assert saved_path.endswith(".md")

    # get_history should now return the saved brief
    history = brief_svc.get_history()
    assert len(history) == 1
    b = history[0]
    assert b.source == "template"
    assert isinstance(b.priorities, list)
    assert isinstance(b.summary.projectsActive, int)
    db.close_db()


def test_brief_history_api_returns_saved_briefs(app_client, tmp_path, monkeypatch):
    """After save_brief() is called, GET /brief/history returns the saved entries."""
    from modules.brief import service as brief_svc

    # Write a brief directly then check the API returns it
    brief_svc.save_brief()

    r = app_client.get("/brief/history")
    assert r.status_code == 200
    history = r.json()["data"]
    assert len(history) >= 1
    assert history[0]["source"] == "template"


def test_brief_history_limit_respected(tmp_path, monkeypatch):
    """get_history(limit=N) returns at most N entries even if more are persisted."""
    import importlib
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
    main_mod.create_app()

    from modules.brief import service as brief_svc
    importlib.reload(brief_svc)

    # Write 3 briefs with different "dates" by overriding generatedAt
    from modules.brief.schema import Brief, BriefSummary

    for date in ["2026-01-01", "2026-01-02", "2026-01-03"]:
        b = Brief(
            generatedAt=f"{date}T12:00:00+00:00",
            asOf=f"{date}T12:00:00+00:00",
            source="template",
            summary=BriefSummary(),
            priorities=[],
            stale=False,
            warnings=[],
        )
        brief_svc.save_brief(b)

    # limit=2 → max 2 returned
    limited = brief_svc.get_history(limit=2)
    assert len(limited) == 2
    # newest-first: 2026-01-03 should be first
    assert limited[0].generatedAt.startswith("2026-01-03")
    db.close_db()


def test_brief_history_malformed_file_skipped(tmp_path, monkeypatch):
    """A corrupt .md file in the history dir is skipped; valid files still returned."""
    import importlib
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
    main_mod.create_app()

    from modules.brief import service as brief_svc
    importlib.reload(brief_svc)

    # Write a valid brief first
    brief_svc.save_brief()

    # Inject a corrupt file directly into the brief dir
    hist_dir = settings.data_dir / "brief"
    hist_dir.mkdir(parents=True, exist_ok=True)
    corrupt = hist_dir / "2026-00-01.md"
    corrupt.write_text("not yaml frontmatter at all {{{{ broken")

    # get_history skips the corrupt file + returns the valid one (fail-open per file)
    history = brief_svc.get_history()
    assert len(history) >= 1  # the valid brief is returned
    # no crash — confirmed by reaching this line

    db.close_db()
