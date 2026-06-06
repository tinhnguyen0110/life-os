"""tests/test_brief.py — brief generator + 5 priority rules unit tests (S11).

BEHAVIOR-TESTED: each rule fires on a matching fixture + stays silent when not; the
build-to-90 abandon-orthogonal DISTINGUISHING case (a health=act 90%/0-user project IS
a priority; an abandoned one is NOT — orthogonal to health, NOT health=dead); fail-soft
per source; no-conditions→honest-empty; severity-sort + display rank `n`. Template, NO AI.

Rules are pure fns over the reader.Sources data → unit-test them DIRECTLY (no live
modules needed for most), + a few generate_brief() integration cases with monkeypatched
reader.pull.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from modules.brief import reader, service
from modules.projects.schema import ProjectStatus


# --------------------------------------------------------------------------- #
# Helpers — minimal fixtures for each source                                    #
# --------------------------------------------------------------------------- #
def _project(pid, *, progress=0, users=0, last_days=0, health="act"):
    # ProjectStatus has NO `abandoned` field — list_projects() filters abandoned out
    # UPSTREAM, so the brief rule never sees one. The rule keys on progress+users, which
    # is exactly what the abandon-orthogonal DISTINGUISHING test proves.
    return ProjectStatus(
        id=pid, name=pid, desc=None, health=health, progress=progress, users=users,
        last=None, lastDays=last_days, next=None, repo="/tmp/x", routines=[], lastAuto=None,
    )


class _Alloc:
    def __init__(self, channel, drift, driftAlert, target=25.0):
        self.channel = channel; self.drift = drift; self.driftAlert = driftAlert; self.target = target


class _Finance:
    def __init__(self, total=1000.0, allocs=None):
        self.totalValue = total; self.allocations = allocs or []


class _Claude:
    def __init__(self, pct, stale=False, asOf="2026-06-06"):
        self.pct = pct; self.stale = stale; self.asOf = asOf


# =========================================================================== #
# Rule 1 — market / ladder                                                      #
# =========================================================================== #
def test_market_rule_hit_is_urgent():
    market = {"triggers": [{"symbol": "BTC", "op": "above", "threshold": 100000,
                            "price": 101000, "state": "hit", "distancePct": -1.0}]}
    p = service._market_priority(market)
    assert p is not None and p.severity == "urgent" and p.source == "market" and "BTC" in p.text


def test_market_rule_near_within_2pct_is_info():
    market = {"triggers": [{"symbol": "ETH", "op": "above", "threshold": 4000,
                            "price": 3925, "state": "near", "distancePct": 1.9}]}
    p = service._market_priority(market)
    assert p is not None and p.severity == "info"


def test_market_rule_near_beyond_2pct_silent():
    market = {"triggers": [{"symbol": "ETH", "op": "above", "threshold": 4000,
                            "price": 3800, "state": "near", "distancePct": 4.5}]}
    assert service._market_priority(market) is None


def test_market_rule_none_source_silent():
    assert service._market_priority(None) is None
    assert service._market_priority({"triggers": []}) is None


# =========================================================================== #
# Rule 2 — project build-to-90 / idle (abandon-orthogonal DISTINGUISHING)       #
# =========================================================================== #
def test_project_build90_is_urgent():
    p = service._project_priority([_project("p", progress=92, users=0, health="act")])
    assert p is not None and p.severity == "urgent" and p.source == "projects" and "build-to-90" in p.text


def test_project_idle_is_warn():
    p = service._project_priority([_project("p", progress=40, users=0, last_days=20, health="slow")])
    assert p is not None and p.severity == "warn" and "đứng 20" in p.text


def test_project_build90_DISTINGUISHING_orthogonal_to_health():
    """CRITICAL: build-to-90 keys on progress≥90 & users==0, NOT health. A FRESH
    health=act 90%/0-user project IS flagged (it's the headline pattern). list_projects
    already excludes abandoned, so the rule never sees an abandoned one. TEETH: a
    health=dead project that is NOT 90%/0-user must NOT be a build-to-90 priority — the
    rule is progress+users, not commit-age health."""
    # health=act, 92%, 0 user → IS a build-to-90 priority (orthogonal to health)
    fresh = service._project_priority([_project("fresh", progress=92, users=0, health="act")])
    assert fresh is not None and fresh.severity == "urgent"

    # health=dead but only 50%/5-user → NOT a build-to-90 priority (and not idle either)
    dead = service._project_priority([_project("dead", progress=50, users=5, last_days=0, health="dead")])
    assert dead is None, "health=dead alone must NOT make a build-to-90 priority — it's progress+users"


def test_project_build90_takes_precedence_over_idle():
    """A project that is BOTH build-to-90 and idle → urgent build-to-90 wins."""
    p = service._project_priority([_project("p", progress=95, users=0, last_days=30, health="stall")])
    assert p.severity == "urgent" and "build-to-90" in p.text


def test_project_with_users_not_flagged():
    assert service._project_priority([_project("p", progress=95, users=10, last_days=0)]) is None


def test_project_none_source_silent():
    assert service._project_priority(None) is None
    assert service._project_priority([]) is None


# =========================================================================== #
# Rule 3 — claude quota bands                                                   #
# =========================================================================== #
def test_claude_90pct_is_urgent():
    p = service._claude_priority(_Claude(pct=92.0))
    assert p is not None and p.severity == "urgent" and p.source == "claude"


def test_claude_75pct_is_warn():
    p = service._claude_priority(_Claude(pct=80.0))
    assert p is not None and p.severity == "warn"


def test_claude_under_75_silent():
    assert service._claude_priority(_Claude(pct=50.0)) is None


def test_claude_stale_caps_at_warn():
    """≥90% but STALE cache → capped at warn (don't cry urgent on old data) + asOf note."""
    p = service._claude_priority(_Claude(pct=95.0, stale=True, asOf="2026-05-01"))
    assert p is not None and p.severity == "warn" and "2026-05-01" in p.text


def test_claude_none_silent():
    assert service._claude_priority(None) is None


# =========================================================================== #
# Rule 4 — finance drift                                                        #
# =========================================================================== #
def test_finance_drift_is_warn():
    fin = _Finance(allocs=[_Alloc("crypto", drift=8.0, driftAlert=True, target=30.0)])
    p = service._finance_priority(fin)
    assert p is not None and p.severity == "warn" and p.source == "finance" and "crypto" in p.text


def test_finance_no_drift_silent():
    fin = _Finance(allocs=[_Alloc("crypto", drift=2.0, driftAlert=False)])
    assert service._finance_priority(fin) is None


def test_finance_picks_largest_drift():
    fin = _Finance(allocs=[_Alloc("crypto", drift=6.0, driftAlert=True),
                           _Alloc("etf", drift=-12.0, driftAlert=True)])
    p = service._finance_priority(fin)
    assert "etf" in p.text  # largest |drift|


def test_finance_none_silent():
    assert service._finance_priority(None) is None


# =========================================================================== #
# Rule 5 — alerts (non-ladder, today; no dup with rule 1)                       #
# =========================================================================== #
def test_alerts_today_is_warn():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT10:00:00+00:00")
    market = {"triggers": [], "alertHistory": [{"symbol": "SOL", "op": "below",
              "threshold": 100, "price": 95, "ts": today}]}
    p = service._alerts_priority(market)
    assert p is not None and p.severity == "warn" and p.source == "alerts" and "SOL" in p.text


def test_alerts_skips_live_hit_symbol_no_dup():
    """An alert whose symbol IS the live rule-1 hit → rule 5 skips it (no dup)."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT10:00:00+00:00")
    market = {"triggers": [{"symbol": "BTC", "state": "hit"}],
              "alertHistory": [{"symbol": "BTC", "op": "above", "threshold": 100000,
                                "price": 101000, "ts": today}]}
    assert service._alerts_priority(market) is None  # BTC is the live hit → rule 1 owns it


def test_alerts_old_alert_silent():
    market = {"triggers": [], "alertHistory": [{"symbol": "SOL", "price": 95,
              "ts": "2026-01-01T10:00:00+00:00"}]}
    assert service._alerts_priority(market) is None  # not today


# =========================================================================== #
# generate_brief — severity sort, honest-empty, fail-soft, summary              #
# =========================================================================== #
def _sources(*, projects=None, finance=None, market=None, claude=None, warnings=None):
    s = reader.Sources()
    s.projects = projects; s.finance = finance; s.market = market; s.claude = claude
    s.warnings = warnings or []
    return s


def test_generate_severity_sort_and_rank(monkeypatch):
    """urgent>warn>info; n assigned after sort (1=top). Build a source set that fires
    market(info-near) + project(urgent) + claude(warn) → display order urgent,warn,info."""
    from datetime import datetime, timezone
    market = {"triggers": [{"symbol": "ETH", "op": "above", "threshold": 4000,
                            "price": 3930, "state": "near", "distancePct": 1.7}],
              "alertHistory": []}
    src = _sources(
        projects=[_project("p", progress=95, users=0, health="act")],   # urgent
        claude=_Claude(pct=80.0),                                        # warn
        market=market,                                                   # info
        finance=_Finance(allocs=[]),
    )
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    sevs = [p.severity for p in brief.priorities]
    assert sevs == ["urgent", "warn", "info"]            # severity DESC
    assert [p.n for p in brief.priorities] == [1, 2, 3]  # rank after sort
    assert brief.source == "template"


def test_generate_honest_empty(monkeypatch):
    """No rule fires → priorities=[] BUT full brief with real summary (NOT fabricated)."""
    src = _sources(
        projects=[_project("p", progress=40, users=3, last_days=1, health="act")],
        finance=_Finance(total=5000.0, allocs=[]),
        claude=_Claude(pct=20.0),
        market={"triggers": [], "alertHistory": []},
    )
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert brief.priorities == []                  # honest-empty
    assert brief.summary.netWorth == 5000.0        # but real summary
    assert brief.summary.projectsActive == 1
    assert brief.summary.claudePct == 20.0


def test_generate_fail_soft_per_source(monkeypatch):
    """A source down (None) → its rules skipped, brief still produced from the rest."""
    src = _sources(
        projects=[_project("p", progress=95, users=0, health="act")],  # urgent fires
        finance=None,    # down
        market=None,     # down
        claude=None,     # down
        warnings=["finance nguồn lỗi"],
    )
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert len(brief.priorities) == 1 and brief.priorities[0].source == "projects"
    assert brief.summary.netWorth is None and brief.summary.claudePct is None
    assert "finance nguồn lỗi" in brief.warnings


def test_generate_all_sources_down(monkeypatch):
    src = _sources(warnings=[])
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert brief.priorities == []
    assert any("không đủ dữ liệu" in w for w in brief.warnings)
    assert brief.summary.netWorth is None and brief.summary.projectsActive == 0


def test_generate_stale_from_claude(monkeypatch):
    src = _sources(claude=_Claude(pct=10.0, stale=True, asOf="2026-05-01"),
                   finance=_Finance(), market={"triggers": [], "alertHistory": []},
                   projects=[])
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert brief.stale is True
    assert brief.asOf == "2026-05-01"  # oldest source freshness


def test_generate_priority_cap(monkeypatch):
    """Cap at 5 priorities even if more rules could fire (they can't exceed 5 here, but
    the cap is enforced)."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT10:00:00+00:00")
    src = _sources(
        projects=[_project("p", progress=95, users=0, health="act")],
        finance=_Finance(allocs=[_Alloc("crypto", drift=9.0, driftAlert=True)]),
        claude=_Claude(pct=92.0),
        market={"triggers": [{"symbol": "BTC", "state": "hit", "op": "above",
                              "threshold": 100000, "price": 101000, "distancePct": -1.0}],
                "alertHistory": [{"symbol": "SOL", "price": 95, "ts": today}]},
    )
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert len(brief.priorities) <= service.PRIORITY_CAP


# =========================================================================== #
# History + persistence (S11-T2)                                                #
# =========================================================================== #
def test_history_empty_returns_list(isolated_paths):
    assert service.get_history() == []


def test_persist_then_history_roundtrip(isolated_paths, monkeypatch):
    """save_brief() writes brief/<date>.md → get_history() reads it back, same shape."""
    src = _sources(projects=[_project("p", progress=95, users=0, health="act")],
                   finance=_Finance(total=1234.0), market={"triggers": [], "alertHistory": []},
                   claude=_Claude(pct=10.0))
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    rel = service.save_brief(brief)
    assert rel.startswith("brief/") and rel.endswith(".md")

    history = service.get_history()
    assert len(history) == 1
    h = history[0]
    assert h.source == "template"
    assert h.summary.netWorth == 1234.0
    assert len(h.priorities) == len(brief.priorities)
    assert h.priorities[0].source == "projects" and h.priorities[0].severity == "urgent"


def test_persist_same_day_overwrites(isolated_paths, monkeypatch):
    """Re-persisting the same day OVERWRITES (a brief is a daily snapshot, latest wins)."""
    src = _sources(finance=_Finance(total=100.0), projects=[], market=None, claude=None)
    monkeypatch.setattr(reader, "pull", lambda: src)
    service.save_brief(service.generate_brief())
    # second assembly, same day, different net worth
    src.finance = _Finance(total=999.0)
    service.save_brief(service.generate_brief())
    history = service.get_history()
    assert len(history) == 1  # one file for the day (overwritten, not duplicated)
    assert history[0].summary.netWorth == 999.0


def test_persist_generates_if_not_given(isolated_paths, monkeypatch):
    """save_brief() with no arg generates the brief itself."""
    monkeypatch.setattr(reader, "pull", lambda: _sources(finance=_Finance(total=5.0)))
    rel = service.save_brief()
    assert rel.endswith(".md")
    assert service.get_history()[0].summary.netWorth == 5.0


def test_morning_pull_persists_brief(isolated_paths, monkeypatch):
    """morning-pull assembles + persists the brief (S11-T2 wiring) — fail-soft."""
    from modules.automation import service as auto
    from modules.projects import service as proj
    monkeypatch.setattr(proj.settings, "project_repos", {})
    status, detail = auto.morning_pull()
    assert "brief" in detail  # the brief step ran + is in the summary
    # the brief file was persisted → history has it
    assert len(service.get_history()) == 1
