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
from typing import Any

import yaml

from core.config import settings
from store import md_store

from . import reader
from .reader import slug
from .schema import (
    ProjectAbandonInput,
    ProjectDevStat,
    ProjectRegisterInput,
    ProjectSource,
    ProjectStatus,
)

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
def _auto_repos() -> dict[str, str]:
    """PROJECTS-UNIFY T2 (#113): auto-discovered repos under DEV_TRACING_ROOTS.

    id=slug(basename) -> abs repo path, for every .git repo dev_activity scans.
    REUSES dev_activity's own scan helpers (lazy-imported to avoid a
    projects↔dev_activity import cycle — the #112 precedent) so the auto ids are
    EXACTLY the repos dev_activity tracks → they slug-join #112 correctly and
    collide-correctly with registered/config ids.

    DEV_TRACING_ROOTS unset → {} (backward-compat: the list is config+registered,
    the pre-#113 behavior, unchanged). Fail-soft: a discovery error → debug-log +
    skip that root, never crashes project discovery.
    """
    out: dict[str, str] = {}
    try:
        from modules.dev_activity import service as dev_service
        for root in dev_service.scan_roots():
            for repo_path in dev_service._find_repos(root):  # noqa: SLF001 — DRY: the one scan impl
                pid = slug(Path(repo_path).name)
                if not pid:
                    continue
                # first-wins within auto (deterministic by sorted roots/repos);
                # cross-source precedence is handled by the overlay order in _tracked_repos.
                out.setdefault(pid, repo_path)
    except Exception as exc:  # discovery must never crash the project list
        logger.debug("auto-discover (DEV_TRACING_ROOTS) skipped: %s", exc)
    return out


def _tracked_repos() -> dict[str, tuple[str, "ProjectSource"]]:
    """id -> (repo-path, source) for ALL tracked projects, 3-source merged.

    Sources, lowest→highest precedence (a later overlay wins an id collision):
      1. auto       — .git repos under DEV_TRACING_ROOTS (#113, fallback discovery)
      2. config     — ``settings.project_repos`` built-ins
      3. registered — ``projects/<id>/status.md`` dirs with a ``repo:`` pointer (manual)

    So registered status.md > config > auto: the human file / config is the more
    reliable truth; an auto entry only fills an id no human/config source claims.
    An auto entry shadowed by config/registered is dropped silently (debug, NOT a
    warning — NG5; this is a normal handled case, like the stale-path→config
    fallback below). DEV_TRACING_ROOTS unset → auto is {} → behavior == pre-#113.
    """
    # 1. auto (lowest) — seed, then config + registered overlay on top.
    repos: dict[str, tuple[str, "ProjectSource"]] = {
        pid: (path, "auto") for pid, path in _auto_repos().items()
    }
    # 2. config built-ins (override auto on collision).
    for pid, path in (settings.project_repos or {}).items():
        if pid in repos and repos[pid][1] == "auto":
            logger.debug("project %r: config built-in shadows the auto-discovered repo", pid)
        repos[pid] = (path, "config")
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
            # G7 — REGISTRATION IS status.md EXISTENCE (the module contract). A child
            # dir WITHOUT a status.md is NOT a registered project — skip it. Without
            # this, leaked dirs under projects_dir (test fixtures like /tmp/pytest-*,
            # crewly scaffolds) surface as phantom notes-only projects in prod (G7).
            if not (child / "status.md").is_file():
                continue
            meta = _load_meta(pid)
            repo = meta.get("repo")
            # G7 (real fix) — TEST-FIXTURE POLLUTION: a test run wrote status.md files
            # into the REAL md-store with repo: pointing at a pytest tmp dir
            # (/tmp/pytest-of-*/...) that no longer exists. Skip a project whose repo: is
            # a /tmp/pytest fixture path THAT DOESN'T RESOLVE (a dead fixture from a past
            # run). NARROW on purpose: a /tmp/pytest path that STILL resolves is a
            # legitimately-registered repo that happens to live in tmp (a test's own
            # repo) — keep it. And a non-/tmp dead path (a real moved/gone repo) is left
            # to the honest-dead stale-path handling below — we don't editorialize those.
            if isinstance(repo, str) and repo.strip():
                rp = repo.strip()
                if rp.startswith("/tmp/pytest") and not Path(rp).expanduser().is_dir():
                    logger.warning(
                        "skipping phantom project %r — repo %r is a dead pytest fixture "
                        "(G7 pollution leaked into the md-store)", pid, rp,
                    )
                    continue
            if isinstance(repo, str) and repo.strip():
                repo = repo.strip()
                # Stale-path fallback (3B layer-4): if the status.md repo: path no
                # longer exists BUT pid is a config built-in, keep the config path
                # — a stale/moved status.md pointer must NOT kill an otherwise-
                # tracked project (it would read as dead/commits=0). The config
                # path is the more reliable source when the recorded one is gone.
                if not Path(repo).expanduser().is_dir() and pid in repos:
                    # NG5: DEBUG, not WARNING — this stale-path→config-path fallback is a
                    # NORMAL handled case (the config path is the reliable source), not a
                    # warning-worthy event. At WARNING it fired 5× on every projects_list/
                    # brief/life_brief call, polluting MCP stderr (which precedes the JSON
                    # the agent reads). The fallback still works; it's just silent now.
                    # Keep the EXISTING source (config/auto) since we keep that path —
                    # we did NOT switch to the registered pointer (it's gone).
                    logger.debug(
                        "project %r status.md repo path %r missing — falling back to config path %r",
                        pid, repo, repos[pid][0],
                    )
                else:
                    # A real registered status.md with a live repo: pointer — registered wins.
                    repos[pid] = (repo, "registered")
            elif pid not in repos:
                # status.md with no repo pointer → notes-only project (no repo).
                # It's a registered project (it has a status.md), just repo-less.
                repos[pid] = (str(child), "registered")
    return repos


def _tracked_repo_paths() -> dict[str, str]:
    """id -> repo-path only (drops the source tag), for callers that don't need source
    (#112 dev_stat_for_project, abandon/restore/hide lookups). One source-of-truth via
    _tracked_repos() so the 3-source merge + precedence stays in ONE place."""
    return {pid: path for pid, (path, _src) in _tracked_repos().items()}


def _is_abandoned(meta: dict) -> bool:
    return bool(meta.get("abandoned") is True)


def _is_hidden(meta: dict) -> bool:
    """#113: the 'not-interested' flag. INDEPENDENT of abandoned (a dead project w/ a
    lesson) and of health=='dead' (git-derived) — abandon-orthogonal-to-health. A hidden
    project is excluded from list_projects but is NOT in the graveyard (that's abandoned)."""
    return bool(meta.get("hidden") is True)


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


def read_one(project_id: str, repo_path: str, source: ProjectSource = "config") -> ProjectStatus:
    """Build a ProjectStatus for one tracked project (meta + read-only git).

    The reader derives id from the repo folder name; we override it with the
    canonical tracked id (config key / status.md dir name) so list/get are
    addressable by a stable id even if the folder name differs from the slug.

    #113: stamps ``source`` (config|registered|auto — passed by the caller from the
    3-source _tracked_repos merge) and ``hidden`` (from status.md meta) onto the status.

    Cached by a cheap git-ref + status.md signature (which INCLUDES status.md mtime →
    a hide/unhide write invalidates it): an unchanged repo returns the prior
    ProjectStatus without spawning any git subprocess (the app's hottest cost).
    """
    key = _cache_key(project_id, repo_path)
    if key is not None:
        cached = _STATUS_CACHE.get(project_id)
        if cached is not None and cached[0] == key:
            return cached[1]

    meta = _load_meta(project_id)
    status = reader.read_project(repo_path, meta=meta)
    updates: dict[str, Any] = {"source": source, "hidden": _is_hidden(meta)}
    if status.id != project_id:
        updates["id"] = project_id
    status = status.model_copy(update=updates)

    if key is not None:
        _STATUS_CACHE[project_id] = (key, status)
    return status


def list_projects(include_hidden: bool = False) -> tuple[list[ProjectStatus], list[str]]:
    """Tracked projects as ProjectStatus + collected warnings.

    Excludes BOTH abandoned (graveyard, S4) AND hidden (#113 not-interested) — two
    INDEPENDENT flags. ``include_hidden=True`` keeps hidden projects in the result (the
    view to un-hide from); abandoned stays excluded regardless (the graveyard is its
    own surface). Never raises: a single bad project yields a dead status + a warning
    string. Returns ([], []) when nothing is tracked.
    """
    statuses: list[ProjectStatus] = []
    warnings: list[str] = []
    for project_id, (repo_path, source) in sorted(_tracked_repos().items()):
        meta = _load_meta(project_id)
        if _is_abandoned(meta):
            continue  # excluded from the default list (graveyard only)
        if _is_hidden(meta) and not include_hidden:
            continue  # #113: not-interested — excluded unless explicitly requested
        try:
            status = read_one(project_id, repo_path, source)
        except Exception as exc:  # last-resort: reader is fail-open, but never crash list
            logger.error("unexpected error reading project %r: %s", project_id, exc)
            warnings.append(f"{project_id}: unexpected read error ({exc})")
            continue
        if status.health == "dead":
            warnings.append(f"{project_id}: repo unreadable or inactive (health=dead)")
        statuses.append(status)
    return statuses, warnings


def get_project(project_id: str) -> ProjectStatus | None:
    """One project's status, or None if the id is not tracked. Includes abandoned.

    #105 case-insensitive / name-or-id: the tracked keys are lowercase slugs
    (``reader.slug(folder_name)``). An agent naturally passes the human-readable ``name``
    from projects_list ("ClaudeManager") or any case variant — so we ``slug()`` the INPUT the
    same way before the dict lookup. "ClaudeManager", "claudemanager", "CLAUDEMANAGER", and a
    spaced/punctuated "Claude Manager" all resolve to the same project. The stored id scheme is
    unchanged (slugs stay lowercase) — we only match the input case-insensitively.

    This is the single lookup chokepoint: ``get_context`` (and thus REST /{id}, /{id}/context
    + the MCP project_get/project_context tools) route through here, so all inherit the fix.
    """
    repos = _tracked_repos()
    key = slug(project_id) if project_id else ""
    entry = repos.get(key)
    if entry is None:
        return None
    repo_path, source = entry
    return read_one(key, repo_path, source)


def get_context(project_id: str, notes_limit: int = 10) -> dict[str, Any] | None:
    """PROJECT-MEMORY (#42): a project's full context for an agent — its metadata PLUS its accumulated
    wiki notes ("project memory"), so the agent reasons WITH the project's notes. Composes
    ``get_project`` (the status/metadata) + ``wiki.reader.project_notes`` (notes tagged
    ``project:<id>``, lean, newest first, top ``notes_limit``).

    Returns ``{project: <metadata>, notes: [{id,title,status,updated,snippet}], noteCount}``; a
    project with ZERO tagged notes → ``notes: []`` (honest-empty, not omitted). An UNTRACKED project
    → ``None`` (the caller 404s / returns found:False — never fabricates a project). project_get stays
    LEAN; this is the dedicated "everything about X" call.

    The ONE compose impl behind BOTH the REST /projects/{id}/context endpoint and the MCP
    project_context tool → they're byte-identical by construction (#24)."""
    status = get_project(project_id)
    if status is None:
        return None
    # lazy import: the wiki reader (the project_notes tag-filter lives in the wiki module).
    # #105: use the CANONICAL slug (status.id), not the raw input — so a mixed-case/name-form
    # query resolves BOTH the metadata AND the project:<slug>-tagged notes (notes are tagged
    # with the lowercase slug). get_project already canonicalized status.id.
    from modules.wiki import reader as wiki_reader
    notes = wiki_reader.project_notes(status.id, limit=notes_limit)
    return {
        "project": status.model_dump(),
        "notes": notes,
        "noteCount": len(notes),
    }


# --------------------------------------------------------------------------- #
# PROJECTS-UNIFY T1 (#112): per-project dev-activity, JOINED by slug.            #
# projects id = slug(folder) (lowercase); dev_activity stores repo = basename    #
# RAW-case. The join key = slug(dev_activity.repo) == project_id, at the READ     #
# layer ONLY (dev_activity's basename storage is git-honest, unchanged). honest-  #
# not-found when the repo isn't scanned (NOT a fake 0); slug-collision → both +   #
# warning. The ONE impl behind REST GET /{id}/dev-activity + the MCP tool (#24).  #
# --------------------------------------------------------------------------- #
_DEV_STAT_DEFAULT_DAYS = 90  # the dev_activity default window (mirrors dev_activity.reader._DEFAULT_DAYS)


def dev_stat_for_project(project_id: str, days: int = _DEV_STAT_DEFAULT_DAYS) -> "ProjectDevStat":
    """A project's dev-activity over the last ``days`` VN-days, JOINED by slug(repo)==project_id.

    Lazy-imports dev_activity (store + the VN window helpers) to avoid a projects↔dev_activity import
    cycle (the market↔macro precedent). Reads dev_activity.store.rows_since(window_start) → filters to
    rows whose slug(repo) == the canonical project slug → aggregates commits / locNet / lastActiveDay /
    activeDays, grouped by the RAW repo basename (so a slug-collision returns BOTH, each tagged).

    honest-mirror: a project whose repo is NOT in the dev_activity scan (not in DEV_TRACING_ROOTS) →
    found=false, commits=0, reason (NEVER a fabricated 0-as-if-real). A slug-collision (≥2 repos →
    same slug) → found=true, summed, + a warning + the per-repo matches (not silently merged).

    ``days`` is clamped to ≥1 (the window is at least today). ``project_id`` is slugified (case-
    insensitive, the #105 lookup convention) before the match."""
    from .schema import RepoDevStat  # ProjectDevStat is imported at module top
    days = max(1, int(days))
    key = slug(project_id) if project_id else ""

    # lazy import (avoid the cycle) — the store read + the VN window helpers.
    from datetime import timedelta
    from modules.dev_activity import store as dev_store
    from modules.dev_activity import service as dev_service

    today_vn = dev_service._now().astimezone(dev_service.VN_TZ).date()
    since = (today_vn - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = dev_store.rows_since(since)

    # group matched rows by RAW repo basename (distinguishes a slug-collision).
    by_repo: dict[str, dict] = {}
    for r in rows:
        if slug(r["repo"]) != key:
            continue
        agg = by_repo.setdefault(r["repo"], {"commits": 0, "locNet": 0, "days": set(),
                                             "lastActiveDay": None})
        agg["commits"] += int(r["commits"])
        agg["locNet"] += int(r["loc_added"]) - int(r["loc_deleted"])
        if int(r["commits"]) > 0 or int(r["loc_added"]) or int(r["loc_deleted"]):
            agg["days"].add(r["date"])
            if agg["lastActiveDay"] is None or r["date"] > agg["lastActiveDay"]:
                agg["lastActiveDay"] = r["date"]

    if not by_repo:
        # HONEST not-found: the project's repo isn't in the dev_activity scan (NOT a fake 0).
        return ProjectDevStat(
            projectId=key, found=False, commits=0, locNet=0, lastActiveDay=None,
            days=days, activeDays=0, matches=[],
            reason="repo not in the dev_activity scan (not in DEV_TRACING_ROOTS / not scanned yet)",
            warning=None)  # explicit (no pydantic mypy plugin → defaulted fields read as required)

    matches = [
        RepoDevStat(repo=repo, commits=a["commits"], locNet=a["locNet"],
                    lastActiveDay=a["lastActiveDay"], activeDays=len(a["days"]))
        for repo, a in sorted(by_repo.items())
    ]
    all_days: set[str] = set()
    for a in by_repo.values():
        all_days |= a["days"]
    last_active = max((a["lastActiveDay"] for a in by_repo.values() if a["lastActiveDay"]),
                      default=None)
    warning = None
    if len(matches) > 1:  # slug-collision — honest, not silently merged
        warning = (f"slug-collision: {len(matches)} repos share the slug {key!r} "
                   f"({', '.join(m.repo for m in matches)}) — stats are SUMMED; see matches[] per-repo")
    return ProjectDevStat(
        projectId=key, found=True,
        commits=sum(m.commits for m in matches),
        locNet=sum(m.locNet for m in matches),
        lastActiveDay=last_active, days=days, activeDays=len(all_days),
        matches=matches, warning=warning, reason=None)  # explicit (no pydantic mypy plugin)


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
    for project_id, (repo_path, source) in sorted(_tracked_repos().items()):
        meta = _load_meta(project_id)
        if not _is_abandoned(meta):
            continue
        try:
            status = read_one(project_id, repo_path, source)
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
    return read_one(project_id, str(repo_path), "registered")


def abandon_project(project_id: str, body: ProjectAbandonInput) -> ProjectStatus | None:
    """Flag a project abandoned in status.md (graveyard). None if id untracked.

    Orthogonal to commit-age health: sets abandoned/abandonedReason/abandonedAt/
    abandonedProgress. get_project still returns it; list_projects excludes it.
    """
    repos = _tracked_repos()
    entry = repos.get(project_id)
    if entry is None:
        return None
    repo_path, source = entry

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
    return read_one(project_id, repo_path, source)


def restore_project(project_id: str) -> ProjectStatus | None:
    """Un-graveyard a project: clear abandoned* (abandoned/abandonedReason/
    abandonedAt/abandonedProgress/abandonedUsers) → it rejoins list_projects.
    PRESERVES `lesson` (hard-won history; persists if re-abandoned later).

    None if id untracked (router → 404). Idempotent: restoring a NON-abandoned
    project is a 200 no-op (no write, returns the project). One md_store commit
    only when something was actually cleared.
    """
    repos = _tracked_repos()
    entry = repos.get(project_id)
    if entry is None:
        return None
    repo_path, source = entry

    content = md_store.read(_status_md_rel(project_id))
    meta, mbody = _split_doc(content)
    # Clear the abandon* flags → rejoins list_projects. PRESERVE `lesson` (hard-won
    # history; not shown on active screens, persists if re-abandoned). Membership
    # gate is `abandoned`, so we key the no-op check on it specifically.
    abandon_keys = ("abandoned", "abandonedReason", "abandonedAt", "abandonedProgress", "abandonedUsers")
    if not _is_abandoned(meta):
        # Not abandoned → no-op (idempotent restore). Return current status.
        return read_one(project_id, repo_path, source)
    for k in abandon_keys:
        meta.pop(k, None)
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(project_id), _dump_front_matter(meta, mbody), f"restore project {project_id}"
    )
    return read_one(project_id, repo_path, source)


def refresh_project(project_id: str) -> ProjectStatus | None:
    """Re-read git + stamp lastAuto into status.md. None if id untracked.

    Same code path the wiki-refresh routine (T3) calls. One md_store commit.
    """
    repos = _tracked_repos()
    entry = repos.get(project_id)
    if entry is None:
        return None
    repo_path, source = entry

    content = md_store.read(_status_md_rel(project_id))
    meta, mbody = _split_doc(content)
    meta["lastAuto"] = _now_iso()
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(project_id), _dump_front_matter(meta, mbody), f"refresh project {project_id}"
    )
    _invalidate(project_id)  # explicit refresh = force fresh git read, never serve cache
    return read_one(project_id, repo_path, source)


def hide_project(project_id: str) -> ProjectStatus | None:
    """#113: mark a project NOT-INTERESTED → excluded from list_projects (still in
    ?include=hidden). None if id untracked (router → 404). Idempotent: hiding an
    already-hidden project is a 200 no-op (no write).

    INDEPENDENT of abandoned (a hidden project is NOT in the graveyard). Scoped-write:
    writes ONLY this id's status.md — for an auto-repo with NO status.md it creates a
    MINIMAL one ({hidden:true, repo:<path>}); for an existing status.md it sets the flag,
    preserving all other front-matter + the body. NO status.md is created for any OTHER
    repo (no spam — per scoped-write discipline)."""
    repos = _tracked_repos()
    entry = repos.get(slug(project_id) if project_id else "")
    if entry is None:
        return None
    key = slug(project_id)
    repo_path, source = entry

    content = md_store.read(_status_md_rel(key))  # None for an auto-repo with no status.md
    meta, mbody = _split_doc(content)
    if _is_hidden(meta):
        return read_one(key, repo_path, source)  # idempotent no-op (no write)
    meta["hidden"] = True
    # Persist the repo pointer so an auto-repo stays resolvable after we write its status.md
    # (it now has one → it's a 'registered' dir on disk, but source stays whatever it was
    # discovered as until the next _tracked_repos read; the repo: pointer keeps it findable).
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(key), _dump_front_matter(meta, mbody), f"hide project {key}"
    )
    _invalidate(key)
    # re-read source from the merge (creating status.md may reclassify an auto-repo as
    # registered) so the returned status reports the now-true source.
    new_entry = _tracked_repos().get(key)
    new_source = new_entry[1] if new_entry else source
    return read_one(key, repo_path, new_source)


def unhide_project(project_id: str) -> ProjectStatus | None:
    """#113: clear the not-interested flag → the project rejoins list_projects. None if id
    untracked (router → 404). Idempotent: unhiding a NOT-hidden project is a 200 no-op (no
    write). Scoped-write: clears ONLY this id's status.md `hidden` key, preserving everything
    else (we do NOT delete the status.md even if it becomes minimal — a written file is a
    human record)."""
    repos = _tracked_repos()
    entry = repos.get(slug(project_id) if project_id else "")
    if entry is None:
        return None
    key = slug(project_id)
    repo_path, source = entry

    content = md_store.read(_status_md_rel(key))
    meta, mbody = _split_doc(content)
    if not _is_hidden(meta):
        return read_one(key, repo_path, source)  # idempotent no-op (no write)
    meta.pop("hidden", None)
    meta.setdefault("repo", repo_path)
    md_store.write_file(
        _status_md_rel(key), _dump_front_matter(meta, mbody), f"unhide project {key}"
    )
    _invalidate(key)
    return read_one(key, repo_path, source)
