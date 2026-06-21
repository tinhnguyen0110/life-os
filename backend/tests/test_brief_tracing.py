"""tests/test_brief_tracing.py — DAILY-TRACING-P4 (#65): the tracing → brief wire (streak-at-risk).

The LAST link of the tracing arc: life_brief / daily_brief surface a streak about to break. Mirrors
the reminders brief-wire (#30) EXACTLY — a Sources.tracing field (fail-soft pull) + a
``_tracing_priority`` warn rule (daily_brief) + a ``_brief_tracing`` section (life_brief).

These tests EXERCISE the rule (behavior-test-not-field-read) on built ActivityViews — each a
DIVERGENT distinguishing case (a correct rule ≠ a plausible-wrong one):
  - streak≥3 + today NOT done → FIRES (warn, count + longest)
  - streak≥3 + today DONE     → no priority (safe today — the done-guard)
  - streak<3 + today not done → no priority (below the at-risk MIN — a 1-2 streak isn't hard-won)
  - no activities / source fail → None (honest, no crash; the brief still assembles)
  - the rule + section reach BOTH consumers (daily_brief priority + life_brief section)
  - PRIORITY_CAP=7 → all 7 rules can fire, none silently dropped
"""

from __future__ import annotations

import pytest

from modules.brief import service as brief_svc
from modules.brief.service import _tracing_priority
from modules.tracing.schema import ActivityView, TodayStat, TracingOverview, TracingScore


def _view(activity_id: str, *, streak: int, done: bool, goal: float = 5.0) -> ActivityView:
    """Build an ActivityView with the only fields the rule reads (streak + today.done)."""
    return ActivityView(
        id=activity_id, name=activity_id.title(), goal=goal,
        today=TodayStat(done=done, val=goal if done else 0.0, pct=100 if done else 0, sessions=1),
        streak=streak, week=[0.0] * 7, history12w=[0.0] * 84,
    )


def _overview(*views: ActivityView) -> TracingOverview:
    """Wrap views in a TracingOverview (heatmap/score not read by the rule — minimal honest stub)."""
    done = sum(1 for v in views if v.today.done)
    total = len(views)
    return TracingOverview(
        date="2026-06-21", activities=list(views), heatmap12w=[0] * 84,
        score=TracingScore(total=total, done=done,
                           pct=round(done / total * 100) if total else 0,
                           topStreak=max((v.streak for v in views), default=0)),
    )


# --- the distinguishing set (EXERCISE the rule) ----------------------------- #
def test_streak_at_risk_fires_warn():
    """streak=5 + today NOT done → FIRES: warn, source=tracing, text names count + longest."""
    ov = _overview(_view("run", streak=5, done=False))
    p = _tracing_priority(ov)
    assert p is not None
    assert p.severity == "warn" and p.source == "tracing"
    assert "sắp đứt" in p.text and "5" in p.text  # longest streak surfaced


def test_streak_done_today_no_priority():
    """streak=5 but today ALREADY done → NO priority (safe today — the done-guard is the key
    distinguisher: a rule that ignored today.done would wrongly fire here)."""
    ov = _overview(_view("run", streak=5, done=True))
    assert _tracing_priority(ov) is None


def test_streak_below_min_no_priority():
    """streak=2 + today not done → NO priority (below STREAK_AT_RISK_MIN=3 — a 1-2 streak isn't
    hard-won; a rule with the wrong threshold would fire here)."""
    ov = _overview(_view("run", streak=2, done=False))
    assert _tracing_priority(ov) is None


def test_at_risk_counts_only_qualifying_and_reports_longest():
    """Mixed board: 2 at-risk (streak 4 undone, streak 7 undone) + 1 safe (streak 9 done) + 1 below
    (streak 1 undone) → fires with count=2, longest=7 (NOT 9 — the done one is safe, excluded)."""
    ov = _overview(
        _view("run", streak=4, done=False),   # at-risk
        _view("code", streak=7, done=False),  # at-risk (longest of the at-risk set)
        _view("study", streak=9, done=True),  # SAFE (done) — excluded despite the highest streak
        _view("read", streak=1, done=False),  # below MIN — excluded
    )
    p = _tracing_priority(ov)
    assert p is not None and p.severity == "warn"
    assert "2 chuỗi" in p.text and "7 ngày" in p.text  # count=2, longest among at-risk=7


def test_no_activities_none():
    assert _tracing_priority(_overview()) is None  # empty board


def test_none_source_none():
    """Source fail (tracing is None) → None (honest, no crash)."""
    assert _tracing_priority(None) is None


# --- BOTH consumers: daily_brief priority + life_brief section --------------- #
def test_daily_brief_carries_tracing_priority(isolated_paths, monkeypatch):
    """End-to-end consumer 1 (daily_brief = generate_brief): an at-risk streak → a tracing warn
    priority is in the assembled brief.priorities. Inject the at-risk overview via the reader's
    Sources (monkeypatch pull so we don't need to backdate-seed 3 days of logs)."""
    from modules.brief import reader as brief_reader
    real_pull = brief_reader.pull

    def _pull_with_at_risk():
        src = real_pull()
        src.tracing = _overview(_view("run", streak=5, done=False))
        return src

    monkeypatch.setattr(brief_svc.reader, "pull", _pull_with_at_risk)
    brief = brief_svc.generate_brief()
    trc_pri = [p for p in brief.priorities if p.source == "tracing"]
    assert trc_pri and trc_pri[0].severity == "warn", "daily_brief must carry the tracing priority"


def test_life_brief_has_tracing_section(isolated_paths):
    """End-to-end consumer 2 (life_brief): it composes its OWN sections (NOT daily_brief's
    priorities), so it must have its own `tracing` section with a source tag. (recheck-ALL-consumers
    — life_brief does NOT reuse generate_brief, verified.)"""
    import mcp_servers.read_server as rs
    lb = rs.life_brief()
    assert "tracing" in lb["brief"], "life_brief must carry a tracing section"
    assert lb["brief"]["tracing"]["source"] == "tracing"
    # honest-empty on a fresh app: atRisk [] + counts 0, never omitted/fabricated
    assert lb["brief"]["tracing"]["atRisk"] == [] and lb["brief"]["tracing"]["atRiskCount"] == 0


def test_brief_tracing_section_surfaces_at_risk(isolated_paths):
    """_brief_tracing surfaces the at-risk activities (streak≥3 + undone) sorted longest-first."""
    import mcp_servers.read_server as rs
    from modules.tracing import service as trc, store
    from modules.tracing.schema import ActivityInput
    store.init_tracing_tables()
    trc.create_activity(ActivityInput(id="run", name="Run", goal=5.0))
    # backdate 3 met days + today undone → streak 3, at-risk
    from datetime import datetime, timedelta
    from modules.tracing.schema import VN_TZ
    for d in (3, 2, 1):
        day = (datetime.now(VN_TZ).date() - timedelta(days=d)).strftime("%Y-%m-%d")
        store.insert_log(activity_id="run", date=day, ts=f"{day}T08:00:00+07:00", val=6.0,
                         dur_min=None, note=None)
    sec = rs._brief_tracing()
    assert sec["atRiskCount"] == 1 and sec["atRisk"][0]["id"] == "run" and sec["atRisk"][0]["streak"] == 3


# --- PRIORITY_CAP = 7 (no rule silently dropped) ---------------------------- #
def test_priority_cap_is_seven():
    """7 rules now (market/projects/claude/finance/alerts/reminders/tracing) → cap must be 7 so all
    can surface; a stale cap=6 would silently drop the 7th (tracing)."""
    assert brief_svc.PRIORITY_CAP == 7
    assert brief_svc._RULE_ORDER["tracing"] == 7
