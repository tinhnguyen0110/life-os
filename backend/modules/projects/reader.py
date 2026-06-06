"""modules/projects/reader.py — READ-ONLY local git reader (Sprint 1, Tier-S).

Given a repo path + optional human metadata (from status.md), derive a
ProjectStatus per the architect's Logic block. The reader issues ONLY read git
commands — a hard invariant (T4 asserts no write/pull happened). It never raises:
an unreadable/missing/non-git/empty repo fails open to health="dead".

Logic (architect-decided, implemented verbatim):
  - lastDays = whole UTC days since the last commit.
  - health: act ≤7 · slow ≤30 · stall ≤90 · dead >90 OR repo unreadable/empty.
  - progress/next/users: from status.md front-matter (caller passes parsed meta);
    progress/next default None, users defaults 0. NEVER fabricated from git.
  - metrics.commits = rev-list --count HEAD; branch = abbrev-ref HEAD;
    lang = dominant tracked-file extension → language name, else None;
    testPass = None; stars = None.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .schema import Health, ProjectMetrics, ProjectStatus

logger = logging.getLogger("life-os.projects.reader")


def slug(folder_name: str) -> str:
    """Project id = folder name lowercased, runs of non-alphanumerics → single '-'.

    e.g. "OutboundOS" → "outboundos", "claude-code-agents-ui" → "claude-code-agents-ui".
    """
    s = re.sub(r"[^a-z0-9]+", "-", folder_name.lower()).strip("-")
    return s or "project"

# READ-ONLY whitelist. The reader may ONLY run these git subcommands. Any other
# subcommand (pull/fetch/clone/commit/add/checkout/...) is rejected before exec,
# making a mutating op structurally impossible (read-only HARD invariant).
_READ_ONLY_GIT = frozenset(
    {"rev-list", "rev-parse", "log", "status", "ls-files", "cat-file", "show-ref"}
)

# Health thresholds in whole UTC days (architect Logic block — verbatim).
_ACT_MAX_DAYS = 7
_SLOW_MAX_DAYS = 30
_STALL_MAX_DAYS = 90

# Dominant-extension → language name. Unmapped/none → lang=None (honest).
_EXT_LANG: dict[str, str] = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".rb": "Ruby",
    ".php": "PHP", ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".cs": "C#",
    ".swift": "Swift", ".kt": "Kotlin", ".scala": "Scala", ".sh": "Shell",
    ".css": "CSS", ".scss": "CSS", ".html": "HTML", ".md": "Markdown",
    ".sql": "SQL", ".vue": "Vue", ".dart": "Dart", ".lua": "Lua", ".r": "R",
}


class _RepoUnreadable(Exception):
    """Internal: repo path is missing / not a git repo / git unavailable."""


def _git(repo_path: Path, args: list[str], *, timeout: float = 10.0) -> str:
    """Run ONE read-only git command in ``repo_path`` and return stdout (stripped).

    Enforces the read-only whitelist before exec. Raises ``_RepoUnreadable`` on a
    non-zero exit, timeout, or missing git binary — callers translate that to a
    fail-open dead status. NEVER runs a mutating subcommand.
    """
    if not args or args[0] not in _READ_ONLY_GIT:
        # Defensive: refuse anything not on the read-only whitelist.
        raise ValueError(f"refusing non-read-only git op: {args[:1]}")
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise _RepoUnreadable(str(exc)) from exc
    if proc.returncode != 0:
        raise _RepoUnreadable(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _is_git_repo(repo_path: Path) -> bool:
    """True iff ``repo_path`` exists and is inside a git work tree."""
    if not repo_path.is_dir():
        return False
    try:
        return _git(repo_path, ["rev-parse", "--is-inside-work-tree"]) == "true"
    except _RepoUnreadable:
        return False


def _last_commit_iso(repo_path: Path) -> str | None:
    """ISO-8601 UTC timestamp of HEAD's commit, or None if no commits / unborn."""
    try:
        # %cI = committer date, strict ISO-8601 (with original offset).
        raw = _git(repo_path, ["log", "-1", "--format=%cI"])
    except _RepoUnreadable:
        return None
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw).astimezone(timezone.utc)
    except ValueError:
        return None
    return dt.isoformat()


def _whole_days_since(iso_utc: str) -> int | None:
    """Whole UTC days between ``iso_utc`` and now. None if unparseable."""
    try:
        then = datetime.fromisoformat(iso_utc)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - then.astimezone(timezone.utc)
    return max(0, delta.days)


def _health_from_days(last_days: int | None) -> Health:
    """Bucket lastDays into a health label. None → dead (fail-open default)."""
    if last_days is None:
        return "dead"
    if last_days <= _ACT_MAX_DAYS:
        return "act"
    if last_days <= _SLOW_MAX_DAYS:
        return "slow"
    if last_days <= _STALL_MAX_DAYS:
        return "stall"
    return "dead"


def _commit_count(repo_path: Path) -> int:
    """git rev-list --count HEAD; 0 on empty/unborn repo."""
    try:
        out = _git(repo_path, ["rev-list", "--count", "HEAD"])
    except _RepoUnreadable:
        return 0
    try:
        return int(out)
    except ValueError:
        return 0


def _current_branch(repo_path: Path) -> str:
    """Abbreviated current branch. 'HEAD' on detached; '' if unreadable."""
    try:
        return _git(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    except _RepoUnreadable:
        return ""


def _dominant_lang(repo_path: Path) -> str | None:
    """Most common tracked-file extension mapped to a language. None if unknown."""
    try:
        out = _git(repo_path, ["ls-files"])
    except _RepoUnreadable:
        return None
    if not out:
        return None
    counts: Counter[str] = Counter()
    for line in out.splitlines():
        ext = Path(line).suffix.lower()
        lang = _EXT_LANG.get(ext)
        if lang:
            counts[lang] += 1
    if not counts:
        return None
    # Deterministic on ties: highest count, then lexicographically first name.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _meta_name(meta: dict, fallback: str) -> str:
    """name from status.md `name:`; else the repo folder name verbatim."""
    val = meta.get("name")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return fallback


def _meta_desc(meta: dict) -> str | None:
    """desc from status.md `desc:`, falling back to `goal:` (alias). Else None."""
    for key in ("desc", "goal"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _meta_last_auto(meta: dict) -> str | None:
    """lastAuto cached in status.md front-matter (set by refresh/routine). Else None."""
    val = meta.get("lastAuto")
    return val.strip() if isinstance(val, str) and val.strip() else None


def _dead_status(
    project_id: str, name: str, repo_path: str, meta: dict
) -> ProjectStatus:
    """Fail-open status for a missing/unreadable/non-git/empty repo.

    git-derived fields zeroed/None; human fields from meta still honored.
    """
    return ProjectStatus(
        id=project_id,
        name=name,
        desc=_meta_desc(meta),
        health="dead",
        progress=_meta_progress(meta),
        users=_meta_users(meta),
        last=None,
        lastDays=None,
        next=_meta_next(meta),
        repo=repo_path,
        metrics=ProjectMetrics(commits=0, branch="", lang=None, testPass=None, stars=None),
        routines=[],
        lastAuto=_meta_last_auto(meta),
    )


def _meta_progress(meta: dict) -> int | None:
    """progress from status.md meta: int 0-100 if valid, else None (no fabrication)."""
    val = meta.get("progress")
    if isinstance(val, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(val, int) and 0 <= val <= 100:
        return val
    return None


def _meta_users(meta: dict) -> int:
    """users from status.md meta: non-negative int, else 0."""
    val = meta.get("users")
    if isinstance(val, bool):
        return 0
    if isinstance(val, int) and val >= 0:
        return val
    return 0


def _meta_next(meta: dict) -> str | None:
    """next action from status.md meta: non-empty str, else None."""
    val = meta.get("next")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def read_project(repo_path: str, *, meta: dict | None = None) -> ProjectStatus:
    """Read a single project's status from its local git repo, READ-ONLY.

    The project ``id`` is derived as ``slug(<repo folder name>)`` and ``name`` is
    the status.md ``name:`` (else the folder name). All human fields come from
    ``meta`` (parsed status.md front-matter); git-derived fields come from
    read-only local git.

    Args:
        repo_path: absolute path of the source git repo (read-only).
        meta:      parsed status.md front-matter dict, or None.

    Returns a schema-valid ProjectStatus. NEVER raises: any unreadable/missing/
    non-git/empty repo fails open to health="dead". Issues only read-only git.
    """
    meta = meta or {}
    path = Path(repo_path).expanduser()
    folder_name = path.name or repo_path
    project_id = slug(folder_name)
    display_name = _meta_name(meta, folder_name)

    if not _is_git_repo(path):
        logger.warning("project %r repo not readable as git: %s", project_id, repo_path)
        return _dead_status(project_id, display_name, repo_path, meta)

    last_iso = _last_commit_iso(path)
    last_days = _whole_days_since(last_iso) if last_iso else None
    health = _health_from_days(last_days)

    metrics = ProjectMetrics(
        commits=_commit_count(path),
        branch=_current_branch(path),
        lang=_dominant_lang(path),
        testPass=None,
        stars=None,
    )

    return ProjectStatus(
        id=project_id,
        name=display_name,
        desc=_meta_desc(meta),
        health=health,
        progress=_meta_progress(meta),
        users=_meta_users(meta),
        last=last_iso,
        lastDays=last_days,
        next=_meta_next(meta),
        repo=repo_path,
        metrics=metrics,
        routines=[],
        lastAuto=_meta_last_auto(meta),
    )
