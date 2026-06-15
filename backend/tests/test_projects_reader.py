"""tests/test_projects_reader.py — projects git-reader + schema + service (Sprint 1).

Covers the architect's Logic block verbatim:
  - health buckets from lastDays (act ≤7 / slow ≤30 / stall ≤90 / dead >90|unreadable)
  - id = slug(folder); name/desc/progress/next/users from status.md only (no fabrication)
  - metrics commits/branch/lang from read-only git; testPass/stars = None
  - fail-open dead on missing/non-git/empty repo (NEVER raises)
  - READ-ONLY HARD INVARIANT: reader issues zero mutating git ops
  - service write paths: register / abandon (graveyard) / refresh (lastAuto)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.projects import reader, service
from modules.projects.reader import _git, _health_from_days, _READ_ONLY_GIT, slug
from modules.projects.schema import (
    ProjectAbandonInput,
    ProjectMetrics,
    ProjectRegisterInput,
    ProjectStatus,
)
from modules.projects.service import parse_front_matter


# --------------------------------------------------------------------------- #
# Local git fixtures — build real repos on disk so the reader runs real git.   #
# --------------------------------------------------------------------------- #
def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)


def _commit(path: Path, fname: str, content: str, *, date: str | None = None) -> None:
    (path / fname).write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    env = None
    if date is not None:
        import os

        env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    subprocess.run(["git", "commit", "-q", "-m", f"add {fname}"], cwd=path, check=True, env=env)


@pytest.fixture
def active_repo(tmp_path: Path) -> Path:
    """A repo whose last commit is 'now' (health act). Folder name 'active'."""
    repo = tmp_path / "active"
    _init_repo(repo)
    _commit(repo, "main.py", "print(1)\n")
    _commit(repo, "util.py", "x = 2\n")
    return repo


@pytest.fixture
def stall_repo(tmp_path: Path) -> Path:
    """A repo whose last commit is ~60 days ago (health stall)."""
    repo = tmp_path / "stall"
    _init_repo(repo)
    from datetime import datetime, timedelta, timezone

    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    _commit(repo, "old.go", "package main\n", date=old)
    return repo


# --------------------------------------------------------------------------- #
# slug (id derivation)                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "folder,expected",
    [
        ("OutboundOS", "outboundos"),
        ("claude-code-agents-ui", "claude-code-agents-ui"),
        ("life-os", "life-os"),
        ("My Project!!", "my-project"),
        ("___", "project"),  # all-non-alnum → safe fallback
    ],
)
def test_slug(folder, expected):
    assert slug(folder) == expected


# --------------------------------------------------------------------------- #
# health bucket logic (Logic block thresholds — verbatim)                       #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "days,expected",
    [
        (0, "act"), (7, "act"),
        (8, "slow"), (30, "slow"),
        (31, "stall"), (90, "stall"),
        (91, "dead"), (1000, "dead"),
        (None, "dead"),  # unknown → fail-open dead
    ],
)
def test_health_buckets(days, expected):
    assert _health_from_days(days) == expected


def test_active_repo_is_act(active_repo):
    st = reader.read_project(str(active_repo))
    assert isinstance(st, ProjectStatus)
    assert st.id == "active"  # derived from folder name
    assert st.name == "active"  # no status.md → folder name
    assert st.health == "act"
    assert st.lastDays is not None and st.lastDays <= 7
    assert st.last is not None
    assert st.metrics.commits == 2
    assert st.metrics.branch in ("main", "master")
    assert st.metrics.lang == "Python"
    assert st.metrics.testPass is None and st.metrics.stars is None


def test_stall_repo_bucket(stall_repo):
    st = reader.read_project(str(stall_repo))
    assert st.health == "stall"
    assert st.lastDays is not None and 30 < st.lastDays <= 90
    assert st.metrics.lang == "Go"


# --------------------------------------------------------------------------- #
# Defensive cases (MANDATORY) — fail-open, never raise                          #
# --------------------------------------------------------------------------- #
def test_missing_path_fails_open_dead(tmp_path):
    st = reader.read_project(str(tmp_path / "does-not-exist"))
    assert st.health == "dead"
    assert st.last is None and st.lastDays is None
    assert st.metrics.commits == 0 and st.metrics.branch == "" and st.metrics.lang is None
    assert st.progress is None and st.users == 0 and st.next is None and st.desc is None


def test_non_git_directory_is_dead(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "readme.txt").write_text("hi")
    st = reader.read_project(str(plain))
    assert st.health == "dead"
    assert st.metrics.commits == 0


def test_empty_repo_no_commits_is_dead(tmp_path):
    repo = tmp_path / "empty"
    _init_repo(repo)  # git init, no commits (unborn HEAD)
    st = reader.read_project(str(repo))
    assert st.health == "dead"
    assert st.last is None and st.lastDays is None
    assert st.metrics.commits == 0


def test_reader_never_raises_on_garbage_path():
    st = reader.read_project("/this/cannot/possibly/exist/ever")
    assert st.health == "dead"


# --------------------------------------------------------------------------- #
# Human fields come ONLY from meta — never fabricated from git                  #
# --------------------------------------------------------------------------- #
def test_human_fields_from_meta(active_repo):
    meta = {"progress": 42, "next": "ship v1", "users": 7, "name": "Active!", "desc": "the app"}
    st = reader.read_project(str(active_repo), meta=meta)
    assert st.progress == 42
    assert st.next == "ship v1"
    assert st.users == 7
    assert st.name == "Active!"
    assert st.desc == "the app"


def test_desc_goal_alias(active_repo):
    # `goal` is accepted as an alias for `desc` when `desc` absent.
    st = reader.read_project(str(active_repo), meta={"goal": "ship the thing"})
    assert st.desc == "ship the thing"
    # explicit desc wins over goal
    st2 = reader.read_project(str(active_repo), meta={"desc": "D", "goal": "G"})
    assert st2.desc == "D"


def test_human_fields_absent_are_none(active_repo):
    st = reader.read_project(str(active_repo), meta={})
    assert st.progress is None and st.next is None and st.desc is None
    assert st.users == 0


@pytest.mark.parametrize(
    "meta,exp_progress,exp_users,exp_next",
    [
        ({"progress": 150}, None, 0, None),
        ({"progress": -5}, None, 0, None),
        ({"progress": True}, None, 0, None),
        ({"progress": "80"}, None, 0, None),
        ({"users": -3}, None, 0, None),
        ({"next": "   "}, None, 0, None),
        ({"next": "  do x  "}, None, 0, "do x"),
    ],
)
def test_meta_edge_values(active_repo, meta, exp_progress, exp_users, exp_next):
    st = reader.read_project(str(active_repo), meta=meta)
    assert st.progress == exp_progress
    assert st.users == exp_users
    assert st.next == exp_next


# --------------------------------------------------------------------------- #
# READ-ONLY HARD INVARIANT                                                       #
# --------------------------------------------------------------------------- #
def test_git_helper_refuses_mutating_ops(active_repo):
    for bad in (["pull"], ["fetch"], ["commit", "-m", "x"], ["add", "."], ["checkout", "x"]):
        with pytest.raises(ValueError, match="non-read-only"):
            _git(active_repo, bad)


def test_read_only_whitelist_is_all_read():
    mutating = {"pull", "fetch", "clone", "push", "commit", "add", "checkout", "reset", "merge"}
    assert _READ_ONLY_GIT.isdisjoint(mutating)


def test_reader_does_not_mutate_repo(active_repo):
    head_before = subprocess.run(
        ["git", "-C", str(active_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    status_before = subprocess.run(
        ["git", "-C", str(active_repo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout

    reader.read_project(str(active_repo), meta={"progress": 10})

    head_after = subprocess.run(
        ["git", "-C", str(active_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    status_after = subprocess.run(
        ["git", "-C", str(active_repo), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert head_before == head_after
    assert status_before == status_after


# --------------------------------------------------------------------------- #
# front-matter parsing (status.md YAML)                                         #
# --------------------------------------------------------------------------- #
def test_parse_front_matter_ok():
    content = "---\nprogress: 60\nnext: do the thing\nusers: 3\n---\n# body\n"
    meta = parse_front_matter(content)
    assert meta == {"progress": 60, "next": "do the thing", "users": 3}


def test_parse_front_matter_none_and_empty():
    assert parse_front_matter(None) == {}
    assert parse_front_matter("") == {}
    assert parse_front_matter("# no front matter\njust text") == {}


def test_parse_front_matter_malformed_yaml_ignored():
    content = "---\nprogress: : : bad\n  - nested wrong\n---\nbody"
    assert parse_front_matter(content) == {}


def test_parse_front_matter_non_mapping_ignored():
    content = "---\n- just\n- a\n- list\n---\nbody"
    assert parse_front_matter(content) == {}


# --------------------------------------------------------------------------- #
# service orchestration (list/get over config.project_repos)                    #
# --------------------------------------------------------------------------- #
def test_list_projects_empty_when_none_tracked(monkeypatch, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    statuses, warnings = service.list_projects()
    assert statuses == [] and warnings == []


def test_G7_phantom_dir_without_status_md_is_not_a_project(monkeypatch, isolated_paths):
    """G7 — a leaked dir under projects_dir with NO status.md (test fixture like a
    /tmp/pytest-* artifact or a crewly scaffold) must NOT surface as a phantom
    project. Registration IS status.md existence."""
    from store import md_store
    monkeypatch.setattr(service.settings, "project_repos", {})
    # a REAL registered project (has status.md)
    md_store.write_file("projects/real-proj/status.md",
                        "---\nname: Real\nprogress: 10\n---\n", "seed real")
    # a PHANTOM dir (leaked) — exists under projects_dir but has NO status.md
    phantom = service.settings.projects_dir / "tmp-pytest-leak"
    phantom.mkdir(parents=True, exist_ok=True)
    (phantom / "some_fixture.txt").write_text("not a project")

    repos = service._tracked_repos()
    assert "real-proj" in repos          # the real one surfaces
    assert "tmp-pytest-leak" not in repos  # the phantom does NOT (no status.md)


def test_G7_status_md_with_tmp_fixture_repo_is_filtered(monkeypatch, tmp_path, isolated_paths):
    """G7 (the REAL leak) — a status.md-BEARING project whose repo: points at a test
    fixture (/tmp/pytest-*) or a nonexistent non-builtin path is test pollution that
    leaked into the md-store. It must NOT surface in projects_list (the existence gate
    alone misses it because it HAS a status.md)."""
    from store import md_store
    real = tmp_path / "realrepo"
    real.mkdir()
    monkeypatch.setattr(service.settings, "project_repos", {"life-os": str(real)})
    # life-os: a real config built-in → surfaces.
    md_store.write_file("projects/life-os/status.md", "---\nname: Life OS\n---\n", "seed")
    # active: status.md with a DEAD /tmp/pytest fixture repo → phantom, filtered.
    md_store.write_file("projects/active/status.md",
                        "---\nname: Active\nrepo: /tmp/pytest-of-x/pytest-9/active\n---\n", "seed")

    repos = service._tracked_repos()
    assert "life-os" in repos                 # real built-in surfaces
    assert "active" not in repos, "dead /tmp/pytest fixture leaked"


def test_G7_resolving_tmp_repo_is_kept(monkeypatch, tmp_path, isolated_paths):
    """A /tmp/pytest path that STILL RESOLVES is a legit registered repo (a test's own
    repo) — the G7 filter is NARROW (dead-fixture only), it must NOT kill it."""
    from store import md_store
    live = tmp_path / "live-tmp-repo"  # tmp_path is itself /tmp/pytest-* and resolves
    live.mkdir()
    monkeypatch.setattr(service.settings, "project_repos", {})
    md_store.write_file("projects/livep/status.md",
                        f"---\nname: Live\nrepo: {live}\n---\n", "seed")
    assert "livep" in service._tracked_repos()  # resolving tmp repo kept


def test_list_and_get_over_real_repos(monkeypatch, active_repo, stall_repo, isolated_paths):
    monkeypatch.setattr(
        service.settings,
        "project_repos",
        {"active": str(active_repo), "stall": str(stall_repo)},
    )
    statuses, warnings = service.list_projects()
    ids = {s.id: s for s in statuses}
    assert set(ids) == {"active", "stall"}
    assert ids["active"].health == "act"
    assert ids["stall"].health == "stall"

    one = service.get_project("active")
    assert one is not None and one.id == "active" and one.health == "act"
    assert service.get_project("nope") is None


def test_list_projects_dead_repo_emits_warning(monkeypatch, tmp_path, isolated_paths):
    monkeypatch.setattr(
        service.settings, "project_repos", {"ghost": str(tmp_path / "nope")}
    )
    statuses, warnings = service.list_projects()
    assert len(statuses) == 1 and statuses[0].health == "dead"
    assert any("ghost" in w for w in warnings)


def test_service_reads_meta_from_status_md(monkeypatch, active_repo, isolated_paths):
    from store import md_store

    md_store.write_file(
        "projects/active/status.md",
        "---\nprogress: 55\nnext: cut release\nusers: 4\nname: Active Project\ndesc: the app\n---\n",
        "seed",
    )
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    st = service.get_project("active")
    assert st is not None
    assert st.progress == 55 and st.next == "cut release" and st.users == 4
    assert st.name == "Active Project" and st.desc == "the app"


# --------------------------------------------------------------------------- #
# service write paths — register / abandon / refresh (md_store commits)         #
# --------------------------------------------------------------------------- #
def test_register_project_writes_status_and_returns(monkeypatch, active_repo, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    body = ProjectRegisterInput(
        name="My Cool App", repo=str(active_repo), goal="ship it", progress=10, next="do x", users=2
    )
    st = service.register_project(body)
    assert st.id == "my-cool-app"  # slug(name)
    assert st.name == "My Cool App" and st.desc == "ship it"
    assert st.progress == 10 and st.next == "do x" and st.users == 2
    assert st.health == "act"  # active_repo
    # status.md persisted
    from store import md_store
    assert md_store.exists("projects/my-cool-app/status.md")


def test_register_rejects_non_git_repo(monkeypatch, tmp_path, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    plain = tmp_path / "notgit"
    plain.mkdir()
    body = ProjectRegisterInput(name="Bad", repo=str(plain))
    with pytest.raises(service.ProjectError) as ei:
        service.register_project(body)
    assert ei.value.code == 400


def test_register_id_collision_409(monkeypatch, active_repo, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    body = ProjectRegisterInput(name="Dup", repo=str(active_repo))
    service.register_project(body)
    with pytest.raises(service.ProjectError) as ei:
        service.register_project(body)
    assert ei.value.code == 409


def test_abandon_excludes_from_list_but_get_returns(monkeypatch, active_repo, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    st = service.abandon_project("active", ProjectAbandonInput(reason="pivot", atProgress=33))
    assert st is not None and st.id == "active"
    # excluded from default list
    statuses, _ = service.list_projects()
    assert all(s.id != "active" for s in statuses)
    # but still retrievable + flag persisted
    got = service.get_project("active")
    assert got is not None
    meta = service._load_meta("active")
    assert meta["abandoned"] is True
    assert meta["abandonedReason"] == "pivot"
    assert meta["abandonedProgress"] == 33
    assert "abandonedAt" in meta


def test_abandon_unknown_id_returns_none(monkeypatch, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    assert service.abandon_project("ghost", ProjectAbandonInput(reason="x")) is None


def test_restore_clears_abandon_flags_but_PRESERVES_lesson(monkeypatch, active_repo, isolated_paths):
    """S8 restore: clears abandoned* (incl. abandonedUsers) → rejoins list_projects,
    but PRESERVES `lesson` (hard-won history). TEETH: RED if `lesson` is ever added
    back to restore_project's clear-set."""
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    service.abandon_project("active", ProjectAbandonInput(reason="pivot", atProgress=40, lesson="ship smaller"))
    meta = service._load_meta("active")
    assert meta["abandoned"] is True and meta["lesson"] == "ship smaller" and meta["abandonedUsers"] == 0

    restored = service.restore_project("active")
    assert restored is not None and restored.id == "active"
    # back in list_projects (un-graveyarded)
    assert any(s.id == "active" for s in service.list_projects()[0])
    meta2 = service._load_meta("active")
    # abandon* flags CLEARED
    for k in ("abandoned", "abandonedReason", "abandonedAt", "abandonedProgress", "abandonedUsers"):
        assert k not in meta2, f"{k} should be cleared by restore"
    # lesson PRESERVED (the architect ruling — hard-won history)
    assert meta2.get("lesson") == "ship smaller"


def test_restore_non_abandoned_is_noop(monkeypatch, active_repo, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    # never abandoned → restore returns the project, no error, no-op
    r = service.restore_project("active")
    assert r is not None and r.id == "active"


def test_restore_unknown_id_returns_none(monkeypatch, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    assert service.restore_project("ghost") is None  # router → 404


def test_refresh_stamps_last_auto(monkeypatch, active_repo, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    st = service.refresh_project("active")
    assert st is not None and st.lastAuto is not None
    # persisted into status.md
    meta = service._load_meta("active")
    assert meta.get("lastAuto") == st.lastAuto


def test_refresh_unknown_id_returns_none(monkeypatch, isolated_paths):
    monkeypatch.setattr(service.settings, "project_repos", {})
    assert service.refresh_project("ghost") is None


def test_registered_project_discovered_from_status_md(monkeypatch, active_repo, isolated_paths):
    """A status.md with a repo: pointer is tracked even if not in config."""
    monkeypatch.setattr(service.settings, "project_repos", {})
    from store import md_store
    md_store.write_file(
        "projects/extra/status.md",
        f"---\nname: Extra\nrepo: {active_repo}\n---\n",
        "seed extra",
    )
    statuses, _ = service.list_projects()
    assert any(s.id == "extra" and s.health == "act" for s in statuses)


def test_stale_status_md_repo_path_falls_back_to_config(monkeypatch, active_repo, isolated_paths):
    """3B layer-4: a config project whose status.md `repo:` points at a GONE path
    must fall back to the config path (not read as dead). Stale status.md ≠ dead project."""
    from store import md_store
    # config tracks 'active' at the REAL repo
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    # but status.md records a stale/nonexistent repo path
    md_store.write_file(
        "projects/active/status.md",
        "---\nname: Active\nrepo: /tmp/this-path-was-moved-and-is-gone\n---\n",
        "stale path",
    )
    tracked = service._tracked_repos()
    # fell back to the config path, NOT the stale status.md path
    assert tracked["active"] == str(active_repo), f"should fall back to config, got {tracked['active']}"
    # and the project reads with REAL health (act), not dead
    st = service.get_project("active")
    assert st is not None and st.health == "act"


def test_stale_path_fallback_logs_at_debug_not_warning(monkeypatch, active_repo, isolated_paths, caplog):
    """NG5: the stale-path→config-path fallback is a NORMAL handled case — it must NOT
    leak a WARNING-level log (which polluted MCP stderr 5× per projects_list/brief call,
    preceding the JSON the agent reads). The fallback still WORKS; it's just silent now:
    the message lives at DEBUG, and projects still resolve via the config path."""
    import logging
    from store import md_store
    monkeypatch.setattr(service.settings, "project_repos", {"active": str(active_repo)})
    md_store.write_file(
        "projects/active/status.md",
        "---\nname: Active\nrepo: /tmp/this-path-was-moved-and-is-gone\n---\n",
        "stale path",
    )
    # Capture at WARNING — nothing about the fallback should appear at this level.
    with caplog.at_level(logging.WARNING, logger=service.logger.name):
        tracked = service._tracked_repos()
    assert not any("falling back to config path" in r.message for r in caplog.records), \
        "stale-path fallback must NOT emit a WARNING (NG5: demoted to DEBUG)"
    # And it's present at DEBUG (the fallback was taken, just quietly).
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=service.logger.name):
        tracked = service._tracked_repos()
    assert any("falling back to config path" in r.message and r.levelno == logging.DEBUG
               for r in caplog.records), "fallback should log at DEBUG level"
    # The fallback still RESOLVES the project via the config path (behavior unchanged).
    assert tracked["active"] == str(active_repo)


def test_stale_status_md_path_kept_when_not_in_config(monkeypatch, isolated_paths):
    """A registered-only (non-config) project with a stale path keeps the stale
    path (no config to fall back to) — it'll read dead, which is honest."""
    from store import md_store
    monkeypatch.setattr(service.settings, "project_repos", {})
    md_store.write_file(
        "projects/orphan/status.md",
        "---\nname: Orphan\nrepo: /tmp/gone-orphan-path\n---\n",
        "orphan stale",
    )
    tracked = service._tracked_repos()
    assert tracked["orphan"] == "/tmp/gone-orphan-path"  # no fallback available


def test_hidden_dirs_are_not_projects(monkeypatch, isolated_paths):
    """Sprint 1A regression: a HIDDEN dir under DATA_DIR/projects (.claude agent-
    memory, .git, ...) must NOT surface as a phantom project (honest-mirror, SPEC §0).

    RED without the `startswith('.')` filter in _tracked_repos(); GREEN with it.
    """
    from store import md_store
    monkeypatch.setattr(service.settings, "project_repos", {})
    projects_dir = service.settings.projects_dir
    # Physically create hidden dirs (the real condition: .claude lands here).
    (projects_dir / ".claude" / "agent-memory").mkdir(parents=True)
    (projects_dir / ".git").mkdir(parents=True)
    # A real (non-hidden) REGISTERED project alongside, to prove the filter is
    # surgical. G7: registration = status.md existence, so the real project has one
    # (a bare dir without status.md is now correctly a phantom — see the G7 test).
    md_store.write_file("projects/realproj/status.md",
                        "---\nname: Real\nprogress: 5\n---\n", "seed realproj")

    tracked = service._tracked_repos()
    assert ".claude" not in tracked, f".claude leaked as a project: {sorted(tracked)}"
    assert ".git" not in tracked, f".git leaked as a project: {sorted(tracked)}"
    assert "realproj" in tracked, "the real registered project must still be tracked"

    # And it must not appear in the public list_projects() output either.
    ids = {s.id for s in service.list_projects()[0]}
    assert not any(i.startswith(".") for i in ids), f"hidden-dir id leaked into list: {ids}"


# --------------------------------------------------------------------------- #
# schema boundary                                                               #
# --------------------------------------------------------------------------- #
def test_register_input_validation():
    ok = ProjectRegisterInput(repo="/x/y", name="Demo")
    assert ok.goal is None and ok.progress is None
    with pytest.raises(Exception):
        ProjectRegisterInput(repo="", name="Demo")
    with pytest.raises(Exception):
        ProjectRegisterInput(repo="/x", name="")
    with pytest.raises(Exception):
        ProjectRegisterInput(repo="/x", name="D", progress=200)


def test_abandon_input_validation():
    ok = ProjectAbandonInput(reason="x")
    assert ok.atProgress is None
    with pytest.raises(Exception):
        ProjectAbandonInput(reason="")  # empty reason rejected


def test_project_status_progress_bounds():
    with pytest.raises(Exception):
        ProjectStatus(id="a", name="A", health="act", repo="/x", progress=101)
    s = ProjectStatus(id="a", name="A", health="act", repo="/x", progress=0)
    assert s.progress == 0 and s.metrics == ProjectMetrics() and s.desc is None
