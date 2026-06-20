"""tests/test_brief_reminders.py — REMINDERS-4 (#30): reminders surfaced in BOTH brief surfaces.

life_brief gains a ``reminders`` section (what's on the plate: un-done overdue+today+week, lean,
sorted overdue→today→week); daily_brief gains a reminders priority rule (overdue→urgent,
due-today→warn, none→nothing). Additive, reuses the #29 reminders reader.

NB on fixture timing: a "due-today (not overdue)" reminder must be due at a LATER time TODAY
(e.g. now+2h), NOT exactly ``now`` — due==now is instantly past (overdue) by the time overdue is
derived. A real due-today reminder is due at a time today, so now+2h is the honest fixture.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import mcp_servers.read_server as rs
from modules.brief import reader as brief_reader
from modules.brief.service import _reminders_priority
from modules.reminders import service as rem
from modules.reminders import store as rem_store
from modules.reminders.schema import ReminderInput


@pytest.fixture
def rem_db(isolated_paths):
    rem_store.init_reminders_tables()
    return isolated_paths


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_distinguishing() -> dict[str, int]:
    """1 overdue + 1 due-today(not overdue) + 1 next-week + 1 DONE. Returns the ids. ``today`` is
    a robustly-today-future due (halfway to end-of-today UTC) so it can't spill to tomorrow if the
    test runs late in the UTC day."""
    now = _now()
    today_end = now.replace(hour=23, minute=59, second=0, microsecond=0)
    today_due = now + (today_end - now) / 2
    return {
        "overdue": rem.create(ReminderInput(title="OVERDUE", due_at=(now - timedelta(days=2)).isoformat())).id,
        "today": rem.create(ReminderInput(title="TODAY", due_at=today_due.isoformat())).id,
        "week": rem.create(ReminderInput(title="NEXTWEEK", due_at=(now + timedelta(days=5)).isoformat())).id,
        "done": rem.create(ReminderInput(title="DONE", due_at=(now - timedelta(days=1)).isoformat())).id,
    }


# --------------------------------------------------------------------------- #
# _brief_reminders — the life_brief reminders section                           #
# --------------------------------------------------------------------------- #
def test_brief_reminders_distinguishing(rem_db):
    """THE distinguishing fixture: [overdue + today + next-week + DONE] → the 3 un-done in order
    (overdue→today→week), DONE excluded, count:3 overdueCount:1, overdue flag on the overdue one."""
    ids = _seed_distinguishing()
    rem.tick(ids["done"])
    sec = rs._brief_reminders()
    assert sec["count"] == 3 and sec["overdueCount"] == 1
    assert [r["title"] for r in sec["reminders"]] == ["OVERDUE", "TODAY", "NEXTWEEK"]
    assert sec["reminders"][0]["overdue"] is True  # the overdue one
    assert sec["reminders"][1]["overdue"] is False  # due-today, not overdue
    # DONE excluded
    assert not any(r["id"] == str(ids["done"]) for r in sec["reminders"])


def test_brief_reminders_lean_shape(rem_db):
    """Each item is the LEAN 4-key {id,title,due_at,overdue} (NOT the full 10-field reminder)."""
    _seed_distinguishing()
    sec = rs._brief_reminders()
    for r in sec["reminders"]:
        assert set(r) == {"id", "title", "due_at", "overdue"}
        assert isinstance(r["id"], str)  # id stringified per the section contract


def test_brief_reminders_honest_empty(rem_db):
    """No un-done overdue/today/week reminders → honest-empty, NOT omitted/fabricated."""
    sec = rs._brief_reminders()
    assert sec == {"reminders": [], "count": 0, "overdueCount": 0}


def test_brief_reminders_dedup_overdue_in_week(rem_db):
    """An overdue reminder within the past week appears ONCE (it's in both the week filter and the
    overdue set — de-duped by id)."""
    now = _now()
    rid = rem.create(ReminderInput(title="OVERDUE-RECENT", due_at=(now - timedelta(days=1)).isoformat())).id
    sec = rs._brief_reminders()
    assert sec["count"] == 1 and [r["id"] for r in sec["reminders"]].count(str(rid)) == 1


def test_brief_reminders_overdue_beyond_a_week_still_included(rem_db):
    """An overdue reminder MORE than a week past due is still surfaced (the union of week + the
    overdue-undone set catches it — it's still on the plate)."""
    now = _now()
    rid = rem.create(ReminderInput(title="LONG-OVERDUE", due_at=(now - timedelta(days=30)).isoformat())).id
    sec = rs._brief_reminders()
    assert any(r["id"] == str(rid) and r["overdue"] for r in sec["reminders"])


def test_brief_reminders_future_beyond_7d_excluded(rem_db):
    """THE ≤7d boundary NEGATIVE (architect-flagged): a FUTURE reminder >7d out (e.g. +10d) is
    EXCLUDED — it's not overdue (so the undone-union doesn't pull it) and not ≤now+7d (so the week
    filter doesn't either). this-week = due ≤ now+7d ROLLING, not a calendar-week-end."""
    now = _now()
    in_window = rem.create(ReminderInput(title="IN+5d", due_at=(now + timedelta(days=5)).isoformat())).id
    out_window = rem.create(ReminderInput(title="OUT+10d", due_at=(now + timedelta(days=10)).isoformat())).id
    sec = rs._brief_reminders()
    ids = {r["id"] for r in sec["reminders"]}
    assert str(in_window) in ids, "a +5d (≤7d) reminder IS in-window"
    assert str(out_window) not in ids, "a +10d (>7d) future reminder is EXCLUDED (the ≤7d boundary)"


def test_life_brief_has_reminders_section(rem_db):
    """life_brief carries a top-level ``reminders`` section with the source tag (via _section)."""
    _seed_distinguishing()
    lb = rs.life_brief()
    assert "reminders" in lb["brief"]
    assert lb["brief"]["reminders"]["source"] == "reminders"
    assert lb["brief"]["reminders"]["count"] == 4 - 0  # 4 un-done (none ticked here)


def test_brief_reminders_fail_soft_section(rem_db, monkeypatch):
    """A reader error → the section is soft-skipped ({source, error}), the brief still assembles
    (the _section fail-soft add-on pattern)."""
    monkeypatch.setattr(rs, "_brief_reminders",
                        lambda: (_ for _ in ()).throw(RuntimeError("reminders down")))
    lb = rs.life_brief()
    assert lb["brief"]["reminders"]["source"] == "reminders"
    assert "error" in lb["brief"]["reminders"]  # soft-skipped, brief still built
    assert "portfolio" in lb["brief"]  # other sections still present


# --------------------------------------------------------------------------- #
# daily_brief reminders priority rule (overdue→urgent, today→warn, none→nothing) #
# --------------------------------------------------------------------------- #
def test_daily_priority_overdue_is_urgent(rem_db):
    _seed_distinguishing()  # has an overdue
    p = _reminders_priority(brief_reader.pull().reminders)
    assert p is not None and p.severity == "urgent" and p.source == "reminders"


def test_daily_priority_due_today_is_warn(rem_db):
    """No overdue, but a due-today un-done → WARN (not urgent). Use a due that's robustly
    today-FUTURE (between now and end-of-today UTC) — now+2h could spill into tomorrow UTC if the
    test runs late in the day (then it'd be 'this week', not 'today')."""
    now = _now()
    today_end = now.replace(hour=23, minute=59, second=0, microsecond=0)
    # halfway from now to end-of-today → always > now AND ≤ today_end (today, not yet due)
    due = now + (today_end - now) / 2
    rem.create(ReminderInput(title="TODAY", due_at=due.isoformat()))
    p = _reminders_priority(brief_reader.pull().reminders)
    assert p is not None and p.severity == "warn"


def test_daily_priority_none_when_nothing_due(rem_db):
    """No overdue, nothing due today (only a next-week reminder) → NO priority entry (0-1 rule)."""
    now = _now()
    rem.create(ReminderInput(title="NEXTWEEK", due_at=(now + timedelta(days=5)).isoformat()))
    p = _reminders_priority(brief_reader.pull().reminders)
    assert p is None


def test_daily_priority_empty_no_entry(rem_db):
    assert _reminders_priority(brief_reader.pull().reminders) is None


def test_daily_brief_carries_reminders_urgent(rem_db):
    """End-to-end: generate_brief with an overdue reminder → a reminders urgent priority is in the
    assembled brief's priorities."""
    from modules.brief import service as brief_svc
    _seed_distinguishing()  # overdue present
    brief = brief_svc.generate_brief()
    rem_pri = [p for p in brief.priorities if p.source == "reminders"]
    assert rem_pri and rem_pri[0].severity == "urgent"
