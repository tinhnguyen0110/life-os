"""tests/test_graveyard.py — graveyard service + abandon-lesson + restore (Sprint 8).

Behavior-tested: abandon w/ lesson → read back in /graveyard; restore → project
leaves graveyard + rejoins list_projects (NOT field-read); stats math hand-calc on
a known fixture; empty graveyard; null-lesson grave; fail-open.
Membership = the `abandoned` flag, NOT health=dead (orthogonal).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.graveyard import service as gy
from modules.projects import service as proj
from modules.projects.schema import ProjectAbandonInput, ProjectRegisterInput


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=path, check=True)
    (path / "a.py").write_text("x=1\n")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "DemoProj"
    _init_repo(r)
    return r


def _register(monkeypatch, repo, **status_fields):
    """Register a project + seed status.md fields (users/progress) via md_store."""
    from store import md_store
    import yaml
    monkeypatch.setattr(proj.settings, "project_repos", {"demo": str(repo)})
    fm = {"name": "Demo", "repo": str(repo), **status_fields}
    md_store.write_file("projects/demo/status.md",
                        "---\n" + yaml.safe_dump(fm, sort_keys=True).strip() + "\n---\n", "seed")


# --------------------------------------------------------------------------- #
# abandon + lesson round-trip                                                   #
# --------------------------------------------------------------------------- #
def test_abandon_with_lesson_round_trip(monkeypatch, repo, isolated_paths):
    _register(monkeypatch, repo, users=5, progress=80)
    proj.abandon_project("demo", ProjectAbandonInput(reason="lost interest", atProgress=80, lesson="ship smaller"))
    gv = gy.get_graveyard()
    assert gv.count == 1
    g = gv.graves[0]
    assert g.id == "demo" and g.reason == "lost interest" and g.lesson == "ship smaller"
    assert g.peak == 80 and g.users == 5
    assert "ship smaller" in gv.lessons


def test_abandon_without_lesson_is_null(monkeypatch, repo, isolated_paths):
    _register(monkeypatch, repo, users=0, progress=33)
    proj.abandon_project("demo", ProjectAbandonInput(reason="pivot", atProgress=33))  # no lesson
    gv = gy.get_graveyard()
    assert gv.graves[0].lesson is None  # never fabricated
    assert gv.lessons == []  # no lesson → not in lessons panel


# --------------------------------------------------------------------------- #
# restore — behavior (leaves graveyard, rejoins list_projects)                  #
# --------------------------------------------------------------------------- #
def test_restore_removes_from_graveyard_and_rejoins_list(monkeypatch, repo, isolated_paths):
    _register(monkeypatch, repo, users=2, progress=50)
    proj.abandon_project("demo", ProjectAbandonInput(reason="x", lesson="learned"))
    assert gy.get_graveyard().count == 1
    # not in list_projects while abandoned
    assert all(s.id != "demo" for s in proj.list_projects()[0])

    restored = proj.restore_project("demo")
    assert restored is not None and restored.id == "demo"
    # leaves graveyard
    assert gy.get_graveyard().count == 0
    # rejoins list_projects
    assert any(s.id == "demo" for s in proj.list_projects()[0])
    # status.md abandon* flags cleared...
    meta = proj._load_meta("demo")
    for k in ("abandoned", "abandonedReason", "abandonedAt", "abandonedProgress", "abandonedUsers"):
        assert k not in meta
    # ...but the LESSON is PRESERVED (hard-won history, architect ruling)
    assert meta.get("lesson") == "learned"


def test_restore_non_abandoned_is_noop_200(monkeypatch, repo, isolated_paths):
    _register(monkeypatch, repo)
    # not abandoned → restore is a no-op, returns the project (not None → router 200)
    r = proj.restore_project("demo")
    assert r is not None and r.id == "demo"


def test_restore_unknown_returns_none(monkeypatch, repo, isolated_paths):
    monkeypatch.setattr(proj.settings, "project_repos", {"demo": str(repo)})
    assert proj.restore_project("ghost") is None  # router → 404


# --------------------------------------------------------------------------- #
# stats math (hand-calc on a multi-grave fixture)                               #
# --------------------------------------------------------------------------- #
def _seed_abandoned(md_store, yaml, pid, repo, *, reason, peak, users, lesson=None):
    fm = {"name": pid, "repo": str(repo), "abandoned": True, "abandonedReason": reason,
          "abandonedAt": "2026-01-15T00:00:00+00:00", "abandonedProgress": peak, "users": users}
    if lesson:
        fm["lesson"] = lesson
    md_store.write_file(f"projects/{pid}/status.md",
                        "---\n" + yaml.safe_dump(fm, sort_keys=True).strip() + "\n---\n", "seed")


def test_stats_handcalc(monkeypatch, repo, isolated_paths):
    from store import md_store
    import yaml
    monkeypatch.setattr(proj.settings, "project_repos", {
        "a": str(repo), "b": str(repo), "c": str(repo), "d": str(repo)})
    _seed_abandoned(md_store, yaml, "a", repo, reason="pivot", peak=90, users=10, lesson="too late")
    _seed_abandoned(md_store, yaml, "b", repo, reason="pivot", peak=50, users=0, lesson="too late")  # dup lesson
    _seed_abandoned(md_store, yaml, "c", repo, reason="boredom", peak=30, users=0)
    _seed_abandoned(md_store, yaml, "d", repo, reason="pivot", peak=10, users=3, lesson="ship smaller")
    gv = gy.get_graveyard()
    assert gv.count == 4
    # avgPeak = (90+50+30+10)/4 = 45.0
    assert gv.avgPeak == 45.0
    # commonReasons: pivot×3, boredom×1, sorted desc
    assert gv.commonReasons[0].reason == "pivot" and gv.commonReasons[0].count == 3
    assert gv.commonReasons[1].reason == "boredom" and gv.commonReasons[1].count == 1
    # reachedUser (users>0): a(10), d(3) = 2 ; beforeUser (users==0): b, c = 2
    assert gv.reachedUser == 2 and gv.beforeUser == 2
    # lessons: distinct non-empty first-seen → "too late" (a), "ship smaller" (d). b's dup skipped.
    assert gv.lessons == ["too late", "ship smaller"]


# --------------------------------------------------------------------------- #
# architect deltas: abandonedUsers snapshot, reason normalize, avgPeak skip      #
# --------------------------------------------------------------------------- #
def test_abandoned_users_snapshot_immune_to_later_edit(monkeypatch, repo, isolated_paths):
    """users is SNAPSHOT at abandon — later status.md edits don't change the stat."""
    import yaml
    from store import md_store
    _register(monkeypatch, repo, users=7, progress=40)
    proj.abandon_project("demo", ProjectAbandonInput(reason="x"))
    # later, the live `users` is edited DOWN to 0 in status.md
    meta = proj._load_meta("demo")
    assert meta["abandonedUsers"] == 7  # snapshotted
    meta["users"] = 0
    md_store.write_file("projects/demo/status.md",
                        "---\n" + yaml.safe_dump(meta, sort_keys=True).strip() + "\n---\n", "edit")
    # graveyard still reports the snapshot (7 → reachedUser), not the edited 0
    gv = gy.get_graveyard()
    assert gv.graves[0].users == 7 and gv.reachedUser == 1 and gv.beforeUser == 0


def test_common_reasons_normalized_case(monkeypatch, repo, isolated_paths):
    """commonReasons groups case-insensitively, displays first-occurrence original case."""
    import yaml
    from store import md_store
    monkeypatch.setattr(proj.settings, "project_repos", {"a": str(repo), "b": str(repo)})
    _seed_abandoned(md_store, yaml, "a", repo, reason="Pivot", peak=50, users=0)
    _seed_abandoned(md_store, yaml, "b", repo, reason="pivot", peak=60, users=0)  # diff case
    gv = gy.get_graveyard()
    assert len(gv.commonReasons) == 1  # grouped despite case
    assert gv.commonReasons[0].count == 2
    assert gv.commonReasons[0].reason == "Pivot"  # first-occurrence original case


def test_avg_peak_skips_missing_progress(monkeypatch, repo, isolated_paths):
    """avgPeak averages only graves WITH abandonedProgress (missing skipped, not 0)."""
    import yaml
    from store import md_store
    monkeypatch.setattr(proj.settings, "project_repos", {"a": str(repo), "b": str(repo)})
    _seed_abandoned(md_store, yaml, "a", repo, reason="x", peak=80, users=0)  # has 80
    # 'b' abandoned with NO abandonedProgress → excluded from avgPeak (not counted as 0)
    md_store.write_file("projects/b/status.md",
        "---\nabandoned: true\nabandonedReason: y\nabandonedAt: '2026-01-01T00:00:00+00:00'\n"
        "name: B\nrepo: " + str(repo) + "\n---\n", "seed")
    gv = gy.get_graveyard()
    assert gv.count == 2
    assert gv.avgPeak == 80.0  # only 'a' counts; NOT (80+0)/2 = 40


# --------------------------------------------------------------------------- #
# empty + defensive                                                             #
# --------------------------------------------------------------------------- #
def test_empty_graveyard(monkeypatch, repo, isolated_paths):
    _register(monkeypatch, repo)  # registered but NOT abandoned
    gv = gy.get_graveyard()
    assert gv.count == 0 and gv.graves == [] and gv.avgPeak == 0.0
    assert gv.commonReasons == [] and gv.reachedUser == 0 and gv.beforeUser == 0 and gv.lessons == []


def test_peak_falls_back_to_progress_then_zero(monkeypatch, repo, isolated_paths):
    from store import md_store
    import yaml
    monkeypatch.setattr(proj.settings, "project_repos", {"a": str(repo), "b": str(repo)})
    # 'a' abandoned with NO abandonedProgress but has progress=42 → peak=42
    md_store.write_file("projects/a/status.md",
        "---\nabandoned: true\nabandonedReason: x\nabandonedAt: '2026-01-01T00:00:00+00:00'\n"
        "name: A\nprogress: 42\nrepo: " + str(repo) + "\n---\n", "seed")
    # 'b' abandoned with neither → peak=0
    md_store.write_file("projects/b/status.md",
        "---\nabandoned: true\nabandonedReason: y\nabandonedAt: '2026-01-01T00:00:00+00:00'\n"
        "name: B\nrepo: " + str(repo) + "\n---\n", "seed")
    peaks = {g.id: g.peak for g in gy.get_graveyard().graves}
    assert peaks["a"] == 42 and peaks["b"] == 0


def test_abandoned_orthogonal_to_health(monkeypatch, repo, isolated_paths):
    """A freshly-committed (health=act) project that's abandoned IS in the graveyard."""
    _register(monkeypatch, repo, users=1)
    proj.abandon_project("demo", ProjectAbandonInput(reason="pivot"))
    gv = gy.get_graveyard()
    assert gv.count == 1
    # health is act (just committed) but it's STILL a grave — membership = abandoned flag
    assert gv.graves[0].health == "act"
