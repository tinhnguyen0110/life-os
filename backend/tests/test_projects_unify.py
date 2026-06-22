"""tests/test_projects_unify.py — PROJECTS-UNIFY T2 (#113): auto-discover + hidden flag.

Projects had 2 repo sources (config built-ins + registered status.md); #113 adds a 3rd:
a .git repo under DEV_TRACING_ROOTS is AUTO-discovered as a project (no manual register),
with a hide/unhide for the ones you don't care about. The load-bearing distinguishing cases
(the dispatch's pass bar — each is a case where the right behavior ≠ a plausible-wrong one):

  - a roots-repo with NO status.md still lists with source="auto" + git-derived fields
    (the unify proof — git truth alone is enough; status.md is optional);
  - registered-id collides with an auto-repo → REGISTERED WINS, auto skipped (debug, no warn);
  - hide → excluded from default /projects, PRESENT in ?include=hidden; unhide → back;
  - 🔴 DEV_TRACING_ROOTS unset → list UNCHANGED (backward-compat — the must-not-break case);
  - hidden ≠ abandoned: two INDEPENDENT flags (abandon-orthogonal-to-health);
  - scoped write: hide writes ONLY that id's status.md (no other file touched);
  - the #112 slug-join still works on an auto-repo (auto id == dev_activity slug).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.projects import service as svc


# --------------------------------------------------------------------------- #
# real git repos on disk (the reader runs real git; auto-discover scans .git)    #
# --------------------------------------------------------------------------- #
def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "main.py").write_text("print(1)\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


@pytest.fixture
def roots(tmp_path, monkeypatch, isolated_paths):
    """A DEV_TRACING_ROOTS dir with two real .git child repos: 'OutboundOS' (raw case) and
    'DevCrew'. Returns the root Path. isolated_paths gives a clean DATA_DIR (no config built-ins
    unless the test adds them)."""
    root = tmp_path / "code"
    root.mkdir()
    _init_repo(root / "OutboundOS")
    _init_repo(root / "DevCrew")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    # no config built-ins by default — isolate the auto source
    monkeypatch.setattr(svc.settings, "project_repos", {}, raising=False)
    return root


# --------------------------------------------------------------------------- #
# auto-discover — a roots-repo with NO status.md is STILL a project (source=auto) #
# --------------------------------------------------------------------------- #
def test_auto_repo_without_status_md_is_a_project(roots):
    """THE UNIFY PROOF: a .git repo under DEV_TRACING_ROOTS, never manually registered (no
    status.md), appears in list_projects with source='auto' + git-derived fields."""
    statuses, _ = svc.list_projects()
    by_id = {s.id: s for s in statuses}
    assert "outboundos" in by_id, "auto-discovered repo must list (no status.md needed)"
    assert "devcrew" in by_id
    ob = by_id["outboundos"]
    assert ob.source == "auto"
    assert ob.hidden is False
    assert ob.metrics.commits >= 1  # git-derived, real
    assert ob.health in ("act", "slow", "stall", "dead")  # git-derived
    assert ob.desc is None  # human metadata is null (no status.md) — honest, not fabricated


def test_auto_repo_id_is_slug_of_basename(roots):
    """auto id = slug(basename) (lowercase) — so it matches dev_activity's slug-join (#112)
    AND collides correctly with registered/config ids."""
    repos = svc._tracked_repos()
    assert "outboundos" in repos and repos["outboundos"][1] == "auto"
    assert repos["outboundos"][0] == str(roots / "OutboundOS")  # raw-case path preserved


def test_get_project_resolves_auto_repo_case_insensitively(roots):
    """get_project (the #105 case-insensitive chokepoint) resolves an auto-repo by name/case."""
    for variant in ("outboundos", "OutboundOS", "OUTBOUNDOS"):
        st = svc.get_project(variant)
        assert st is not None and st.id == "outboundos" and st.source == "auto"


# --------------------------------------------------------------------------- #
# precedence — registered status.md > config > auto (collision → human wins)      #
# --------------------------------------------------------------------------- #
def test_registered_wins_over_auto_on_id_collision(roots):
    """A registered status.md for the SAME slug as an auto-repo → REGISTERED wins (source=
    registered), the auto entry is dropped (debug-log, not a warning)."""
    from store import md_store
    # register 'outboundos' pointing at a different path (the human truth)
    other = roots.parent / "registered-outbound"
    _init_repo(other)
    md_store.write_file("projects/outboundos/status.md",
                        f"---\nname: Outbound (registered)\nrepo: {other}\ndesc: human truth\n---\n",
                        "seed registered")
    repos = svc._tracked_repos()
    assert repos["outboundos"][1] == "registered", "registered must win the collision"
    assert repos["outboundos"][0] == str(other), "registered path wins (human truth)"
    st = svc.get_project("outboundos")
    assert st is not None and st.source == "registered" and st.desc == "human truth"


def test_config_wins_over_auto_on_id_collision(roots, monkeypatch):
    """A config built-in for the same slug as an auto-repo → config wins (source=config)."""
    cfg_path = roots.parent / "config-outbound"
    _init_repo(cfg_path)
    monkeypatch.setattr(svc.settings, "project_repos", {"outboundos": str(cfg_path)}, raising=False)
    repos = svc._tracked_repos()
    assert repos["outboundos"][1] == "config"
    assert repos["outboundos"][0] == str(cfg_path)


# --------------------------------------------------------------------------- #
# 🔴 backward-compat — DEV_TRACING_ROOTS unset → list UNCHANGED                  #
# --------------------------------------------------------------------------- #
def test_roots_unset_auto_source_empty(tmp_path, monkeypatch, isolated_paths):
    """THE MUST-NOT-BREAK case: DEV_TRACING_ROOTS unset → auto-source empty → the list is
    config+registered only (the pre-#113 behavior)."""
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)
    cfg = tmp_path / "only-config"
    _init_repo(cfg)
    monkeypatch.setattr(svc.settings, "project_repos", {"onlyconfig": str(cfg)}, raising=False)
    repos = svc._tracked_repos()
    # only the config built-in — no auto entries
    assert set(repos) == {"onlyconfig"}
    assert repos["onlyconfig"][1] == "config"


def test_auto_repos_empty_when_roots_unset(monkeypatch, isolated_paths):
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)
    assert svc._auto_repos() == {}


# --------------------------------------------------------------------------- #
# hide / unhide — excluded from default, present in ?include=hidden               #
# --------------------------------------------------------------------------- #
def test_hide_excludes_from_default_list_present_in_include_hidden(roots):
    st = svc.hide_project("outboundos")
    assert st is not None and st.hidden is True
    default_ids = {s.id for s in svc.list_projects()[0]}
    assert "outboundos" not in default_ids, "hidden → excluded from default list"
    assert "devcrew" in default_ids, "the OTHER repo is unaffected"
    incl_ids = {s.id for s in svc.list_projects(include_hidden=True)[0]}
    assert "outboundos" in incl_ids, "?include=hidden must show the hidden project"


def test_unhide_restores_to_default_list(roots):
    svc.hide_project("outboundos")
    assert "outboundos" not in {s.id for s in svc.list_projects()[0]}
    st = svc.unhide_project("outboundos")
    assert st is not None and st.hidden is False
    assert "outboundos" in {s.id for s in svc.list_projects()[0]}, "unhide → back in default"


def test_hide_is_idempotent(roots):
    svc.hide_project("outboundos")
    # hiding again is a no-op (still hidden, no crash)
    st = svc.hide_project("outboundos")
    assert st is not None and st.hidden is True


def test_unhide_not_hidden_is_noop(roots):
    """unhiding a project that was never hidden → 200 no-op (returns it, hidden=False)."""
    st = svc.unhide_project("devcrew")
    assert st is not None and st.hidden is False


def test_hide_unknown_id_returns_none(roots):
    assert svc.hide_project("no-such-project") is None
    assert svc.unhide_project("no-such-project") is None


# --------------------------------------------------------------------------- #
# hidden ≠ abandoned — two INDEPENDENT flags (abandon-orthogonal-to-health)       #
# --------------------------------------------------------------------------- #
def test_hidden_and_abandoned_are_independent(roots):
    """hide one repo, abandon another → list_projects excludes BOTH; graveyard has ONLY the
    abandoned; ?include=hidden shows the hidden but NOT the abandoned."""
    from modules.projects.schema import ProjectAbandonInput
    svc.hide_project("outboundos")
    svc.abandon_project("devcrew", ProjectAbandonInput(reason="dead, learned X"))

    default_ids = {s.id for s in svc.list_projects()[0]}
    assert "outboundos" not in default_ids and "devcrew" not in default_ids  # both excluded

    # graveyard = abandoned ONLY (the hidden one is NOT in the graveyard)
    grave_ids = {st.id for st, _meta in svc.list_abandoned()[0]}
    assert grave_ids == {"devcrew"}, "graveyard is abandoned-only, never hidden"

    # ?include=hidden shows the hidden one, NOT the abandoned (abandoned stays excluded)
    incl_ids = {s.id for s in svc.list_projects(include_hidden=True)[0]}
    assert "outboundos" in incl_ids
    assert "devcrew" not in incl_ids, "abandoned stays out of include=hidden too"


# --------------------------------------------------------------------------- #
# scoped write — hide writes ONLY that id's status.md                            #
# --------------------------------------------------------------------------- #
def test_hide_is_scoped_writes_only_that_id(roots):
    """hide('outboundos') must create ONLY projects/outboundos/status.md — never touch devcrew
    (which has no status.md and must STILL have none)."""
    from store import md_store
    assert not md_store.exists("projects/outboundos/status.md")
    assert not md_store.exists("projects/devcrew/status.md")
    svc.hide_project("outboundos")
    assert md_store.exists("projects/outboundos/status.md"), "hide creates the minimal status.md"
    assert not md_store.exists("projects/devcrew/status.md"), "NO status.md spam for other repos"


def test_hide_preserves_existing_status_md_fields(roots):
    """hide on a repo that ALREADY has a status.md sets hidden:true but preserves other fields."""
    from store import md_store
    md_store.write_file("projects/devcrew/status.md",
                        f"---\nname: Dev Crew\nrepo: {roots / 'DevCrew'}\ndesc: keep me\nprogress: 42\n---\n",
                        "seed")
    svc.hide_project("devcrew")
    meta = svc._load_meta("devcrew")
    assert meta.get("hidden") is True
    assert meta.get("desc") == "keep me" and meta.get("progress") == 42  # preserved


# --------------------------------------------------------------------------- #
# #112 slug-join still works on an auto-repo (the unify payoff)                   #
# --------------------------------------------------------------------------- #
def test_auto_repo_dev_stat_joins_by_slug(roots):
    """An auto-discovered repo's #112 dev-stat joins by slug — seed a dev_activity row for the
    RAW-case basename, the auto-project (slug id) joins to it."""
    from datetime import timedelta
    from modules.dev_activity import service as dev_service
    from modules.dev_activity import store as dev_store
    dev_store.init_dev_activity_tables()
    today = (dev_service._now().astimezone(dev_service.VN_TZ).date()).strftime("%Y-%m-%d")
    dev_store.upsert_day(date=today, repo="OutboundOS", source="you", commits=4,
                         loc_added=10, loc_deleted=2, first_ts=None, last_ts=None)
    stat = svc.dev_stat_for_project("outboundos", days=7)
    assert stat.found is True and stat.commits == 4  # the auto-project joins dev_activity by slug


# --------------------------------------------------------------------------- #
# cache — an auto-repo caches + a hide invalidates (status.md mtime in the key)   #
# --------------------------------------------------------------------------- #
def test_auto_repo_cache_then_hide_invalidates(roots):
    """read_one caches the auto-repo; hide writes status.md → the cache key (which includes
    status.md mtime) changes → next read reflects hidden=True (no stale cache)."""
    st1 = svc.get_project("outboundos")
    assert st1 is not None and st1.hidden is False  # cached
    svc.hide_project("outboundos")
    st2 = svc.get_project("outboundos")
    assert st2 is not None and st2.hidden is True, "hide must invalidate the cached read"


# --------------------------------------------------------------------------- #
# REST API — the endpoints (the #113 surface; REST-only, no MCP this task)        #
# --------------------------------------------------------------------------- #
@pytest.fixture
def api(roots):
    from fastapi.testclient import TestClient
    from main import create_app
    return TestClient(create_app())


def test_rest_list_includes_auto_with_source(api):
    """GET /projects lists the auto-repos, each tagged source='auto'."""
    body = api.get("/projects").json()
    projects = {p["id"]: p for p in body["data"]["projects"]}
    assert "outboundos" in projects
    assert projects["outboundos"]["source"] == "auto"
    assert projects["outboundos"]["hidden"] is False


def test_rest_hide_then_default_excludes_include_shows(api):
    """POST /hide → gone from default GET /projects, present in ?include=hidden; /unhide → back."""
    r = api.post("/projects/outboundos/hide")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["hidden"] is True

    default_ids = {p["id"] for p in api.get("/projects").json()["data"]["projects"]}
    assert "outboundos" not in default_ids

    incl_ids = {p["id"] for p in api.get("/projects?include=hidden").json()["data"]["projects"]}
    assert "outboundos" in incl_ids

    r2 = api.post("/projects/outboundos/unhide")
    assert r2.status_code == 200 and r2.json()["data"]["hidden"] is False
    assert "outboundos" in {p["id"] for p in api.get("/projects").json()["data"]["projects"]}


def test_rest_hide_unknown_id_is_404(api):
    r = api.post("/projects/ghost/hide")
    assert r.status_code == 404
    # agent-readable error: nested {error:{code,message,hint,retryable}}
    err = r.json()["error"]
    assert err["code"] == "NOT_FOUND" and err["hint"] and err["retryable"] is False


def test_rest_unhide_unknown_id_is_404(api):
    r = api.post("/projects/ghost/unhide")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
