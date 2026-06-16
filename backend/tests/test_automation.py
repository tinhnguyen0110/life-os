"""tests/test_automation.py — routines + run-record wrapper + automation service (S10A).

Tests INVOKE routine funcs DIRECTLY + assert the run_log row — NEVER a real timer
(scheduler enabled=False). Each algorithm on a fixture; fail-soft on raise; toggle
persists; manual run; the 4 decided rules (esp pattern-check on progress+users NOT
health=dead — abandon-orthogonal). NO AI (pure rules).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.automation import service as auto
from modules.projects import service as proj
from modules.projects.schema import ProjectAbandonInput


def _init_repo(path: Path, *, days_ago: int = 0) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    env = None
    if days_ago:
        from datetime import datetime, timedelta, timezone
        d = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        import os
        env = {**os.environ, "GIT_AUTHOR_DATE": d, "GIT_COMMITTER_DATE": d}
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True, env=env)


def _seed_project(monkeypatch, repos: dict, pid: str, repo: Path, **status_fields):
    import yaml
    from store import md_store
    monkeypatch.setattr(proj.settings, "project_repos", repos)
    fm = {"name": pid, "repo": str(repo), **status_fields}
    md_store.write_file(f"projects/{pid}/status.md",
                        "---\n" + yaml.safe_dump(fm, sort_keys=True).strip() + "\n---\n", "seed")


# --------------------------------------------------------------------------- #
# run-record wrapper                                                            #
# --------------------------------------------------------------------------- #
def test_wrapper_records_ok_run(isolated_paths):
    run = auto.record_routine_run("test-r", lambda: ("ok", "did a thing"))
    assert run["status"] == "ok" and run["detail"] == "did a thing"
    from store import db
    rows = db.recent_runs("test-r")
    assert len(rows) == 1 and rows[0]["status"] == "ok" and rows[0]["detail"] == "did a thing"


def test_wrapper_records_warn_run(isolated_paths):
    auto.record_routine_run("test-r", lambda: ("warn", "flagged 2"))
    from store import db
    assert db.recent_runs("test-r")[0]["status"] == "warn"


def test_wrapper_fail_soft_on_raise(isolated_paths):
    """A routine that RAISES → error run recorded, exception SWALLOWED (fail-soft)."""
    def boom():
        raise RuntimeError("kaboom")
    # must NOT raise
    run = auto.record_routine_run("test-r", boom)
    assert run["status"] == "error" and "kaboom" in run["detail"]
    from store import db
    assert db.recent_runs("test-r")[0]["status"] == "error"


def test_wrapper_none_result_is_ok(isolated_paths):
    run = auto.record_routine_run("test-r", lambda: None)
    assert run["status"] == "ok"


# --------------------------------------------------------------------------- #
# idle-hunter — projects idle >7d (not abandoned)                               #
# --------------------------------------------------------------------------- #
def test_idle_hunter_flags_over_7_days(monkeypatch, tmp_path, isolated_paths):
    fresh = tmp_path / "fresh"; _init_repo(fresh, days_ago=0)      # lastDays 0 → not idle
    stale = tmp_path / "stale"; _init_repo(stale, days_ago=20)     # lastDays 20 → idle
    _seed_project(monkeypatch, {"fresh": str(fresh), "stale": str(stale)}, "fresh", fresh)
    _seed_project(monkeypatch, {"fresh": str(fresh), "stale": str(stale)}, "stale", stale)
    status, detail = auto.idle_hunter()
    assert status == "warn"
    assert "stale" in detail and "fresh" not in detail  # only the >7d one


def test_idle_hunter_excludes_abandoned(monkeypatch, tmp_path, isolated_paths):
    stale = tmp_path / "stale"; _init_repo(stale, days_ago=20)
    _seed_project(monkeypatch, {"stale": str(stale)}, "stale", stale)
    proj.abandon_project("stale", ProjectAbandonInput(reason="x"))  # abandoned → excluded
    status, detail = auto.idle_hunter()
    assert status == "ok"  # list_projects excludes abandoned → nothing idle


def test_idle_hunter_no_projects_ok(monkeypatch, isolated_paths):
    monkeypatch.setattr(proj.settings, "project_repos", {})
    assert auto.idle_hunter()[0] == "ok"


# --------------------------------------------------------------------------- #
# pattern-check — build-to-90 (progress>=90 & users==0), NOT health=dead         #
# --------------------------------------------------------------------------- #
def test_pattern_check_flags_90pct_0user(monkeypatch, tmp_path, isolated_paths):
    repo = tmp_path / "p"; _init_repo(repo, days_ago=0)  # health=act (fresh!)
    _seed_project(monkeypatch, {"p": str(repo)}, "p", repo, progress=95, users=0)
    status, detail = auto.pattern_check()
    assert status == "warn" and "95%" in detail and "0 user" in detail


def test_pattern_check_orthogonal_to_health(monkeypatch, tmp_path, isolated_paths):
    """CRITICAL: a FRESH (health=act) project at 90%/0-user IS flagged — pattern-check
    is progress+users, NOT commit-age health. RED if it filtered by health=dead."""
    repo = tmp_path / "p"; _init_repo(repo, days_ago=0)  # health=act
    _seed_project(monkeypatch, {"p": str(repo)}, "p", repo, progress=92, users=0)
    st = proj.get_project("p")
    assert st.health == "act"  # fresh — NOT dead
    assert auto.pattern_check()[0] == "warn"  # still flagged (orthogonal)


def test_pattern_check_not_flagged_with_users(monkeypatch, tmp_path, isolated_paths):
    repo = tmp_path / "p"; _init_repo(repo, days_ago=0)
    _seed_project(monkeypatch, {"p": str(repo)}, "p", repo, progress=95, users=5)  # has users
    assert auto.pattern_check()[0] == "ok"


def test_pattern_check_not_flagged_under_90(monkeypatch, tmp_path, isolated_paths):
    repo = tmp_path / "p"; _init_repo(repo, days_ago=0)
    _seed_project(monkeypatch, {"p": str(repo)}, "p", repo, progress=80, users=0)
    assert auto.pattern_check()[0] == "ok"


# --------------------------------------------------------------------------- #
# journal-nudge — event (latest market alert) + morning-pull                    #
# --------------------------------------------------------------------------- #
def test_journal_nudge_on_market_alert(isolated_paths):
    import json
    from store import db
    db.record_run("market-poll", "warn", auto._now_iso(),
                  detail=json.dumps({"kind": "alert", "symbol": "BTC", "op": "above", "threshold": 1, "price": 2}))
    status, detail = auto.journal_nudge()
    assert status == "warn" and "BTC" in detail


def test_journal_nudge_no_alert_ok(isolated_paths):
    assert auto.journal_nudge()[0] == "ok"


def test_journal_nudge_event_arg(isolated_paths):
    """Event-driven: market-poll passes the fired alert dict directly (simulable)."""
    status, detail = auto.journal_nudge({"symbol": "ETH", "op": "below", "threshold": 1500})
    assert status == "warn" and "ETH" in detail


def test_morning_pull_records_summary(monkeypatch, tmp_path, isolated_paths):
    monkeypatch.setattr(proj.settings, "project_repos", {})
    monkeypatch.setattr("modules.market.service.settings.market_assets", [])
    status, detail = auto.morning_pull()
    assert "projects" in detail and "Morning pull" in detail


# --------------------------------------------------------------------------- #
# D2 — morning_pull captures a finance snapshot (fail-soft add-on) so the equity #
# curve fills day-by-day. 3 distinguishing cases.                                #
# --------------------------------------------------------------------------- #
def test_d2_morning_pull_captures_snapshot(monkeypatch, isolated_paths):
    """Capture works: after morning_pull(), value_history() gained today's row."""
    from modules.finance import service as fin
    monkeypatch.setattr(proj.settings, "project_repos", {})
    monkeypatch.setattr("modules.market.service.settings.market_assets", [])
    assert fin.value_history() == []          # baseline: no snapshots
    auto.morning_pull()
    hist = fin.value_history()
    assert len(hist) == 1                      # today's row landed


def test_d2_snapshot_idempotent_run_twice_one_today_row(monkeypatch, isolated_paths):
    """Idempotent upsert: morning_pull() TWICE same UTC day → still exactly ONE today-row
    (take_snapshot upserts per day — no dup)."""
    import datetime as _dt
    from modules.finance import service as fin
    monkeypatch.setattr(proj.settings, "project_repos", {})
    monkeypatch.setattr("modules.market.service.settings.market_assets", [])
    auto.morning_pull()
    auto.morning_pull()                        # second run, same UTC day
    today = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    today_rows = [h for h in fin.value_history() if h["day"] == today]
    assert len(today_rows) == 1                # upsert, not append


def test_d2_snapshot_failure_is_fail_soft_pull_completes(monkeypatch, isolated_paths):
    """THE discipline: a snapshot RAISE must NOT ABORT the pull. Mock take_snapshot to
    raise → morning_pull still COMPLETES + returns, the finance READ part + other parts
    are intact, the failure is NOTED. The add-on warn folds into the status tier EXACTLY
    like the existing brief add-on (status=warn, NOT error, NOT a propagated raise) —
    the pull WORK is not lost. (Matches the brief-add-on precedent at service.py:212.)"""
    from modules.finance import service as fin
    monkeypatch.setattr(proj.settings, "project_repos", {})
    monkeypatch.setattr("modules.market.service.settings.market_assets", [])

    def _boom():
        raise RuntimeError("snapshot store down")
    monkeypatch.setattr(fin, "take_snapshot", _boom)

    status, detail = auto.morning_pull()
    # pull COMPLETED (the raise did NOT propagate/abort) — that's the fail-soft contract
    assert detail.startswith("Morning pull:")
    assert "snapshot ERR" in detail             # the failure is visible
    assert "finance $" in detail                # the finance READ part is intact (pull worked)
    # add-on warn folds into the tier like the brief add-on; never 'error', never a raise
    assert status == "warn"


# --------------------------------------------------------------------------- #
# toggle persistence + list + run                                               #
# --------------------------------------------------------------------------- #
def test_set_enabled_persists(isolated_paths):
    info = auto.set_enabled("idle-hunter", False)
    assert info is not None and info.enabled is False
    # persisted: a fresh list reflects it
    view = auto.list_routines()
    idle = next(r for r in view.routines if r.id == "idle-hunter")
    assert idle.enabled is False


def test_set_enabled_unknown_returns_none(isolated_paths):
    assert auto.set_enabled("ghost", True) is None


def test_list_routines_shape_and_stats(isolated_paths):
    # run one routine so it has a run_log row
    auto.record_routine_run("idle-hunter", lambda: ("ok", "none idle"))
    view = auto.list_routines()
    assert view.total == 8  # +held-history (#62 FINANCE-AUDIT-S3); was 7 (#52 macro-snapshot)
    ids = {r.id for r in view.routines}
    assert ids == {"market-poll", "wiki-refresh", "idle-hunter", "pattern-check",
                   "journal-nudge", "morning-pull", "macro-snapshot", "held-history"}
    idle = next(r for r in view.routines if r.id == "idle-hunter")
    assert idle.runs >= 1 and idle.lastResult == "ok" and idle.lastRun is not None
    assert view.runsToday >= 1 and view.lastRunAt is not None


def test_run_routine_records_and_returns(monkeypatch, isolated_paths):
    monkeypatch.setattr(proj.settings, "project_repos", {})
    run = auto.run_routine("idle-hunter")
    assert run is not None and run.id == "idle-hunter" and run.status == "ok"
    from store import db
    assert len(db.recent_runs("idle-hunter")) == 1


def test_run_routine_unknown_returns_none(isolated_paths):
    assert auto.run_routine("ghost") is None


def test_run_routine_fail_soft_records_error(isolated_paths, monkeypatch):
    """A routine whose deps blow up → error run recorded, run_routine still returns
    (200-equivalent), does NOT raise."""
    def boom():
        raise RuntimeError("dep down")
    monkeypatch.setitem(auto._CATALOG_BY_ID["idle-hunter"], "func", boom)
    run = auto.run_routine("idle-hunter")
    assert run is not None and run.status == "error" and "dep down" in run.detail


def test_empty_run_log_routines_show_none(isolated_paths):
    view = auto.list_routines()
    for r in view.routines:
        assert r.lastRun is None and r.lastResult is None and r.runs == 0
    assert view.runsToday == 0 and view.lastRunAt is None
