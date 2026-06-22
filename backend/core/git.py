"""core/git.py — the ONE read-only git-exec helper (PROJECTS-UNIFY T4, #115).

Both projects/reader.py and dev_activity/service.py spawn `git` subprocesses to read
commit history, but had DIFFERENT implementations (projects: whitelist + `log -1 %cI` +
`rev-list --count`; dev_activity: `log --no-merges --all --numstat`). This unifies the
EXEC layer into one safe, read-only spawn point — the module-specific PARSE stays in each
module (projects: health-bucket; dev_activity: numstat/LOC/you-vs-other).

🔴 READ-ONLY INVARIANT (HARD): `run_read_git` enforces ``READ_ONLY_GIT`` — it refuses any
subcommand not on the whitelist, so this helper can NEVER run a mutating git op.

Two failure CONTRACTS are preserved (the callers differ on purpose — #115 must keep both
byte-identical):
  - ``run_read_git`` — strip + RAISE on failure (fail-CLOSED). projects/reader uses this:
    a non-zero/timeout/missing-git raises ``RepoUnreadable`` → the caller marks the repo
    dead. stdout is ``.strip()``-ed (projects parses single values like %cI / a count).
  - ``run_read_git_proc`` — return the raw ``CompletedProcess`` (NO strip, NO raise on
    non-zero). dev_activity uses this: it needs the RAW multi-line ``log --numstat`` output
    for its line-parser, and it is fail-SOFT (its own try/except logs + skips the repo so
    the scan continues). Only ``FileNotFoundError``/``TimeoutExpired`` still propagate (the
    caller catches ``Exception`` around the call, exactly as before).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# The read-only git subcommands this app is allowed to run. Anything not here is refused
# (defense-in-depth: this module can never mutate a repo). Superset of both callers' needs:
# projects (rev-list/rev-parse/log/status/ls-files/cat-file/show-ref) + dev_activity (log).
READ_ONLY_GIT = frozenset(
    {"rev-list", "rev-parse", "log", "status", "ls-files", "cat-file", "show-ref"}
)


class RepoUnreadable(Exception):
    """Repo path is missing / not a git repo / git unavailable / a read-only op failed.

    Raised by ``run_read_git`` (the fail-CLOSED contract). Callers translate it to a
    fail-open dead status."""


def _check_read_only(args: list[str]) -> None:
    """Refuse anything not on the read-only whitelist (the HARD invariant)."""
    if not args or args[0] not in READ_ONLY_GIT:
        raise ValueError(f"refusing non-read-only git op: {args[:1]}")


def run_read_git_proc(
    repo_path: str | Path, args: list[str], *, timeout: float
) -> subprocess.CompletedProcess[str]:
    """Run ONE read-only git command and return the RAW ``CompletedProcess`` (no strip, no
    raise-on-nonzero). Enforces the read-only whitelist before exec.

    For the fail-SOFT, raw-stdout caller (dev_activity._scan_repo): it reads
    ``.stdout`` un-stripped (the line-parser needs the structure) and wraps the call in its
    own try/except to skip a failed repo. ``FileNotFoundError`` / ``subprocess.TimeoutExpired``
    propagate (the caller catches ``Exception``)."""
    _check_read_only(args)
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def run_read_git(repo_path: str | Path, args: list[str], *, timeout: float = 10.0) -> str:
    """Run ONE read-only git command in ``repo_path`` and return stdout (stripped).

    Enforces the read-only whitelist before exec. Raises ``RepoUnreadable`` on a non-zero
    exit, timeout, or missing git binary — the fail-CLOSED contract (projects/reader: the
    caller translates it to a dead status). NEVER runs a mutating subcommand."""
    try:
        proc = run_read_git_proc(repo_path, args, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RepoUnreadable(str(exc)) from exc
    if proc.returncode != 0:
        raise RepoUnreadable(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def is_git_repo(repo_path: str | Path) -> bool:
    """True iff ``repo_path`` exists and is inside a git work tree."""
    p = Path(repo_path)
    if not p.is_dir():
        return False
    try:
        return run_read_git(p, ["rev-parse", "--is-inside-work-tree"]) == "true"
    except RepoUnreadable:
        return False
