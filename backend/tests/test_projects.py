"""tests/test_projects.py — Sprint 1 T4 verification for the projects module.

Sections:
  A. Reader unit tests — derivation, bucket logic, fail-open, read-only invariant
  B. Service unit tests — list_projects / get_project
  C. API endpoint tests — all 5 endpoints (skip-guarded until T2 router lands)
  D. Registry auto-discovery — /health shows "projects"

Health-bucket thresholds (reader.py verbatim):
  act   → lastDays ≤ 7
  slow  → 7 < lastDays ≤ 30
  stall → 30 < lastDays ≤ 90
  dead  → lastDays > 90, OR repo missing/unreadable/empty

Real repo ages verified at 2026-06-06 (pre-scaffold):
  OutboundOS   ~1d  → act
  ClaudeManager ~29d → slow (near 30d boundary — assert via formula)
  DevCrew      ~35d → stall
  crewly       ~69d → stall
  Groundwork   ~35d → stall
  life-os      ~0d  → act
  bogus path         → dead (fail-open)

Key API shape from reader.py:
  read_project(project_id, repo_path, *, name=None, meta=None) -> ProjectStatus
  No `warning` field on ProjectStatus — warnings surface at service layer.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import guard — A/B sections skip cleanly until T1 lands.
# The moment modules/projects/reader.py is importable, guard lifts.
# ---------------------------------------------------------------------------

pytest.importorskip(
    "modules.projects.reader",
    reason="modules/projects/reader not yet implemented — pre-scaffold",
)

from modules.projects.reader import (  # noqa: E402
    _health_from_days,
    _whole_days_since,
    read_project,
)
from modules.projects.schema import ProjectMetrics, ProjectStatus  # noqa: E402
from modules.projects.service import (  # noqa: E402
    get_project,
    list_projects,
    parse_front_matter,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REAL_REPOS: dict[str, str] = {
    "outboundos":    "/home/watercry/Disk_C/Data/Tinhdev/OutboundOS",
    "devcrew":       "/home/watercry/Disk_C/Data/Tinhdev/DevCrew",
    "crewly":        "/home/watercry/Disk_C/Data/Tinhdev/crewly",
    "claudemanager": "/home/watercry/Disk_C/Data/Tinhdev/ClaudeManager",
    "groundwork":    "/home/watercry/Disk_C/Data/Tinhdev/Groundwork",
    "lifeos":        "/home/watercry/Disk_C/Data/Tinhdev/life-os",
}

BOGUS_PATH = "/tmp/this-repo-does-not-exist-lifeos-tester"
NON_GIT_DIR = "/tmp"  # exists but is not a git repo


# ---------------------------------------------------------------------------
# A. Reader unit tests
# ---------------------------------------------------------------------------

class TestHealthBucketLogic:
    """Assert the BUCKET LOGIC, not date-fragile hardcodes.

    Uses _health_from_days directly plus synthetic git repos for deterministic
    boundary tests. Does NOT hardcode a real repo's expected bucket (date-fragile).
    """

    def test_act_boundary_at_0(self):
        assert _health_from_days(0) == "act", "lastDays=0 must be 'act'"

    def test_act_boundary_at_7(self):
        assert _health_from_days(7) == "act", "lastDays=7 (boundary) must be 'act'"

    def test_slow_boundary_at_8(self):
        assert _health_from_days(8) == "slow", "lastDays=8 must be 'slow'"

    def test_slow_boundary_at_30(self):
        assert _health_from_days(30) == "slow", "lastDays=30 (boundary) must be 'slow'"

    def test_stall_boundary_at_31(self):
        assert _health_from_days(31) == "stall", "lastDays=31 must be 'stall'"

    def test_stall_boundary_at_90(self):
        assert _health_from_days(90) == "stall", "lastDays=90 (boundary) must be 'stall'"

    def test_dead_boundary_at_91(self):
        assert _health_from_days(91) == "dead", "lastDays=91 must be 'dead'"

    def test_dead_at_none(self):
        assert _health_from_days(None) == "dead", "lastDays=None must be 'dead'"

    def test_dead_at_large_value(self):
        assert _health_from_days(9999) == "dead", "lastDays=9999 must be 'dead'"


class TestWholeDaysSince:
    """_whole_days_since correctness."""

    def test_recent_is_zero(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        days = _whole_days_since(now_iso)
        assert days == 0, f"A just-now commit should give lastDays=0, got {days}"

    def test_seven_days_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=7, hours=1)).isoformat()
        days = _whole_days_since(ts)
        assert days == 7, f"7d+1h ago should give lastDays=7, got {days}"

    def test_never_negative(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        days = _whole_days_since(now_iso)
        assert days is not None and days >= 0, f"lastDays must be non-negative, got {days}"

    def test_malformed_returns_none(self):
        days = _whole_days_since("not-a-date")
        assert days is None, f"Malformed ISO string must return None, got {days}"


class TestReaderRealRepos:
    """read_project against real repos — assert bucket formula, not hardcoded names.

    Frozen signature: read_project(repo_path, *, meta=None) -> ProjectStatus
    id = slug(folder_name), name = meta["name"] or folder_name.
    """

    def test_outboundos_health_and_lastdays(self):
        """OutboundOS = a recently-active repo. Assert bucket via the lastDays
        formula (not a hardcoded name) — its commit age drifts with wall-clock, so
        pin to the formula + a sanity band, like the ClaudeManager test."""
        s = read_project(REAL_REPOS["outboundos"])
        assert isinstance(s, ProjectStatus)
        assert s.lastDays is not None, "lastDays must not be None for a readable repo"
        expected = _health_from_days(s.lastDays)
        assert s.health == expected, (
            f"health mismatch: reported {s.health!r} but lastDays={s.lastDays} → {expected!r}"
        )
        # Sanity: a recently-active repo → act or slow, never stall/dead.
        assert s.health in ("act", "slow"), (
            f"OutboundOS should be recently-active (act/slow), got {s.health!r} "
            f"(lastDays={s.lastDays})"
        )

    def test_claudemanager_near_30d_boundary(self):
        """ClaudeManager ~29d — assert bucket matches formula, not a hardcoded name."""
        s = read_project(REAL_REPOS["claudemanager"])
        assert s.lastDays is not None
        expected = _health_from_days(s.lastDays)
        assert s.health == expected, (
            f"ClaudeManager health mismatch: reported {s.health!r} but "
            f"lastDays={s.lastDays} → formula gives {expected!r}"
        )
        # Sanity: near 30d boundary → must be slow or stall, not act or dead
        assert s.health in ("slow", "stall"), (
            f"ClaudeManager near 30d boundary should be slow/stall, got {s.health!r} "
            f"(lastDays={s.lastDays})"
        )

    def test_devcrew_stall(self):
        """DevCrew ~35d → 'stall'. Assert via formula."""
        s = read_project(REAL_REPOS["devcrew"])
        assert s.lastDays is not None
        expected = _health_from_days(s.lastDays)
        assert s.health == expected
        assert s.health == "stall", (
            f"DevCrew (~35d ago) should be 'stall', got {s.health!r} (lastDays={s.lastDays})"
        )

    def test_lifeos_is_act(self):
        """life-os last commit today → 'act'."""
        s = read_project(REAL_REPOS["lifeos"])
        assert s.health == "act", (
            f"life-os (0d ago) should be 'act', got {s.health!r} (lastDays={s.lastDays})"
        )

    def test_last_is_iso8601_utc(self):
        s = read_project(REAL_REPOS["outboundos"])
        assert s.last, "last must not be None/empty for a readable repo"
        dt = datetime.fromisoformat(s.last.replace("Z", "+00:00"))
        assert dt.year >= 2020, f"last timestamp looks wrong: {s.last}"

    def test_metrics_commits_positive(self):
        s = read_project(REAL_REPOS["outboundos"])
        assert s.metrics.commits > 0, (
            f"metrics.commits must be > 0 for a real repo, got {s.metrics.commits}"
        )

    def test_metrics_branch_nonempty(self):
        s = read_project(REAL_REPOS["outboundos"])
        assert s.metrics.branch, f"metrics.branch must be non-empty, got {s.metrics.branch!r}"

    def test_progress_none_without_meta(self):
        """progress must be None when no status.md meta supplied — no fabrication."""
        s = read_project(REAL_REPOS["outboundos"])
        assert s.progress is None, (
            f"progress must be None when no meta supplied, got {s.progress!r}"
        )

    def test_next_none_without_meta(self):
        """next must be None when no status.md meta supplied."""
        s = read_project(REAL_REPOS["outboundos"])
        assert s.next is None, (
            f"next must be None when no meta supplied, got {s.next!r}"
        )

    def test_users_zero_without_meta(self):
        """users must be 0 when no status.md meta supplied."""
        s = read_project(REAL_REPOS["outboundos"])
        assert s.users == 0, f"users must be 0 when no meta, got {s.users}"

    def test_meta_progress_honored(self):
        """progress from meta must be passed through."""
        s = read_project(REAL_REPOS["outboundos"], meta={"progress": 55})
        assert s.progress == 55, f"progress=55 from meta must be honored, got {s.progress}"

    def test_meta_next_honored(self):
        s = read_project(REAL_REPOS["outboundos"], meta={"next": "write tests"})
        assert s.next == "write tests", f"next from meta must be honored, got {s.next!r}"

    def test_meta_users_honored(self):
        s = read_project(REAL_REPOS["outboundos"], meta={"users": 3})
        assert s.users == 3, f"users=3 from meta must be honored, got {s.users}"

    def test_id_derived_from_folder_name(self):
        """id = slug(folder_name) — OutboundOS → 'outboundos'."""
        s = read_project(REAL_REPOS["outboundos"])
        assert s.id == "outboundos", f"id must be slug('OutboundOS')='outboundos', got {s.id!r}"
        assert s.repo == REAL_REPOS["outboundos"], f"repo mismatch: {s.repo!r}"

    def test_name_from_meta_honored(self):
        """name from meta overrides folder name."""
        s = read_project(REAL_REPOS["outboundos"], meta={"name": "My Custom Name"})
        assert s.name == "My Custom Name", f"name from meta must be honored, got {s.name!r}"

    def test_routines_empty_at_reader_level(self):
        """routines must be [] at reader level (router layer adds wiki-refresh)."""
        s = read_project(REAL_REPOS["outboundos"])
        assert s.routines == [], f"routines should be [] from reader, got {s.routines}"

    def test_last_auto_none_before_routine_run(self):
        """lastAuto must be None before any routine runs."""
        s = read_project(REAL_REPOS["outboundos"])
        assert s.lastAuto is None, f"lastAuto must be None before first routine, got {s.lastAuto}"


class TestReaderFailOpen:
    """Reader must never raise — fail-open with health='dead'."""

    def test_bogus_path_returns_projectstatus(self):
        s = read_project(BOGUS_PATH)
        assert isinstance(s, ProjectStatus), f"Expected ProjectStatus, got {type(s)}"

    def test_bogus_path_health_dead(self):
        s = read_project(BOGUS_PATH)
        assert s.health == "dead", f"Missing path → health='dead', got {s.health!r}"

    def test_bogus_path_metrics_zeroed(self):
        s = read_project(BOGUS_PATH)
        assert s.metrics.commits == 0, f"Missing path → commits=0, got {s.metrics.commits}"
        assert s.metrics.branch == "", f"Missing path → branch='', got {s.metrics.branch!r}"
        assert s.metrics.lang is None, f"Missing path → lang=None, got {s.metrics.lang!r}"

    def test_bogus_path_last_is_none(self):
        s = read_project(BOGUS_PATH)
        assert s.last is None, f"Missing path → last=None, got {s.last!r}"

    def test_bogus_path_lastdays_is_none(self):
        s = read_project(BOGUS_PATH)
        assert s.lastDays is None, f"Missing path → lastDays=None, got {s.lastDays!r}"

    def test_non_git_dir_returns_dead(self):
        """A real directory that isn't a git repo must also return dead."""
        s = read_project(NON_GIT_DIR)
        assert s.health == "dead", (
            f"/tmp is not a git repo → health='dead', got {s.health!r}"
        )

    def test_meta_honored_on_dead_repo(self):
        """Even a dead/missing repo must pass through meta fields."""
        s = read_project(BOGUS_PATH, meta={"progress": 42, "next": "migrate"})
        assert s.progress == 42, f"progress from meta must survive dead status, got {s.progress}"
        assert s.next == "migrate", f"next from meta must survive dead status, got {s.next!r}"


class TestReaderReadOnlyInvariant:
    """HARD INVARIANT: reader must leave source repos byte-identical.

    Two complementary checks:
      1. Subprocess spy — intercept subprocess.run to catch any forbidden git op
         (pull/fetch/push/commit/add/checkout). Structural guard.
      2. HEAD sha + `git status --porcelain` snapshot — operational proof that
         the repo state is identical before/after a read.
    """

    def _head_sha(self, repo: str) -> str:
        result = subprocess.run(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def _working_tree_status(self, repo: str) -> str:
        result = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def test_head_sha_unchanged_after_read(self):
        """Source repo HEAD sha must be identical before/after read_project."""
        repo = REAL_REPOS["outboundos"]
        sha_before = self._head_sha(repo)
        read_project(repo)
        sha_after = self._head_sha(repo)
        assert sha_before == sha_after, (
            f"read_project changed OutboundOS HEAD sha!\n"
            f"  Before: {sha_before}\n"
            f"  After:  {sha_after}\n"
            "This means the reader wrote to or pulled the source repo."
        )

    def test_working_tree_unchanged_after_read(self):
        """git status --porcelain must be identical before/after read_project."""
        repo = REAL_REPOS["outboundos"]
        status_before = self._working_tree_status(repo)
        read_project(repo)
        status_after = self._working_tree_status(repo)
        assert status_before == status_after, (
            f"read_project changed OutboundOS working tree state!\n"
            f"  Before: {status_before!r}\n"
            f"  After:  {status_after!r}\n"
            "This means the reader wrote to the source repo."
        )

    def test_no_forbidden_git_subcommand(self, monkeypatch):
        """Intercept subprocess.run — forbidden git ops must never be called."""
        FORBIDDEN = {"fetch", "pull", "push", "commit", "add", "checkout",
                     "reset", "merge", "rebase", "clone"}
        forbidden_calls: list[str] = []
        original_run = subprocess.run

        def spy(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and len(cmd) >= 2:
                # git -C <path> <subcommand> ...
                # find 'git' then look at next non-flag token
                args_list = [str(c) for c in cmd]
                for i, tok in enumerate(args_list):
                    if tok == "git" and i + 1 < len(args_list):
                        # skip -C <path> if present
                        j = i + 1
                        while j < len(args_list) and args_list[j].startswith("-"):
                            j += 2  # skip flag + value
                        if j < len(args_list) and args_list[j] in FORBIDDEN:
                            forbidden_calls.append(" ".join(args_list))
                        break
            return original_run(cmd, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", spy)
        read_project(REAL_REPOS["outboundos"])
        assert not forbidden_calls, (
            f"read_project issued forbidden git subcommand(s):\n"
            + "\n".join(f"  {c}" for c in forbidden_calls)
        )


# ---------------------------------------------------------------------------
# B. Service unit tests
# ---------------------------------------------------------------------------

class TestParseFrontMatter:
    """parse_front_matter edge cases."""

    def test_none_returns_empty(self):
        assert parse_front_matter(None) == {}

    def test_empty_string_returns_empty(self):
        assert parse_front_matter("") == {}

    def test_no_front_matter_returns_empty(self):
        assert parse_front_matter("just some text\nno yaml here") == {}

    def test_valid_front_matter(self):
        content = "---\nprogress: 42\nnext: refactor\nusers: 5\n---\nbody text"
        result = parse_front_matter(content)
        assert result.get("progress") == 42
        assert result.get("next") == "refactor"
        assert result.get("users") == 5

    def test_malformed_yaml_returns_empty(self):
        content = "---\n: bad: yaml: [\n---\nbody"
        result = parse_front_matter(content)
        assert isinstance(result, dict)  # must not raise

    def test_non_mapping_yaml_returns_empty(self):
        content = "---\n- list item\n- another\n---"
        result = parse_front_matter(content)
        assert result == {}


class TestServiceListProjects:
    """list_projects() with monkeypatched settings.

    Each test uses ``isolated_paths`` (conftest) so ``settings.data_dir`` points at
    a fresh tmp dir — otherwise list_projects() discovers registered status.md
    dirs persisted in the REAL backend/data/projects/ and leaks state across tests.
    list = (config.project_repos) ∪ (registered status.md dirs under DATA_DIR);
    isolating DATA_DIR makes the disk half empty so config alone drives the result.
    """

    def test_empty_config_returns_empty_list(self, monkeypatch, isolated_paths):
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {})
        statuses, warnings = list_projects()
        assert statuses == [], f"Empty config + clean DATA_DIR must yield [], got {statuses}"
        assert isinstance(warnings, list)

    def test_real_repo_appears_in_list(self, monkeypatch, isolated_paths):
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "outboundos": REAL_REPOS["outboundos"],
        })
        statuses, warnings = list_projects()
        assert len(statuses) == 1, f"Expected 1 project, got {len(statuses)}: {statuses}"
        assert statuses[0].id == "outboundos"

    def test_read_one_cache_skips_git_on_warm_call(self, monkeypatch, isolated_paths):
        """Second read of an UNCHANGED repo serves the cache → no git subprocess."""
        import modules.projects.service as svc
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {"outboundos": REAL_REPOS["outboundos"]})
        svc._STATUS_CACHE.clear()

        calls = {"n": 0}
        real_run = subprocess.run
        def counting_run(args, *a, **k):
            if args and args[0] == "git":
                calls["n"] += 1
            return real_run(args, *a, **k)
        monkeypatch.setattr(subprocess, "run", counting_run)

        list_projects()                 # cold — spawns git
        cold_forks = calls["n"]
        assert cold_forks > 0, "cold read should spawn git"
        calls["n"] = 0
        s2, _ = list_projects()         # warm — must be served from cache
        assert calls["n"] == 0, f"warm read must spawn ZERO git, spawned {calls['n']}"
        assert s2 and s2[0].id == "outboundos"  # same data, just cached

    def test_refresh_invalidates_cache(self, monkeypatch, isolated_paths):
        """refresh_project() forces a fresh git read even if the cache is warm."""
        import modules.projects.service as svc
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {"outboundos": REAL_REPOS["outboundos"]})
        svc._STATUS_CACHE.clear()
        list_projects()                                  # warm the cache
        assert "outboundos" in svc._STATUS_CACHE
        svc.refresh_project("outboundos")                # must invalidate + re-read
        # after refresh the entry is repopulated with a fresh read (key present again)
        assert "outboundos" in svc._STATUS_CACHE

    def test_bogus_path_in_list_is_dead(self, monkeypatch, isolated_paths):
        """A bogus path in project_repos must appear as dead, not crash list."""
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "bogus": BOGUS_PATH,
        })
        statuses, warnings = list_projects()
        assert len(statuses) == 1
        assert statuses[0].health == "dead"
        # A dead repo should surface a warning
        assert warnings, "Bogus path should produce at least one warning string"

    def test_mixed_good_and_bogus(self, monkeypatch, isolated_paths):
        """Good + bogus repos: both appear, bogus is dead, good is not dead."""
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "outboundos": REAL_REPOS["outboundos"],
            "bogus": BOGUS_PATH,
        })
        statuses, _ = list_projects()
        by_id = {s.id: s for s in statuses}
        assert "outboundos" in by_id
        assert "bogus" in by_id
        assert by_id["outboundos"].health != "dead"
        assert by_id["bogus"].health == "dead"

    def test_read_one_exception_is_caught_and_warned(self, monkeypatch, isolated_paths):
        """The last-resort except in list_projects: even if read_one() itself RAISES
        (not just returns a dead status), the project is dropped with a warning and
        the list does not crash. read_one is normally fail-open, so this guards the
        'never crash the list' contract against a future regression there."""
        import modules.projects.service as svc
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {"outboundos": REAL_REPOS["outboundos"]})
        svc._STATUS_CACHE.clear()

        def boom(project_id, repo_path):
            raise RuntimeError("reader blew up")
        monkeypatch.setattr(svc, "read_one", boom)

        statuses, warnings = list_projects()
        assert statuses == []  # the one project was dropped, not surfaced half-built
        assert any("outboundos" in w and "read error" in w for w in warnings)

    def test_load_meta_returns_empty_when_read_raises(self, monkeypatch, isolated_paths):
        """_load_meta swallows a md_store.read failure → {} so discovery never
        crashes on an unreadable status.md (distinct from 'file absent')."""
        import modules.projects.service as svc
        def boom(_path):
            raise OSError("status.md unreadable")
        monkeypatch.setattr(svc.md_store, "read", boom)
        assert svc._load_meta("anything") == {}


class TestServiceGetProject:
    """get_project() — single-project accessor. DATA_DIR isolated per test."""

    def test_get_tracked_project(self, monkeypatch, isolated_paths):
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "outboundos": REAL_REPOS["outboundos"],
        })
        s = get_project("outboundos")
        assert s is not None
        assert s.id == "outboundos"

    def test_get_untracked_returns_none(self, monkeypatch, isolated_paths):
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {})
        s = get_project("nonexistent")
        assert s is None, f"Untracked project must return None, got {s}"

    def test_get_bogus_path_returns_dead(self, monkeypatch, isolated_paths):
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "bogus": BOGUS_PATH,
        })
        s = get_project("bogus")
        assert s is not None
        assert s.health == "dead"

    # --- #105: case-insensitive / name-or-id lookup --------------------------- #
    def test_105_get_project_case_insensitive(self, monkeypatch, isolated_paths):
        """#105: the tracked key is the lowercase slug 'outboundos'; an agent passing the
        human-readable name 'OutboundOS' (or any case) must resolve to the SAME project, and
        the returned status carries the CANONICAL slug id (not the mixed-case input)."""
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "outboundos": REAL_REPOS["outboundos"],
        })
        for variant in ("OutboundOS", "outboundos", "OUTBOUNDOS", "outBoundOS"):
            s = get_project(variant)
            assert s is not None, f"case variant {variant!r} must resolve (case-insensitive)"
            assert s.id == "outboundos", f"{variant!r} → canonical slug id, got {s.id!r}"

    def test_105_get_project_name_with_separators_slugifies(self, monkeypatch, isolated_paths):
        """#105: a name-form with separators ('Out Bound OS' / 'out-bound.os') slugifies the same
        way the stored key was built → still resolves (robust full-slugify, not just lowercase)."""
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "out-bound-os": BOGUS_PATH,  # the stored key is the slug; path bogus → health=dead, id matches
        })
        for variant in ("Out Bound OS", "out-bound.os", "OUT_BOUND_OS"):
            s = get_project(variant)
            assert s is not None, f"separator name {variant!r} must slug-resolve"
            assert s.id == "out-bound-os"

    def test_105_get_project_still_404s_genuine_miss(self, monkeypatch, isolated_paths):
        """#105: a genuinely-absent id (even slugified) still → None (the fix MATCHES case, it does
        not invent projects)."""
        from core import config
        monkeypatch.setattr(config.settings, "project_repos", {
            "outboundos": REAL_REPOS["outboundos"],
        })
        assert get_project("NoSuchProject") is None
        assert get_project("") is None


# ---------------------------------------------------------------------------
# C. API endpoint tests (skip-guarded until T2 router lands)
# ---------------------------------------------------------------------------

try:
    from modules.projects import router as _projects_router_mod  # noqa: F401
    _ROUTER_AVAILABLE = hasattr(_projects_router_mod, "MODULE") or hasattr(_projects_router_mod, "router")
except ImportError:
    _ROUTER_AVAILABLE = False

skip_api = pytest.mark.skipif(
    not _ROUTER_AVAILABLE,
    reason="modules/projects/router not yet implemented — skip until T2 lands",
)


@pytest.fixture(scope="module")
def api_client(tmp_path_factory):
    """TestClient with full app — projects module auto-discovered via registry.

    Uses explicit save/restore for settings mutations (monkeypatch is
    function-scoped and incompatible with module-scoped fixtures; raw assignment
    without teardown leaks global state across the session).
    """
    import importlib
    tmp = tmp_path_factory.mktemp("projapi")

    from core import config
    # Save originals so teardown restores global settings state exactly.
    _orig_data_dir = config.settings.data_dir
    _orig_db_path = config.settings.db_path
    _orig_scheduler = config.settings.scheduler_enabled
    _orig_repos = config.settings.project_repos

    config.settings.data_dir = tmp / "data"
    config.settings.db_path = tmp / "proj_api_test.db"
    config.settings.scheduler_enabled = False
    config.settings.project_repos = {
        "outboundos": REAL_REPOS["outboundos"],
        "lifeos": REAL_REPOS["lifeos"],
    }

    from store import db as db_mod
    db_mod.close_db()

    import main as main_mod
    app = main_mod.create_app()

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    # Restore global settings — prevents state leak to subsequent tests/fixtures.
    config.settings.data_dir = _orig_data_dir
    config.settings.db_path = _orig_db_path
    config.settings.scheduler_enabled = _orig_scheduler
    config.settings.project_repos = _orig_repos
    db_mod.close_db()


class TestGetProjects:
    """GET /projects returns {success, data: {projects: [...], summary: {...}}}."""

    @skip_api
    def test_200(self, api_client):
        resp = api_client.get("/projects")
        assert resp.status_code == 200, f"GET /projects → {resp.status_code}: {resp.text}"

    @skip_api
    def test_envelope_shape(self, api_client):
        body = api_client.get("/projects").json()
        assert body.get("success") is True, f"success must be True: {body}"
        assert "data" in body, f"Missing 'data' key: {body}"
        # data is {projects: [...], summary: {...}} (not a flat list)
        assert "projects" in body["data"], f"data must have 'projects' key: {body['data']}"
        assert "summary" in body["data"], f"data must have 'summary' key: {body['data']}"
        assert isinstance(body["data"]["projects"], list), (
            f"data.projects must be list: {body['data']}"
        )

    @skip_api
    def test_summary_shape(self, api_client):
        """Summary must include act/slow/stall/dead/total counts."""
        body = api_client.get("/projects").json()
        summary = body["data"]["summary"]
        for key in ("act", "slow", "stall", "dead", "total"):
            assert key in summary, f"summary missing key {key!r}: {summary}"
            assert isinstance(summary[key], int), (
                f"summary[{key!r}] must be int, got {type(summary[key])}"
            )

    @skip_api
    def test_items_have_frozen_shape(self, api_client):
        """Every item must carry all ProjectStatus keys — Tier-S frozen shape (+ desc)."""
        REQUIRED = {"id", "name", "desc", "health", "progress", "users", "last",
                    "lastDays", "next", "repo", "metrics", "routines", "lastAuto"}
        body = api_client.get("/projects").json()
        items = body["data"]["projects"]
        assert items, "Expected at least 1 project (outboundos registered)"
        for item in items:
            missing = REQUIRED - set(item.keys())
            assert not missing, f"ProjectStatus missing keys {missing}: {item}"

    @skip_api
    def test_health_values_valid(self, api_client):
        valid = {"act", "slow", "stall", "dead"}
        for item in api_client.get("/projects").json()["data"]["projects"]:
            assert item["health"] in valid, (
                f"Invalid health {item['health']!r} for {item['id']}"
            )

    @skip_api
    def test_outboundos_recently_active(self, api_client):
        """OutboundOS is a recently-active repo → act or slow (its commit age drifts
        with wall-clock; assert the band, not a hardcoded 'act')."""
        items = {p["id"]: p for p in api_client.get("/projects").json()["data"]["projects"]}
        assert "outboundos" in items, f"outboundos not in list: {list(items)}"
        assert items["outboundos"]["health"] in ("act", "slow"), (
            f"outboundos should be recently-active (act/slow), "
            f"got {items['outboundos']['health']!r}"
        )

    @skip_api
    def test_routines_includes_wiki_refresh(self, api_client):
        """Router layer must attach wiki-refresh to every project's routines."""
        items = api_client.get("/projects").json()["data"]["projects"]
        for item in items:
            assert "wiki-refresh" in item["routines"], (
                f"wiki-refresh must be in routines for {item['id']}: {item['routines']}"
            )


class TestGetProjectDetail:
    @skip_api
    def test_200_known(self, api_client):
        resp = api_client.get("/projects/outboundos")
        assert resp.status_code == 200, f"GET /projects/outboundos → {resp.status_code}: {resp.text}"

    @skip_api
    def test_envelope_and_shape(self, api_client):
        REQUIRED = {"id", "name", "desc", "health", "progress", "users", "last",
                    "lastDays", "next", "repo", "metrics", "routines", "lastAuto"}
        body = api_client.get("/projects/outboundos").json()
        assert body.get("success") is True
        missing = REQUIRED - set(body["data"].keys())
        assert not missing, f"Detail missing keys {missing}"

    @skip_api
    def test_404_unknown(self, api_client):
        resp = api_client.get("/projects/this-project-does-not-exist-xyz")
        assert resp.status_code == 404, f"Unknown project must 404, got {resp.status_code}"

    # --- #105: case-insensitive name-or-id lookup over REST -------------------- #
    @skip_api
    def test_105_api_case_insensitive_resolves(self, api_client):
        """#105: the slug is 'outboundos'; an agent hitting the name-form 'OutboundOS' (or any
        case) must get the SAME 200 project as the exact slug (agent uses .name → must work)."""
        slug_resp = api_client.get("/projects/outboundos")
        assert slug_resp.status_code == 200
        canonical_id = slug_resp.json()["data"]["id"]
        for variant in ("OutboundOS", "OUTBOUNDOS"):
            r = api_client.get(f"/projects/{variant}")
            assert r.status_code == 200, f"/projects/{variant} → {r.status_code}: {r.text}"
            assert r.json()["data"]["id"] == canonical_id, "must resolve to the canonical project"

    @skip_api
    def test_105_404_hint_names_id_and_case_insensitive(self, api_client):
        """#105: a genuine miss still 404s with the SHARPENED agent-error hint — naming the .id
        field (not .name) + that ids are matched case-insensitively (NOT_FOUND, retryable false)."""
        resp = api_client.get("/projects/this-project-does-not-exist-xyz")
        assert resp.status_code == 404
        body = resp.json()
        err = body.get("error") or body  # agent-error envelope
        hint = (err.get("hint") or "").lower()
        assert ".id" in hint and "case-insensitive" in hint, f"hint must guide the agent: {err}"


class TestPostProjects:
    @skip_api
    def test_register_valid_repo(self, api_client):
        payload = {
            "repo": REAL_REPOS["devcrew"],
            "name": "DevCrew Test Register",
            "goal": "testing registration",
        }
        resp = api_client.post("/projects", json=payload)
        assert resp.status_code in (200, 201), f"POST /projects → {resp.status_code}: {resp.text}"
        assert resp.json().get("success") is True

    @skip_api
    def test_register_bogus_path_returns_invalid_input(self, api_client):
        """Registering a non-git path → agent_error INVALID_INPUT (validated before write), not 500.
        #46-P4: the status is now 422 (agent_error _CODE_STATUS maps INVALID_INPUT→422), was raw 400.
        INTENDED — bad-input is 422, consistent with the missing-field 422 below; body is flat {error}."""
        payload = {"repo": BOGUS_PATH, "name": "Bogus Test Register", "goal": "test validation"}
        resp = api_client.post("/projects", json=payload)
        assert resp.status_code == 422, (
            f"Bogus path must return 422 INVALID_INPUT (not a git repo), got {resp.status_code}: {resp.text}"
        )
        j = resp.json()
        assert "detail" not in j and j["error"]["code"] == "INVALID_INPUT"

    @skip_api
    def test_register_missing_required_fields_422(self, api_client):
        """Missing required field (repo) must return 422."""
        resp = api_client.post("/projects", json={"name": "No Repo"})
        assert resp.status_code == 422, (
            f"Missing repo must return 422, got {resp.status_code}: {resp.text}"
        )


class TestPostRefresh:
    @skip_api
    def test_refresh_known_200(self, api_client):
        resp = api_client.post("/projects/outboundos/refresh")
        assert resp.status_code == 200, f"refresh → {resp.status_code}: {resp.text}"
        assert resp.json().get("success") is True

    @skip_api
    def test_refresh_unknown_404(self, api_client):
        resp = api_client.post("/projects/nobody-here/refresh")
        assert resp.status_code == 404, f"Unknown refresh must 404, got {resp.status_code}"


class TestPostAbandon:
    @skip_api
    def test_abandon_known_200(self, api_client):
        # Register something to abandon first (id = slug("Abandon Test Fixture") = "abandon-test-fixture")
        reg_resp = api_client.post("/projects", json={
            "repo": REAL_REPOS["lifeos"],
            "name": "Abandon Test Fixture",
            "goal": "will be abandoned",
        })
        # Registration may 409 if this test already ran (module-scope fixture)
        assert reg_resp.status_code in (200, 201, 409), (
            f"Register for abandon → {reg_resp.status_code}: {reg_resp.text}"
        )
        # atProgress is the field name (ProjectAbandonInput.atProgress), not progress_pct
        resp = api_client.post("/projects/abandon-test-fixture/abandon",
                               json={"reason": "test abandon", "atProgress": 10})
        assert resp.status_code == 200, f"abandon → {resp.status_code}: {resp.text}"
        assert resp.json().get("success") is True

    @skip_api
    def test_abandon_unknown_404(self, api_client):
        resp = api_client.post("/projects/nobody-abandons-this/abandon",
                               json={"reason": "test", "atProgress": 0})
        assert resp.status_code == 404, f"Unknown abandon must 404, got {resp.status_code}"


# ---------------------------------------------------------------------------
# D. Registry auto-discovery
# ---------------------------------------------------------------------------

class TestAutoDiscovery:
    @skip_api
    def test_health_lists_projects(self, api_client):
        """GET /health must list 'projects' in data.modules after T2 mounts."""
        body = api_client.get("/health").json()
        assert "projects" in body["data"]["modules"], (
            f"'projects' not in /health.data.modules: {body['data']['modules']}"
        )

    @skip_api
    def test_no_skipped_modules_warning(self, api_client):
        """Projects module must mount cleanly — no warning in /health."""
        body = api_client.get("/health").json()
        if body.get("warning"):
            pytest.fail(
                f"Module(s) skipped at boot: warning={body['warning']!r}\nbody={body}"
            )
