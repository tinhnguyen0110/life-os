"""modules/projects/service.py — project registry + orchestration (Sprint 1).

Tracked projects come from two sources, unified by slug id:
  - built-ins: ``settings.project_repos`` (id -> abs path, populated by T3), and
  - registered: any ``projects/<id>/status.md`` under DATA_DIR (written by
    POST /projects). status.md existence IS registration; its `repo:` front-matter
    points at the source repo.

Each project's human metadata + cached derived fields (desc/abandoned*/lastAuto)
live in its ``status.md`` YAML front-matter (read-only via md_store); git fills
health/last/commits/branch/lang live each call.

Exposes the accessors T2 (router) calls:
  - list_projects()        -> (statuses[, excluding abandoned], warnings)
  - get_project(id)        -> ProjectStatus | None (includes abandoned)
  - register_project(body) -> ProjectStatus
  - abandon_project(id, body) -> ProjectStatus | None
  - refresh_project(id)    -> ProjectStatus | None
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.config import settings
from store import md_store

from . import reader
from .reader import slug
from .schema import ProjectAbandonInput, ProjectRegisterInput, ProjectStatus

logger = logging.getLogger("life-os.projects.service")


# --------------------------------------------------------------------------- #
# status.md front-matter I/O                                                    #
# --------------------------------------------------------------------------- #
def _status_md_rel(project_id: str) -> str:
    """DATA_DIR-relative path of a project's status.md."""
    return f"projects/{project_id}/status.md"


def parse_front_matter(content: str | None) -> dict:
    """Parse a leading ``---\\n<yaml>\\n---`` front-matter block into a dict.

    Returns {} when content is None, has no front-matter, or the YAML is
    malformed / not a mapping. NEVER raises — a broken status.md degrades to
    "no human metadata", git-derived fields still populate.
    """
    if not content:
        return {}
    text = content.lstrip("﻿")  # tolerate a leading BOM
    if not text.startswith("---"):
        return {}
    # Strip the opening fence, then split on the closing one.
    body = text[len("---"):]
    parts = body.split("\n---", 1)
    yaml_block = parts[0]
    try:
        data = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        logger.warning("malformed status.md front-matter, ignoring: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _dump_front_matter(meta: dict, body: str = "") -> str:
    """Serialize meta back into a ``---\\n<yaml>\\n---\\n<body>`` document."""
    yaml_block = yaml.safe_dump(meta, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{yaml_block}\n---\n{body}"


def _split_doc(content: str | None) -> tuple[dict, str]:
    """Return (front-matter dict, markdown body) from a status.md document."""
    if not content:
        return {}, ""
    meta = parse_front_matter(content)
    text = content.lstrip("﻿")
    if text.startswith("---"):
        parts = text[len("---"):].split("\n---", 1)
        body = parts[1] if len(parts) > 1 else ""
        return meta, body.lstrip("\n")
    return meta, ""


def _load_meta(project_id: str) -> dict:
    """Read + parse ``projects/<id>/status.md`` front-matter. {} if absent/bad."""
    try:
        content = md_store.read(_status_md_rel(project_id))
    except Exception as exc:  # defensive: md_store should not crash discovery
        logger.warning("status.md read failed for %r: %s", project_id, exc)
        return {}
    return parse_front_matter(content)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Tracked-project discovery (config built-ins + registered status.md dirs)      #
# --------------------------------------------------------------------------- #
def _tracked_repos() -> dict[str, str]:
    """id -> repo-path for ALL tracked projects: config built-ins + registered.

    Built-ins come from ``settings.project_repos``. Registered projects are
    ``projects/<id>/status.md`` dirs whose front-matter carries a ``repo:``
    pointer (written by register_project). Registered entries override built-ins
    on id collision (the human file is the more recent source of truth).
    """
    repos: dict[str, str] = dict(settings.project_repos or {})
    projects_dir = settings.projects_dir
    if projects_dir.is_dir():
        for child in sorted(projects_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                # Hidden dirs (.claude agent-memory, .git, ...) are never projects.
                # They land under DATA_DIR but must not surface as phantom projects
                # (honest-mirror, SPEC §0). A real project id is a slug() result,
                # which never starts with a dot.
                continue
            pid = child.name
            meta = _load_meta(pid)
            repo = meta.get("repo")
            if isinstance(repo, str) and repo.strip():
                repo = repo.strip()
                # Stale-path fallback (3B layer-4): if the status.md repo: path no
                # longer exists BUT pid is a config built-in, keep the config path
                # — a stale/moved status.md pointer must NOT kill an otherwise-
                # tracked project (it would read as dead/commits=0). The config
                # path is the more reliable source when the recorded one is gone.
                if not Path(repo).expanduser().is_dir() and pid in repos:
                    logger.warning(
                        "project %r status.md repo path %r missing — falling back to config path %r",
                        pid, repo, repos[pid],
                    )
                else:
                    repos[pid] = repo
            elif pid not in repos:
                # status.md with no repo pointer → notes-only project (no repo).
                repos[pid] = str(child)
    return repos


def _is_abandoned(meta: dict) -> bool:
    return bool(meta.get("abandoned") is True)


# --------------------------------------------------------------------------- #
# read_one in-process cache (perf — git fan-out is the app's #1 cost)           #
# --------------------------------------------------------------------------- #
# read_one() spawns ~5 git subprocesses per project; list_projects/list_abandoned
# loop it over every tracked repo, so Home/Projects/Brief each pay 35-42 forks per
# request (measured: /brief 325ms, Home 288ms). Cache the built ProjectStatus keyed
# by a CHEAP signature that changes exactly when the underlying data changes:
#   - the repo's git ref state (.git/HEAD + the current branch's ref file mtime/size
#     — a new commit or branch switch bumps these; NO subprocess), and
#   - the project's status.md mtime/size (meta edits).
# Same pattern as claude_usage/transcripts.py `_CACHE`. Mutating ops (register/
# abandon/refresh) call _invalidate() so they never serve stale data.
_STATUS_CACHE: dict[str, tuple[tuple, ProjectStatus]] = {}


def _git_dir(repo_path: Path) -> Path | None:
    """The repo's .git dir (handles both a real dir and a `gitdir:` file/worktree).
    None if absent — caller then falls back to a signature that always re-reads."""
    g = repo_path / ".git"
    if g.is_dir():
        return g
    if g.is_file():
        try:
            txt = g.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if txt.startswith("gitdir:"):
            p = Path(txt[len("gitdir:"):].strip())
            if not p.is_absolute():
                p = (repo_path / p).resolve()
            return p if p.exists() else None
    return None


def _stat_sig(p: Path) -> tuple:
    """(mtime_ns, size) for a file, or () if it can't be stat'd (→ no cache hit)."""
    try:
        st = p.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return ()


def _cache_key(project_id: str, repo_path: str) -> tuple | None:
    """Cheap fingerprint of everything read_one depends on. None → don't cache
    (e.g. .git missing) so a non-git / unreadable repo always reads fresh."""
    repo = Path(repo_path)
    gdir = _git_dir(repo)
    if gdir is None:
        return None
    parts: list = [project_id]
    # HEAD pointer (branch switch / detached) + the ref it points at (new commit).
    head = gdir / "HEAD"
    parts.append(_stat_sig(head))
    try:
        head_txt = head.read_text(encoding="utf-8").strip()
    except OSError:
        head_txt = ""
    if head_txt.startswith("ref:"):
        ref_rel = head_txt[len("ref:"):].strip()
        parts.append(_stat_sig(gdir / ref_rel))
        # packed-refs covers the case where the loose ref file doesn't exist yet
        parts.append(_stat_sig(gdir / "packed-refs"))
    # status.md meta (desc / abandoned flags / lastAuto)
    parts.append(_stat_sig(Path(settings.data_dir) / _status_md_rel(project_id)))
    return tuple(parts)


def _invalidate(project_id: str | None = None) -> None:
    """Drop cached status for one project (or all). Called by mutating ops."""
    if project_id is None:
        _STATUS_CACHE.clear()
    else:
        _STATUS_CACHE.pop(project_id, None)


def read_one(project_id: str, repo_path: str) -> ProjectStatus:
    """Build a ProjectStatus for one tracked project (meta + read-only git).

    The reader derives id from the repo folder name; we override it with the
    canonical tracked id (config key / status.md dir name) so list/get are
    addressable by a stable id even if the folder name differs from the slug.

    Cached by a cheap git-ref + status.md signature: an unchanged repo returns the
    prior ProjectStatus without spawning any git subprocess (the app's hottest cost).
    """
    key = _cache_key(project_id, repo_path)
    if key is not None:
        cached = _STATUS_CACHE.get(project_id)
        if cached is not None and cached[0] == key:
            return cached[1]

    meta = _load_meta(project_id)
    status = reader.read_project(repo_path, meta=meta)
    if status.id != project_id:
        status = status.model_copy(update={"id": project_id})

    if key is not None:
        _STATUS_CACHE[project_id] = (key, status)
    return status


def list_projects() -> tuple[list[ProjectStatus], list[str]]:
    """All tracked, NON-abandoned projects as ProjectStatus + collected warnings.

    Never raises: a single bad project yields a dead status + a warning string;
    abandoned projects are excluded (they live in the graveyard, S4). Returns
    ([], []) when nothing is tracked.
    """
    statuses: list[ProjectStatus] = []
    warnings: list[str] = []
    for project_id, repo_path in sorted(_tracked_repos().items()):
        meta = _load_meta(project_id)
        if _is_abandoned(meta):
            continue  # excluded from the default list (graveyard only)
        try:
            status = read_one(project_id, repo_path)
        except Exception as exc:  # last-resort: reader is fail-open, but never crash list
            logger.error("unexpected error reading project %r: %s", project_id, exc)
            warnings.append(f"{project_id}: unexpected read error ({exc})")
            continue
        if status.health == "dead":
            warnings.append(f"{project_id}: repo unreadable or inactive (health=dead)")
        statuses.append(status)
    return statuses, warnings


def get_project(project_id: str) -> ProjectStatus | None:
    """One project's status, or None if the id is not tracked. Includes abandoned."""
    repos = _tracked_repos()
    repo_path = repos.get(project_id)
    if repo_path is None:
        return None
    return read_one(project_id, repo_path)


def list_abandoned() -> tuple[list[tuple[ProjectStatus, dict]], list[str]]:
    """Abandoned projects as (ProjectStatus, raw status.md meta) pairs + warnings.

    The Graveyard (S8) reads this — it needs BOTH the derived status (health/name/
    repo) AND the raw abandon-metadata (abandonedReason/abandonedProgress/lesson/
    users) from status.md. Membership is the `abandoned` flag, NOT health=dead
    (orthogonal — abandon-orthogonal-to-health). Fail-open: a malformed abandoned
    project is skipped + warned, never crashes the list.
    """
    out: list[tuple[ProjectStatus, dict]] = []
    warnings: list[str] = []
    for project_id, repo_path in sorted(_tracked_repos().items()):
        meta = _load_meta(project_id)
        if not _is_abandoned(meta):
            continue
        try:
            status = read_one(project_id, repo_path)
        except Exception as exc:  # fail-open per project
            logger.error("graveyard: reading abandoned project %r failed: %s", project_id, exc)
            warnings.append(f"{project_id}: abandoned project unreadable ({exc})")
            continue
        out.append((status, meta))
    return out, warnings


# --------------------------------------------------------------------------- #
# Write paths (md_store = one git commit each) — called by the T2 router        #
# --------------------------------------------------------------------------- #
class ProjectError(Exception):
    """Raised by write helpers; router maps .code to an HTTP status."""

    def __init__(self, message: str, code: int = 400) -> None:
        super().__init__(message)
        self.code = code


def register_project(body: ProjectRegisterInput) -> ProjectStatus:
    """Register a project: derive id=slug(name), write status.md, return its status.

    Validates the repo path is an existing git repo (400 otherwise). id collision
    with an existing status.md → 409. Writes one md_store commit.
    """
    project_id = slug(body.name)
    repo_path = Path(body.repo).expanduser()
    if not reader._is_git_repo(repo_path):  # noqa: SLF001 — same package
        raise ProjectError(f"repo path is not an existing git repo: {body.repo}", code=400)
    if md_store.exists(_status_md_rel(project_id)):
        raise ProjectError(f"project id {project_id!r} already exists", code=409)

    meta: dict = {"name": body.name, "repo": str(repo_path)}
    if body.goal is not None:
        meta["desc"] = body.goal
    if body.progress is not None:
        meta["progress"] = body.progress
    if body.next is not None:
        meta["next"] = body.next
    if body.users is not None:
        meta["users"] = body.users

    md_store.write_file(
        _status_md_rel(project_id), _dump_front_matter(meta), f"register project {project_id}"
    )
    return read_one(project_id, str(repo_path))


def abandon_project(project_id: str, body: ProjectAbandonInput) -> ProjectStatus | None:
    """Flag a project abandoned in status.md (graveyard). None if id untracked.

    Orthogonal to commit-age health: sets abandoned/abandonedReason/abandonedAt/
    abandonedProgress. get_project still returns it; list_projects excludes it.
    """
    repos = _tracked_repos()
    repo_path = repos.get(project_id)
    if repo_path is None:
        return None

    content = md_store.read(_status_md_rel(project_id))
    meta, mbody = _split_doc(content)
    current_progress = meta.get("progress")
    meta["abandoned"] = True
    meta["abandonedReason"] = body.reason
    meta["abandonedAt"] = _now_iso()
    meta["abandonedProgress"] = (
        body.atProgress if body.atProgress is not None else current_progress
    )
    # Snapshot users at abandon-time (S8) so the reached/before-user graveyard
    # pattern stat is immune to later status.md edits (historical truth).
    current_users = meta.get("users")
    meta["abandonedUsers"] = current_users if isinstance(current_users, int) else 0
    # Graveyard lesson (S8) — what was learned. Only stored if provided (never fabricated).
    if body.lesson is not None and body.lesson.strip():
        meta["lesson"] = body.lesson.strip()
    # Ensure repo pointer persists so the project stays discoverable.
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(project_id), _dump_front_matter(meta, mbody), f"abandon project {project_id}"
    )
    return read_one(project_id, repo_path)


def restore_project(project_id: str) -> ProjectStatus | None:
    """Un-graveyard a project: clear abandoned* (abandoned/abandonedReason/
    abandonedAt/abandonedProgress/abandonedUsers) → it rejoins list_projects.
    PRESERVES `lesson` (hard-won history; persists if re-abandoned later).

    None if id untracked (router → 404). Idempotent: restoring a NON-abandoned
    project is a 200 no-op (no write, returns the project). One md_store commit
    only when something was actually cleared.
    """
    repos = _tracked_repos()
    repo_path = repos.get(project_id)
    if repo_path is None:
        return None

    content = md_store.read(_status_md_rel(project_id))
    meta, mbody = _split_doc(content)
    # Clear the abandon* flags → rejoins list_projects. PRESERVE `lesson` (hard-won
    # history; not shown on active screens, persists if re-abandoned). Membership
    # gate is `abandoned`, so we key the no-op check on it specifically.
    abandon_keys = ("abandoned", "abandonedReason", "abandonedAt", "abandonedProgress", "abandonedUsers")
    if not _is_abandoned(meta):
        # Not abandoned → no-op (idempotent restore). Return current status.
        return read_one(project_id, repo_path)
    for k in abandon_keys:
        meta.pop(k, None)
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(project_id), _dump_front_matter(meta, mbody), f"restore project {project_id}"
    )
    return read_one(project_id, repo_path)


def refresh_project(project_id: str) -> ProjectStatus | None:
    """Re-read git + stamp lastAuto into status.md. None if id untracked.

    Same code path the wiki-refresh routine (T3) calls. One md_store commit.
    """
    repos = _tracked_repos()
    repo_path = repos.get(project_id)
    if repo_path is None:
        return None

    content = md_store.read(_status_md_rel(project_id))
    meta, mbody = _split_doc(content)
    meta["lastAuto"] = _now_iso()
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(project_id), _dump_front_matter(meta, mbody), f"refresh project {project_id}"
    )
    _invalidate(project_id)  # explicit refresh = force fresh git read, never serve cache
    return read_one(project_id, repo_path)
