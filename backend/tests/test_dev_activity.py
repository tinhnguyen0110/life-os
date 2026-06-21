"""tests/test_dev_activity.py — DEV-TRACING-P1 (#63) local git-scan tests.

EXERCISE the scan against a REAL temp git repo (git init + commits in the test, scan it, assert) —
NOT a field-read (behavior-test-not-field-read). Each test is a DIVERGENT distinguishing case from
the HARD GATE: identity-map (you vs other), LOC_SKIP (lockfile excluded), --no-merges, idempotent
re-scan, honest-empty-on-unconfigured-roots, TZ→VN-day. Mount-independent (the temp repo is the
scan root); the live-container curl (tester) verifies the real mount.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from modules.dev_activity import reader, service, store


def _git(repo: str, *args: str, env: dict | None = None):
    """Run a git command in `repo`, raising on failure (test setup must succeed)."""
    full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True, env=full_env)


def _commit(repo: str, *, email: str, name: str, files: dict[str, str], msg: str,
            date: str | None = None):
    """Write `files` (path→content) + commit as (name<email>). `date` (ISO) sets author+committer
    date for TZ tests. Returns nothing — exercises the real git history the scan reads."""
    for path, content in files.items():
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(path) else None
        with open(full, "w") as f:
            f.write(content)
    _git(repo, "add", "-A")
    env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
           "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    _git(repo, "commit", "-m", msg, env=env)


@pytest.fixture
def temp_repo(tmp_path, isolated_paths, monkeypatch):
    """A real git repo under a tmp scan root + DEV_TRACING_ROOTS/EMAILS pointed at it. isolated_paths
    gives a fresh dev_activity db. Returns the repo path."""
    root = tmp_path / "scan_root"
    repo = root / "myrepo"
    repo.mkdir(parents=True)
    _git(str(repo), "init", "-b", "main")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    return str(repo)


# --- identity-map: you vs other (the HARD GATE: 2 you / 1 other → commits=2 source=you) ----- #
def test_identity_map_you_vs_other(temp_repo):
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="mine 1")
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=2\ny=3\n"}, msg="mine 2")
    _commit(temp_repo, email="other@team.com", name="Teammate", files={"b.py": "z=1\n"}, msg="theirs")
    result = service.scan(days=30)
    assert result["yourCommits"] == 2  # only the 2 me@ commits count as "you"
    ov = reader.get_overview(30)
    assert ov.summary.totalCommits == 2  # your totals exclude "other"
    # the 'other' commit is STORED + surfaced separately (team context, tagged, not in your totals)
    assert any(r.source == "other" and r.commits == 1 for r in ov.otherRepos)


def test_unconfigured_emails_tags_all_other_with_warning(tmp_path, isolated_paths, monkeypatch):
    """DEV_TRACING_EMAILS unset → every commit tags 'other' + a warning (NEVER silently 'you')."""
    root = tmp_path / "r"
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(str(repo), "init", "-b", "main")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.delenv("DEV_TRACING_EMAILS", raising=False)
    store.init_dev_activity_tables()
    _commit(str(repo), email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    result = service.scan(days=30)
    assert result["yourCommits"] == 0  # nothing attributed to "you"
    assert any("DEV_TRACING_EMAILS not set" in w for w in result["warnings"])


# --- LOC_SKIP: a lockfile + a real file → LOC counts ONLY the real file --------------------- #
def test_loc_skip_excludes_lockfile(temp_repo):
    _commit(temp_repo, email="me@example.com", name="Me",
            files={"package-lock.json": "{\n" + "\n".join(f'"k{i}":{i},' for i in range(50)) + "\n}\n",
                   "real.py": "a=1\nb=2\nc=3\n"},
            msg="lock + real")
    service.scan(days=30)
    ov = reader.get_overview(30)
    me = [r for r in ov.byRepo if r.repo == "myrepo"][0]
    # only real.py's 3 lines counted; the 50-line lockfile is LOC_SKIP-excluded
    assert me.locAdded == 3, f"LOC must exclude the lockfile, got {me.locAdded}"


def test_binary_numstat_is_zero_not_crash(temp_repo):
    """A binary file (numstat '-\t-') → 0 LOC, no crash (the validate guard)."""
    with open(os.path.join(temp_repo, "img.bin"), "wb") as f:
        f.write(bytes(range(256)) * 4)  # binary content
    _git(temp_repo, "add", "-A")
    _git(temp_repo, "commit", "-m", "binary",
         env={"GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "me@example.com",
              "GIT_COMMITTER_NAME": "Me", "GIT_COMMITTER_EMAIL": "me@example.com"})
    service.scan(days=30)
    ov = reader.get_overview(30)  # must not raise on the binary numstat
    me = [r for r in ov.byRepo if r.repo == "myrepo"][0]
    assert me.commits == 1 and me.locAdded == 0


# --- --no-merges: a merge commit is excluded ------------------------------------------------ #
def test_merge_commit_excluded(temp_repo):
    e = {"GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "me@example.com",
         "GIT_COMMITTER_NAME": "Me", "GIT_COMMITTER_EMAIL": "me@example.com"}
    _commit(temp_repo, email="me@example.com", name="Me", files={"base.py": "x=1\n"}, msg="base")
    _git(temp_repo, "checkout", "-b", "feature")
    _commit(temp_repo, email="me@example.com", name="Me", files={"feat.py": "y=1\n"}, msg="feat")
    _git(temp_repo, "checkout", "main")
    _commit(temp_repo, email="me@example.com", name="Me", files={"main2.py": "z=1\n"}, msg="main work")
    _git(temp_repo, "merge", "--no-ff", "feature", "-m", "MERGE feature", env=e)
    service.scan(days=30)
    ov = reader.get_overview(30)
    me = [r for r in ov.byRepo if r.repo == "myrepo"][0]
    # base + feat + main work = 3 real commits; the MERGE is excluded by --no-merges
    assert me.commits == 3, f"merge must be excluded, got {me.commits}"


# --- idempotent re-scan (no double-count — upsert per date×repo×source) --------------------- #
def test_rescan_idempotent(temp_repo):
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\ny=2\n"}, msg="c1")
    service.scan(days=30)
    first = reader.get_overview(30).summary.totalCommits
    service.scan(days=30)  # re-scan
    second = reader.get_overview(30).summary.totalCommits
    assert first == second == 1, f"re-scan must be idempotent, got {first} then {second}"


# --- honest-empty + warnings (roots unconfigured / unreachable) ----------------------------- #
def test_no_roots_honest_empty_with_warning(isolated_paths, monkeypatch):
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)
    store.init_dev_activity_tables()
    result = service.scan(days=30)
    assert result["scannedRepos"] == 0 and result["rowsUpserted"] == 0
    assert any("DEV_TRACING_ROOTS not set" in w for w in result["warnings"])
    ov = reader.get_overview(30)
    assert ov.byDay == [] and ov.summary.totalCommits == 0
    assert ov.warnings  # honest: warns, NOT silent-zero


def test_unreachable_root_warns_not_crash(isolated_paths, monkeypatch, tmp_path):
    """A configured root that doesn't exist (e.g. unmounted) → warning + honest-empty, no crash."""
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    result = service.scan(days=30)
    assert result["scannedRepos"] == 0
    assert any("unreachable" in w for w in result["warnings"])


def test_non_git_dir_skipped(isolated_paths, monkeypatch, tmp_path):
    """A root that exists but has no .git (and no child repos) → 0 scanned, no crash."""
    root = tmp_path / "plain"
    (root / "subdir").mkdir(parents=True)
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    result = service.scan(days=30)
    assert result["scannedRepos"] == 0 and result["rowsUpserted"] == 0


# --- TZ → VN day (the vn_day_of helper) ----------------------------------------------------- #
def test_tz_vn_day_bucketing():
    # 23:30 +07:00 → that VN day; 23:30 Z (UTC) → next VN day (06:30 VN next day)
    assert service._vn_day("2026-06-21T23:30:00+07:00") == "2026-06-21"
    assert service._vn_day("2026-06-21T23:30:00+00:00") == "2026-06-22"


def test_active_span_format():
    assert service._span("08:00", "10:30") == "2h 30m"
    assert service._span("09:00", "09:00") == ""   # single commit → no span
    assert service._span(None, None) == ""


# --- registry auto-discovery (no core edit) ------------------------------------------------- #
def test_module_registered():
    from modules.dev_activity.router import MODULE
    assert MODULE.name == "dev_activity"
    assert any(r.id == "dev-activity-scan" for r in MODULE.routines())


# --- the MCP dev_activity tool == REST (byte-identical, #24) --------------------------------- #
def test_mcp_dev_activity_byte_identical_to_reader(temp_repo):
    import json
    import mcp_servers.read_server as rs
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    service.scan(days=30)
    mcp = rs.dev_activity(90)
    rest = reader.get_overview(90).model_dump()
    assert json.dumps(mcp, sort_keys=True) == json.dumps(rest, sort_keys=True)
