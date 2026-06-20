"""tests/test_reminders_notify.py — REMINDERS-3 (#29): the notify engine (the alarm fires).

MOCKABLE CLOCK — every test injects ``now`` into notify_scan(now=...) so re-notify-after-X +
roll-forward are testable INSTANTLY (no real waits). Discord is monkeypatched (assert it's CALLED,
never actually post); the fail-soft path is tested by making the poster raise.

The HARD GATE (distinguishing, both directions):
  - due + count 0 → fires once (count→1, last_notified set); a 2nd scan before re_notify_every →
    NO re-fire (double-fire avoidance).
  - re_notify_every=X + X elapsed + count<max → re-fires; count>=max → STOPS Discord.
  - tick a daily → series stops (done_at filters it out).  [SEMANTIC 1]
  - repeat=daily → fires each period (roll-on-fire); repeat=once → fires once, never rolls.
  - freshly-overdue PRE-cap → overdue=True (NOT cap-gated).  [SEMANTIC 2]
  - webhook FAILS → routine doesn't crash, other reminders still scanned.
  - NOT-yet-due → not fired.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import modules.reminders.service as svc
from modules.reminders import service, store
from modules.reminders.schema import ReminderInput

T0 = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def rem_db(isolated_paths, monkeypatch):
    store.init_reminders_tables()
    # capture notify calls without posting (default for most tests)
    calls: list[str] = []
    monkeypatch.setattr(svc, "_notify", lambda msg: (calls.append(msg) or True))
    return calls


def _mk(title: str, due: datetime, **kw) -> int:
    return service.create(ReminderInput(title=title, due_at=due.isoformat(), **kw)).id


# --------------------------------------------------------------------------- #
# first fire + double-fire avoidance                                            #
# --------------------------------------------------------------------------- #
def test_due_fires_once(rem_db):
    rid = _mk("Alarm", T0)
    s = svc.notify_scan(now=T0)
    assert s["fired"] == 1
    r = service.get(rid)
    assert r.notified_count == 1 and r.last_notified is not None
    assert len(rem_db) == 1  # exactly one Discord call


def test_no_double_fire_before_cadence(rem_db):
    rid = _mk("Alarm", T0)
    svc.notify_scan(now=T0)
    s2 = svc.notify_scan(now=T0 + timedelta(seconds=30))  # no re_notify configured
    assert s2["fired"] == 0, "a 2nd scan must NOT re-fire (no re_notify → fired once)"
    assert service.get(rid).notified_count == 1


def test_not_yet_due_does_not_fire(rem_db):
    _mk("Future", T0 + timedelta(hours=1))
    assert svc.notify_scan(now=T0)["fired"] == 0


# --------------------------------------------------------------------------- #
# re-notify cadence + cap                                                        #
# --------------------------------------------------------------------------- #
def test_renotify_after_cadence(rem_db):
    rid = _mk("Nag", T0, re_notify_every=5, max_times=3)
    svc.notify_scan(now=T0)                                  # first fire → count 1
    assert svc.notify_scan(now=T0 + timedelta(minutes=3))["fired"] == 0   # 3 < 5 → no
    assert svc.notify_scan(now=T0 + timedelta(minutes=6))["fired"] == 1   # 6 >= 5 → re-fire
    assert service.get(rid).notified_count == 2


def test_cap_stops_discord(rem_db):
    rid = _mk("Nag", T0, re_notify_every=5, max_times=3)
    svc.notify_scan(now=T0)                       # 1
    svc.notify_scan(now=T0 + timedelta(minutes=6))   # 2
    svc.notify_scan(now=T0 + timedelta(minutes=12))  # 3 (cap)
    assert service.get(rid).notified_count == 3
    # past the cap → no more Discord (overdue/RED in-app takes over)
    assert svc.notify_scan(now=T0 + timedelta(minutes=30))["fired"] == 0


def test_default_cap_is_3_when_no_max_times(rem_db):
    rid = _mk("Nag", T0, re_notify_every=1)  # no max_times → default 3
    for m in (0, 1, 2, 3, 4, 5):
        svc.notify_scan(now=T0 + timedelta(minutes=m))
    assert service.get(rid).notified_count == 3, "default cap of 3 applies when max_times is None"


# --------------------------------------------------------------------------- #
# SEMANTIC 1 — repeat roll-on-fire + tick-ends-series                            #
# --------------------------------------------------------------------------- #
def test_repeat_daily_rolls_due_forward_and_resets(rem_db):
    rid = _mk("Daily", T0, repeat="daily")
    svc.notify_scan(now=T0)
    r = service.get(rid)
    assert r.due_at > T0.isoformat(), "daily rolls due_at forward on fire"
    assert r.notified_count == 0 and r.last_notified is None, "roll resets count/last_notified"
    # the rolled due is ~1 day ahead (the next period)
    rolled = datetime.fromisoformat(r.due_at)
    assert rolled == T0 + timedelta(days=1)


def test_repeat_once_never_rolls(rem_db):
    rid = _mk("Once", T0, repeat="once")
    svc.notify_scan(now=T0)
    r = service.get(rid)
    assert r.due_at == T0.isoformat(), "a once reminder never rolls"
    assert r.notified_count == 1


def test_tick_ends_daily_series(rem_db):
    """SEMANTIC 1: tick a daily → it's done_at-set → NOT scanned → never fires again."""
    rid = _mk("Daily", T0, repeat="daily")
    svc.notify_scan(now=T0)               # fires + rolls to T0+1d
    service.tick(rid)                     # user says "stop reminding"
    rolled_due = datetime.fromisoformat(service.get(rid).due_at)
    s = svc.notify_scan(now=rolled_due + timedelta(minutes=1))  # past the rolled due
    assert s["fired"] == 0, "a ticked daily must NOT fire (done ends the series)"
    assert service.get(rid).done_at is not None


# --------------------------------------------------------------------------- #
# SEMANTIC 2 — overdue = un-done AND past-due, NOT cap-gated                     #
# --------------------------------------------------------------------------- #
def test_overdue_is_undone_and_past_due_not_cap_gated(rem_db):
    """THE distinguishing for SEMANTIC 2: a freshly-overdue reminder (count 0, well below cap) is
    overdue=True the moment it's past-due. overdue is INDEPENDENT of the notify cap."""
    past = _mk("Past", datetime.now(timezone.utc) - timedelta(hours=2))
    r = service.get(past)
    assert r.overdue is True and r.notified_count == 0, \
        "overdue=True for un-done past-due even at count 0 (NOT cap-gated)"


def test_not_overdue_when_future_or_done(rem_db):
    fut = _mk("Future", datetime.now(timezone.utc) + timedelta(days=2))
    assert service.get(fut).overdue is False, "future → not overdue"
    past = _mk("PastDone", datetime.now(timezone.utc) - timedelta(hours=2))
    service.tick(past)
    assert service.get(past).overdue is False, "done → not overdue (even if past-due)"


# --------------------------------------------------------------------------- #
# fail-soft — a webhook failure doesn't crash the scan; other reminders run     #
# --------------------------------------------------------------------------- #
def test_webhook_failure_is_fail_soft(isolated_paths, monkeypatch):
    """A Discord post that RAISES must NOT crash the scan — _notify catches it (returns False);
    the reminder is still marked notified (the fire was attempted) + other reminders still scanned.
    Tests the real _notify fail-soft path (monkeypatch urlopen to raise)."""
    store.init_reminders_tables()
    import urllib.request
    monkeypatch.setattr(svc, "_discord_webhook", lambda: "http://fake.invalid/hook")
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network down")))
    a = _mk("A", T0)
    b = _mk("B", T0)
    s = svc.notify_scan(now=T0)  # must NOT raise
    assert s["scanned"] == 2, "both reminders scanned despite the webhook failure"
    # the scan continued + recorded the fire attempt for both (fail-soft: a failed post still
    # advances state so it doesn't retry-storm every minute)
    assert service.get(a).notified_count == 1 and service.get(b).notified_count == 1


def test_notify_silent_skip_when_no_webhook(rem_db, monkeypatch):
    """No webhook configured → _notify silent-skips (returns False), the scan still runs + marks
    notified (honest: the reminder is 'fired' from the engine's POV; Discord just had nowhere to go)."""
    monkeypatch.setattr(svc, "_notify", svc._notify)  # use the real one
    monkeypatch.setattr(svc, "_discord_webhook", lambda: "")  # no webhook
    rid = _mk("A", T0)
    s = svc.notify_scan(now=T0)
    assert s["fired"] == 1  # the engine fired (advanced state); the Discord post was a no-op skip
    assert service.get(rid).notified_count == 1


# --------------------------------------------------------------------------- #
# the routine wrapper records a run                                              #
# --------------------------------------------------------------------------- #
def test_routine_records_run_and_attributes(rem_db):
    """reminders_notify() runs via auto.run_scheduled → a run_log row under 'reminders-notify',
    and the routine is in the automation catalog (friendly-name attribution)."""
    from modules.reminders import router as rem_router
    from store import db as _db
    _mk("A", T0)
    rem_router.reminders_notify()  # the scheduler entry point
    runs = _db.recent_runs(service.NOTIFY_ROUTINE_ID, limit=5)
    assert len(runs) == 1 and runs[0]["routine_id"] == "reminders-notify"
    from modules.automation.service import _CATALOG_BY_ID
    assert "reminders-notify" in _CATALOG_BY_ID and _CATALOG_BY_ID["reminders-notify"]["name"]
