"""tests/test_core_git.py — PROJECTS-UNIFY T4 (#115): the shared read-only git-exec helper.

core/git.py unifies the git-subprocess EXEC layer that projects/reader.py + dev_activity/
service.py both used. This proves:
  - the read-only whitelist is HARD (a mutating op is REFUSED before exec — the invariant);
  - 🔴 BYTE-IDENTICAL to the old inline subprocess.run (the pure-refactor proof, deterministic
    on a FIXED repo — the live /projects+/dev-activity snapshot is too noisy to prove this,
    real commits land between snapshots, so we prove it at the unit level on a fixed input);
  - the two failure CONTRACTS the callers depend on are preserved: run_read_git strips+raises
    (fail-CLOSED, projects), run_read_git_proc returns raw CompletedProcess (no strip, no raise
    on nonzero — fail-SOFT, dev_activity).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from core import git as core_git


# --------------------------------------------------------------------------- #
# a real fixed git repo (so the byte-identical comparison is deterministic)      #
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
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "fixed"
    _init_repo(r)
    _commit(r, "a.py", "print(1)\n", date="2026-01-01T10:00:00")
    _commit(r, "b.py", "x = 2\ny = 3\n", date="2026-01-02T11:00:00")
    return r


# --------------------------------------------------------------------------- #
# 🔴 read-only whitelist is HARD — a mutating op is REFUSED before exec          #
# --------------------------------------------------------------------------- #
_MUTATING = ["commit", "push", "merge", "rebase", "reset", "checkout", "add", "rm",
             "clean", "gc", "fetch", "pull", "branch", "tag", "stash", "cherry-pick"]


@pytest.mark.parametrize("op", _MUTATING)
def test_whitelist_refuses_mutating_op(repo, op):
    """run_read_git / run_read_git_proc REFUSE any subcommand not on READ_ONLY_GIT — the op
    must NEVER reach subprocess. ValueError before exec."""
    with pytest.raises(ValueError, match="non-read-only"):
        core_git.run_read_git(repo, [op, "--anything"])
    with pytest.raises(ValueError, match="non-read-only"):
        core_git.run_read_git_proc(repo, [op], timeout=5)


def test_whitelist_is_disjoint_from_mutating():
    assert core_git.READ_ONLY_GIT.isdisjoint(set(_MUTATING))


def test_empty_args_refused(repo):
    with pytest.raises(ValueError):
        core_git.run_read_git(repo, [])


# --------------------------------------------------------------------------- #
# 🔴 BYTE-IDENTICAL to the old inline subprocess.run (the pure-refactor proof)    #
# --------------------------------------------------------------------------- #
def test_run_read_git_proc_byte_identical_to_inline_log(repo):
    """dev_activity's exact `git log --numstat` via run_read_git_proc == the old inline
    subprocess.run — RAW stdout, no strip (the dev_activity contract)."""
    _LOG_FORMAT = "C|%ae|%cI|%H"
    args = ["log", "--no-merges", "--all", "--since=2025-01-01",
            "--numstat", f"--pretty=format:{_LOG_FORMAT}", "--date=iso-strict"]
    # old inline form (what _scan_repo used before #115)
    old = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True, timeout=60).stdout
    # new shared form
    new = core_git.run_read_git_proc(repo, args, timeout=60).stdout
    assert new == old, "run_read_git_proc must be byte-identical to the old inline subprocess.run"
    assert "C|t@t|" in new  # sanity: it actually returned the log


def test_run_read_git_byte_identical_to_inline_strip(repo):
    """projects' single-value reads via run_read_git == old inline .stdout.strip() for each
    read-only op projects used."""
    for args in (["rev-list", "--count", "HEAD"],
                 ["rev-parse", "--abbrev-ref", "HEAD"],
                 ["log", "-1", "--format=%cI"]):
        old = subprocess.run(["git", "-C", str(repo), *args],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        new = core_git.run_read_git(repo, args)
        assert new == old, f"run_read_git mismatch for {args}: {new!r} != {old!r}"
    # the count is the real number of commits (2)
    assert core_git.run_read_git(repo, ["rev-list", "--count", "HEAD"]) == "2"


# --------------------------------------------------------------------------- #
# failure CONTRACTS — fail-CLOSED (run_read_git) vs fail-SOFT (run_read_git_proc) #
# --------------------------------------------------------------------------- #
def test_run_read_git_raises_on_nonzero(tmp_path):
    """fail-CLOSED: a non-git dir → non-zero exit → RepoUnreadable (projects marks dead)."""
    notgit = tmp_path / "notgit"
    notgit.mkdir()
    with pytest.raises(core_git.RepoUnreadable):
        core_git.run_read_git(notgit, ["rev-parse", "--is-inside-work-tree"])


def test_run_read_git_proc_does_not_raise_on_nonzero(tmp_path):
    """fail-SOFT: run_read_git_proc returns the CompletedProcess with returncode!=0 — it does
    NOT raise (dev_activity's own try/except decides; on a clean dir git just exits nonzero)."""
    notgit = tmp_path / "notgit2"
    notgit.mkdir()
    proc = core_git.run_read_git_proc(notgit, ["log", "--oneline"], timeout=5)
    assert proc.returncode != 0  # nonzero, but NO exception raised


def test_is_git_repo(repo, tmp_path):
    assert core_git.is_git_repo(repo) is True
    assert core_git.is_git_repo(tmp_path / "does-not-exist") is False
    plain = tmp_path / "plain"
    plain.mkdir()
    assert core_git.is_git_repo(plain) is False  # exists but not a git work tree


# --------------------------------------------------------------------------- #
# projects/reader re-exports still resolve to the shared symbols (no caller break)#
# --------------------------------------------------------------------------- #
def test_reader_reexports_are_the_shared_symbols():
    from modules.projects import reader
    assert reader._git is core_git.run_read_git
    assert reader._is_git_repo is core_git.is_git_repo
    assert reader._RepoUnreadable is core_git.RepoUnreadable
    assert reader._READ_ONLY_GIT is core_git.READ_ONLY_GIT
