"""tests/test_settings.py — settings module (S12): AppConfig persistence + reader wiring.

BEHAVIOR-TESTED: defaults = current hardcoded values; PATCH partial-merge + round-trip;
fail-open read (absent/malformed → defaults); per-field validation; and the WIRING teeth
— idle_hunter reads idleThresholdDays (not literal-7), the master switch gates the
scheduled path but NOT the manual run. Persistence = md_store (1 commit).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.settings import service as cfg
from modules.settings.schema import AppConfig, AppConfigPatch


# --------------------------------------------------------------------------- #
# Defaults = current hardcoded behavior                                         #
# --------------------------------------------------------------------------- #
def test_defaults_match_current_behavior(isolated_paths):
    c = cfg.get_config()
    assert c.automationEnabled is True
    assert c.briefHour == 8            # morning-pull cron hour
    assert c.idleThresholdDays == 7    # idle_hunter literal
    assert c.patternCheckEnabled is True
    assert c.errorChannel == "inapp"
    assert c.timezone == "Asia/Ho_Chi_Minh"  # dispatch default
    assert c.displayName == ""                # dispatch default (stored-only, may be empty)
    assert c.wikiAgentAutonomous is False     # W4d: SAFE default OFF (proposals-only north-star)


def test_wiki_agent_autonomous_patch_round_trips(isolated_paths):
    """W4d toggle persists OFF→ON→OFF via md_store (a fresh read reflects it)."""
    cfg.set_config(AppConfigPatch(wikiAgentAutonomous=True))
    assert cfg.get_config().wikiAgentAutonomous is True
    cfg.set_config(AppConfigPatch(wikiAgentAutonomous=False))
    assert cfg.get_config().wikiAgentAutonomous is False


def test_absent_config_is_defaults(isolated_paths):
    """Nothing persisted → full defaults (fail-open), never 500."""
    assert cfg.get_config() == AppConfig()


# --------------------------------------------------------------------------- #
# PATCH partial-merge + round-trip                                              #
# --------------------------------------------------------------------------- #
def test_patch_partial_merge_persists(isolated_paths):
    cfg.set_config(AppConfigPatch(idleThresholdDays=14))
    c = cfg.get_config()
    assert c.idleThresholdDays == 14   # changed
    assert c.briefHour == 8            # untouched key keeps default


def test_patch_multiple_fields(isolated_paths):
    cfg.set_config(AppConfigPatch(briefHour=6, automationEnabled=False, displayName="Watercry"))
    c = cfg.get_config()
    assert c.briefHour == 6 and c.automationEnabled is False and c.displayName == "Watercry"
    assert c.idleThresholdDays == 7  # untouched


def test_patch_round_trips_via_fresh_read(isolated_paths):
    """A PATCH persists to md_store → a brand-new read reflects it."""
    cfg.set_config(AppConfigPatch(errorChannel="discord"))
    assert cfg.get_config().errorChannel == "discord"


def test_malformed_config_falls_back_to_defaults(isolated_paths):
    """A corrupt config.md → defaults (honest: can't trust the file), never crash."""
    from store import md_store
    md_store.write_file("settings/config.md", "---\nnot: [valid yaml\n", "corrupt")
    assert cfg.get_config() == AppConfig()


# --------------------------------------------------------------------------- #
# Per-field validation (schema boundary — router returns 422)                   #
# --------------------------------------------------------------------------- #
def test_briefhour_out_of_range_rejected():
    with pytest.raises(Exception):
        AppConfigPatch(briefHour=25)
    with pytest.raises(Exception):
        AppConfigPatch(briefHour=-1)


def test_idle_threshold_min_1():
    with pytest.raises(Exception):
        AppConfigPatch(idleThresholdDays=0)


def test_error_channel_enum():
    with pytest.raises(Exception):
        AppConfigPatch(errorChannel="email")  # not in discord|inapp|none


def test_unknown_field_forbidden():
    with pytest.raises(Exception):
        AppConfigPatch(bogusField=True)  # extra=forbid → 422


def test_blank_displayname_allowed():
    """displayName may be empty (dispatch default = "", stored-only) — NOT rejected."""
    p = AppConfigPatch(displayName="")
    assert p.displayName == ""


# --------------------------------------------------------------------------- #
# WIRING TEETH — idle_hunter reads the configured threshold (not literal-7)     #
# --------------------------------------------------------------------------- #
def _init_repo(path: Path, *, days_ago: int) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    from datetime import datetime, timedelta, timezone
    import os
    d = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    env = {**os.environ, "GIT_AUTHOR_DATE": d, "GIT_COMMITTER_DATE": d}
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)


def _seed_project(monkeypatch, repos, pid, repo):
    import yaml
    from modules.projects import service as proj
    from store import md_store
    monkeypatch.setattr(proj.settings, "project_repos", repos)
    fm = {"name": pid, "repo": str(repo)}
    md_store.write_file(f"projects/{pid}/status.md",
                        "---\n" + yaml.safe_dump(fm, sort_keys=True).strip() + "\n---\n", "seed")


def test_idle_hunter_reads_configured_threshold(monkeypatch, tmp_path, isolated_paths):
    """FILTERING DISTINGUISHING: two repos at different ages; threshold=20 keeps only the
    30d-idle one; threshold=100 keeps none; threshold=7 keeps both. Proves idle_hunter
    FILTERS against the CONFIG value (not a fixed literal), because the SET of projects
    that flag CHANGES when the threshold crosses a project-age boundary.

    team-lead sharpening (S12): use a threshold that CHANGES which projects pass the
    boundary — 40/100 pattern on the live server, 20/100 pattern here with synthetic repos.
    """
    from modules.automation import service as auto
    # Two synthetic repos: p_old=30d idle, p_new=10d idle
    repo_old = tmp_path / "p_old"; _init_repo(repo_old, days_ago=30)
    repo_new = tmp_path / "p_new"; _init_repo(repo_new, days_ago=10)
    _seed_project(monkeypatch,
                  {"p_old": str(repo_old), "p_new": str(repo_new)},
                  "p_old", repo_old)
    # also seed p_new
    import yaml
    from modules.projects import service as proj
    from store import md_store
    fm = {"name": "p_new", "repo": str(repo_new)}
    md_store.write_file("projects/p_new/status.md",
                        "---\n" + yaml.safe_dump(fm, sort_keys=True).strip() + "\n---\n", "seed")

    # threshold=20 → only p_old(30d) flags; p_new(10d) excluded
    cfg.set_config(AppConfigPatch(idleThresholdDays=20))
    status, detail = auto.idle_hunter()
    assert status == "warn" and "p_old" in detail and "p_new" not in detail

    # threshold=100 → neither flags (status=ok)
    cfg.set_config(AppConfigPatch(idleThresholdDays=100))
    assert auto.idle_hunter()[0] == "ok"

    # threshold=7 → both flag (config drives it, literal-7 is gone)
    cfg.set_config(AppConfigPatch(idleThresholdDays=7))
    status, detail = auto.idle_hunter()
    assert status == "warn" and "p_old" in detail and "p_new" in detail and ">7" in detail


# --------------------------------------------------------------------------- #
# WIRING TEETH — master switch gates SCHEDULED path, NOT manual run             #
# --------------------------------------------------------------------------- #
def test_automation_off_skips_scheduled(isolated_paths):
    """automationEnabled=False → run_scheduled no-ops (returns None, no run_log row)."""
    from modules.automation import service as auto
    cfg.set_config(AppConfigPatch(automationEnabled=False))
    result = auto.run_scheduled("idle-hunter", lambda: ("ok", "ran"))
    assert result is None  # skipped
    from store import db
    assert db.recent_runs("idle-hunter") == []  # no row recorded


def test_automation_on_runs_scheduled(isolated_paths):
    from modules.automation import service as auto
    cfg.set_config(AppConfigPatch(automationEnabled=True))
    result = auto.run_scheduled("idle-hunter", lambda: ("ok", "ran"))
    assert result is not None and result["status"] == "ok"


def test_manual_run_ignores_master_switch(monkeypatch, isolated_paths):
    """The MANUAL path (run_routine) runs even when automation is OFF — a manual run is an
    explicit user action, not the scheduler."""
    from modules.automation import service as auto
    from modules.projects import service as proj
    monkeypatch.setattr(proj.settings, "project_repos", {})
    cfg.set_config(AppConfigPatch(automationEnabled=False))
    run = auto.run_routine("idle-hunter")  # manual
    assert run is not None and run.status == "ok"  # ran despite automation OFF


def test_automation_on_fail_open(isolated_paths, monkeypatch):
    """settings read failing → automation_on defaults TRUE (don't silently disable)."""
    from modules.automation import service as auto
    monkeypatch.setattr(cfg, "get_config", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert auto.automation_on() is True


def test_pattern_check_on_default(isolated_paths):
    from modules.automation import service as auto
    assert auto.pattern_check_on() is True
    cfg.set_config(AppConfigPatch(patternCheckEnabled=False))
    assert auto.pattern_check_on() is False
