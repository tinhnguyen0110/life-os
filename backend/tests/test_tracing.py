"""tests/test_tracing.py — DAILY-TRACING-P1 (#65) derivation tests.

The G-HABIT module: raw sessions logged → metrics DERIVED server-side (today/streak/week/
history12w/heatmap12w/score), ALL VN-day (UTC+7). These tests are the DIVERGENT distinguishing set
(the dispatch's HARD GATE) — each uses a case where a correct derivation ≠ a plausible-wrong one:
  - accumulate (2 same-day sessions SUM, not overwrite)
  - streak resets on a gap (3-met-then-skip → only the post-gap run counts)
  - heatmap day-score is a COUNT of met activities (1 met → 1, both → 2), NOT a boolean
  - VN-tz: a 23:30-VN session buckets to its VN day (not UTC-tomorrow)
  - honest-empty: a fresh activity → all-0 derived (no fabricated streak)
  - goal==0 → pct 0, never divide-by-zero, never done

Tests drive through the SERVICE (the derive surface) on an isolated db; the date is controlled by
seeding logs with explicit `date=` so the assertions don't depend on the wall clock except where the
VN-today bucket is the point (those monkeypatch vn_today).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from modules.tracing import service as svc
from modules.tracing import store
from modules.tracing.schema import ActivityInput, LogInput, VN_TZ


@pytest.fixture
def db(isolated_paths):
    """Fresh isolated db with the tracing tables created."""
    store.init_tracing_tables()
    return isolated_paths


def _mk(activity_id="run", *, goal=5.0, unit="km"):
    return svc.create_activity(ActivityInput(id=activity_id, name=activity_id.title(),
                                             goal=goal, unit=unit))


def _today():
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def _days_ago(n: int) -> str:
    return (datetime.now(VN_TZ).date() - timedelta(days=n)).strftime("%Y-%m-%d")


# --- accumulate (2 same-day sessions SUM, not overwrite) -------------------- #
def test_two_same_day_sessions_accumulate(db):
    _mk("run", goal=10.0)
    svc.log_session("run", LogInput(val=4.0))
    view = svc.log_session("run", LogInput(val=3.0))  # same VN-day → accumulate
    assert view.today.val == 7.0, "two same-day logs must SUM (4+3), not overwrite to 3"
    assert view.today.sessions == 2
    assert view.today.pct == 70  # 7/10
    assert view.today.done is False
    # a 3rd that crosses the goal flips done
    view2 = svc.log_session("run", LogInput(val=5.0))
    assert view2.today.val == 12.0 and view2.today.done is True and view2.today.pct == 100


def test_dur_and_note_rollup_today(db):
    _mk("code", goal=2.0, unit="h")
    svc.log_session("code", LogInput(val=1.0, dur_min=50, note="morning"))
    view = svc.log_session("code", LogInput(val=1.0, dur_min=40, note="evening"))
    assert view.today.durMin == 90 and view.today.dur == "1h 30m"
    assert view.today.note == "evening"  # the latest session's note


# --- streak resets on a gap (the DIVERGENT case) --------------------------- #
def test_streak_three_consecutive_then_gap_resets(db):
    """3 goal-met days then a SKIPPED day → the streak counts only the post-gap run, NOT 3.
    A naive 'count all met days' would wrongly report 3; the gap must break it."""
    act = _mk("run", goal=5.0)
    today = _today()
    # met on day-4, day-3, day-2 (3 consecutive) ... then a GAP on day-1 (no log) ... met today.
    for d in (4, 3, 2):
        store.insert_log(activity_id="run", date=_days_ago(d), ts=f"{_days_ago(d)}T08:00:00+07:00",
                         val=6.0, dur_min=None, note=None)
    # day-1 SKIPPED (the gap)
    store.insert_log(activity_id="run", date=today, ts=f"{today}T08:00:00+07:00",
                     val=6.0, dur_min=None, note=None)
    view = svc.get_activity("run")
    assert view is not None
    from modules.tracing.reader import get_activity_view
    v = get_activity_view("run")
    assert v is not None
    # post-gap run = just today (the gap on day-1 severs the older 3-day run).
    assert v.streak == 1, f"a gap must reset the streak — expected 1 (today only), got {v.streak}"


def test_streak_today_incomplete_does_not_break(db):
    """today-incomplete does NOT break the streak: 3 met days through yesterday, today not yet met
    → streak still 3 (today = at-risk, counted-if-met, not a break)."""
    _mk("run", goal=5.0)
    for d in (3, 2, 1):  # yesterday, day-2, day-3 all met
        store.insert_log(activity_id="run", date=_days_ago(d), ts=f"{_days_ago(d)}T08:00:00+07:00",
                         val=6.0, dur_min=None, note=None)
    # today: a partial log (below goal) → today not met, but the run through yesterday stands.
    svc.log_session("run", LogInput(val=1.0))
    from modules.tracing.reader import get_activity_view
    v = get_activity_view("run")
    assert v is not None
    assert v.today.done is False
    assert v.streak == 3, f"today-incomplete must NOT break a 3-day streak, got {v.streak}"


def test_streak_today_met_includes_today(db):
    """3 met days through yesterday + today also met → streak 4 (today included)."""
    _mk("run", goal=5.0)
    for d in (3, 2, 1):
        store.insert_log(activity_id="run", date=_days_ago(d), ts=f"{_days_ago(d)}T08:00:00+07:00",
                         val=6.0, dur_min=None, note=None)
    svc.log_session("run", LogInput(val=6.0))  # today met
    from modules.tracing.reader import get_activity_view
    v = get_activity_view("run")
    assert v is not None and v.streak == 4


# --- heatmap day-score is a COUNT, not a boolean --------------------------- #
def test_heatmap_dayscore_is_count_of_met_activities(db):
    """heatmap day-score = COUNT of activities that met goal that day (0..N). Seed 2 activities:
    on a day where only 1 meets → score 1; a day where both meet → score 2. A boolean impl would
    cap at 1 and fail the both-met day."""
    _mk("run", goal=5.0)
    _mk("code", goal=2.0, unit="h")
    today = _today()
    yesterday = _days_ago(1)
    # yesterday: only run meets (code logs below goal) → score 1
    store.insert_log(activity_id="run", date=yesterday, ts=f"{yesterday}T08:00:00+07:00",
                     val=6.0, dur_min=None, note=None)
    store.insert_log(activity_id="code", date=yesterday, ts=f"{yesterday}T09:00:00+07:00",
                     val=1.0, dur_min=None, note=None)  # below code's goal of 2
    # today: BOTH meet → score 2
    store.insert_log(activity_id="run", date=today, ts=f"{today}T08:00:00+07:00",
                     val=6.0, dur_min=None, note=None)
    store.insert_log(activity_id="code", date=today, ts=f"{today}T09:00:00+07:00",
                     val=3.0, dur_min=None, note=None)
    ov = svc.overview()
    assert len(ov.heatmap12w) == 84
    # the heatmap is oldest→newest ending today → today is the LAST cell, yesterday second-last.
    assert ov.heatmap12w[-1] == 2, "both met today → day-score 2 (a COUNT, not a capped boolean)"
    assert ov.heatmap12w[-2] == 1, "only run met yesterday → day-score 1"
    # score roll-up: 2 active, 2 done today
    assert ov.score.total == 2 and ov.score.done == 2 and ov.score.pct == 100


# --- VN-tz day bucketing --------------------------------------------------- #
def test_vn_late_night_session_buckets_to_vn_day(db):
    """A 23:30-VN session counts on its VN day, NOT UTC-tomorrow. vn_day_of must bucket
    '2026-06-21T23:30:00+07:00' → 2026-06-21 (in UTC it's 16:30Z same day, but the point is the
    VN-day rule holds for an end-of-day-VN ts that an offset/naive parse could mis-bucket)."""
    from modules.tracing.schema import vn_day_of
    # offset-aware late-night VN
    assert vn_day_of("2026-06-21T23:30:00+07:00") == "2026-06-21"
    # a UTC ts that is 23:30 UTC = 06:30-VN NEXT day → buckets to the VN day (the 22nd)
    assert vn_day_of("2026-06-21T23:30:00+00:00") == "2026-06-22"
    # naive ts → assumed already VN
    assert vn_day_of("2026-06-21T23:30:00") == "2026-06-21"


# --- honest-empty + goal==0 ------------------------------------------------ #
def test_fresh_activity_all_zero_no_fabrication(db):
    """A fresh activity with NO sessions → today all-0, streak 0, week/history all-0 — HONEST,
    never a fabricated streak."""
    _mk("study", goal=3.0)
    from modules.tracing.reader import get_activity_view
    v = get_activity_view("study")
    assert v is not None
    assert v.today.val == 0 and v.today.done is False and v.today.pct == 0
    assert v.streak == 0
    assert v.week == [0.0] * 7
    assert v.history12w == [0.0] * 84 and len(v.history12w) == 84


def test_no_activities_honest_empty_board(db):
    """No activities at all → activities [], score all-0, heatmap all-0 (+ honest empty)."""
    ov = svc.overview()
    assert ov.activities == []
    assert ov.score.total == 0 and ov.score.done == 0 and ov.score.pct == 0
    assert ov.heatmap12w == [0] * 84


def test_goal_zero_no_divide_never_done(db):
    """goal==0 → pct 0 (no divide-by-zero), done False, and it never contributes to the heatmap."""
    _mk("freeform", goal=0.0)
    view = svc.log_session("freeform", LogInput(val=99.0))
    assert view.today.pct == 0 and view.today.done is False and view.today.val == 99.0
    assert view.streak == 0  # goal<=0 → never met → no streak
    ov = svc.overview()
    assert ov.heatmap12w[-1] == 0, "a goal==0 activity must not score on the heatmap"


# --- log against unknown activity (service assumes router-checked existence) - #
def test_log_unknown_activity_is_404_at_router(db):
    """The router 404s an unknown activity before service.log_session. Verify the existence check
    the router relies on (service.get_activity returns None for unknown)."""
    assert svc.get_activity("ghost") is None


# --- archive drops off the board, logs survive ----------------------------- #
def test_archive_removes_from_board_keeps_logs(db):
    _mk("run", goal=5.0)
    svc.log_session("run", LogInput(val=6.0))
    assert svc.overview().score.total == 1
    assert svc.archive_activity("run") is True
    ov = svc.overview()
    assert ov.score.total == 0 and ov.activities == []  # off the board
    # the def still exists (archived) + its logs are intact (history preserved)
    act = svc.get_activity("run")
    assert act is not None and act.archived is True
    assert len(store.logs_for_activity("run")) == 1


# --- #102 PERF: heatmap/overview at 100 act × 1yr stays within budget ------- #
@pytest.mark.slow  # PERF #102: seeds 100 act × 365 days (~36.5k logs) — opt-in via -m slow
def test_102_overview_perf_at_scale(db):
    """#102 MEASURE-FIRST regression pin: the suspected _derive_heatmap cliff was measured at
    ~46ms (overview) / ~10ms (heatmap) for 100 activities × 1 year — well within the <500ms
    budget → YAGNI, no optimization. This test PINS that: it seeds the worst realistic scale and
    asserts overview() stays under a generous 1.0s ceiling (10× headroom over the measured 46ms,
    catching a real O(act×day×logs) regression while tolerating slow CI hardware) AND that the
    heatmap still computes real per-day COUNTS (not blanked by any future 'fix'). The heatmap reads
    all logs ONCE into a dict then loops O(84×N) — O(logs + 84×N), not O(logs×84×N)."""
    import time

    n_act, days = 100, 365
    today = datetime.now(VN_TZ).date()
    start = today - timedelta(days=days - 1)
    for i in range(n_act):
        _mk(f"act{i:03d}", goal=30.0, unit="min")
    # bulk-seed logs straight through the store (the derive path is what we measure, not inserts)
    for i in range(n_act):
        aid = f"act{i:03d}"
        for d in range(days):
            day = (start + timedelta(days=d)).strftime("%Y-%m-%d")
            val = 35.0 if (d + i) % 3 == 0 else 20.0  # some days meet goal(30), some don't
            store.insert_log(activity_id=aid, date=day, ts=f"{day}T08:00:00+07:00",
                             val=val, dur_min=30, note=None)

    t = time.perf_counter()
    ov = svc.overview()
    elapsed = time.perf_counter() - t

    assert len(ov.activities) == n_act
    assert len(ov.heatmap12w) == 84
    # the heatmap is a real per-day COUNT (not blanked / not all-N) — some days N met, some fewer
    assert any(c > 0 for c in ov.heatmap12w), "heatmap must carry real counts, not all-0"
    assert max(ov.heatmap12w) <= n_act
    # PERF budget: measured ~46ms; 1.0s ceiling = 20× headroom, fails only on a real cliff regression
    assert elapsed < 1.0, f"overview() at {n_act}act×{days}d took {elapsed*1000:.0f}ms (budget 1000ms)"
