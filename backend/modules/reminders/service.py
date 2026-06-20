"""modules/reminders/service.py — reminders business logic (REMINDERS-1 #27, REMINDERS-3 #29).

CRUD + the tick lifecycle + the due/done filtered list (#27) + the NOTIFY ENGINE (#29: the alarm
fires). Coordinates store (SQLite) + reader (fail-open mapping). Single-user, no auth.

The notify engine (#29) — the reminders-notify routine scans un-done reminders each minute:
  - first fire: due + notified_count==0 → Discord + count=1, last_notified=now.
  - re-notify: count≥1 + re_notify_every set + count<max + cadence elapsed → fire again.
  - cap: count≥(max_times or 3) → stop Discord (overdue/RED in-app takes over).
  - SEMANTIC 1: repeat (daily|weekly) rolls due_at forward on fire (+resets count) — UNTIL ticked
    (done ends the series: a ticked reminder isn't scanned).
  - SEMANTIC 2: overdue = un-done AND past-due (derived in the reader), NOT cap-gated.
Discord is fail-SOFT per reminder (one webhook fail → log + continue; the routine still records).
"""

from __future__ import annotations

import json
import logging
import pathlib
import urllib.request
from datetime import datetime, timedelta, timezone

from . import store
from .reader import map_rows, row_to_reminder
from .schema import Reminder, ReminderInput, ReminderList, now_iso

logger = logging.getLogger("life-os.reminders.service")

# REMINDERS-3 (#29): default re-notify cap when a reminder sets re_notify_every but no max_times.
_DEFAULT_MAX_TIMES = 3
NOTIFY_ROUTINE_ID = "reminders-notify"


def create(inp: ReminderInput) -> Reminder:
    """Create a reminder from a validated input (due_at already validated parseable by the schema
    → the router never reaches here with a bad due_at). Returns the stored Reminder."""
    rid = store.create_reminder(
        title=inp.title, note=inp.note, due_at=inp.due_at, repeat=inp.repeat,
        re_notify_every=inp.re_notify_every, max_times=inp.max_times, created=now_iso(),
    )
    row = store.get_reminder(rid)
    assert row is not None  # just inserted
    return row_to_reminder(row)


def get(reminder_id: int) -> Reminder | None:
    """One reminder by id, or None (→ 404 at the router)."""
    row = store.get_reminder(reminder_id)
    return row_to_reminder(row) if row is not None else None


def tick(reminder_id: int) -> Reminder | None:
    """Mark a reminder done. IDEMPOTENT — re-ticking a done reminder is a no-op (done_at keeps
    its first value), returns the reminder. None if the reminder doesn't exist (→ 404)."""
    row = store.tick_reminder(reminder_id, ts=now_iso())
    return row_to_reminder(row) if row is not None else None


def delete(reminder_id: int) -> bool:
    """Delete a reminder. True if removed, False if absent (→ 404)."""
    return store.delete_reminder(reminder_id)


def list_reminders(filter_key: str | None) -> tuple[ReminderList, list[str]]:
    """The filtered list + counts. Returns (ReminderList, warnings). Fail-open: a malformed row
    is skipped + warned, never crashes. ``undoneCount`` = how many in this list have done_at NULL
    (for 'all'/'undone' that's the undone subset; for 'today'/'week' all are undone by construction)."""
    rows = store.list_reminders(filter_key)
    reminders, warnings = map_rows(rows)
    undone = sum(1 for r in reminders if r.done_at is None)
    view = ReminderList(
        reminders=reminders,
        count=len(reminders),
        undoneCount=undone,
        filter=store.canonical_filter(filter_key),
    )
    return view, warnings


# --------------------------------------------------------------------------- #
# REMINDERS-3 (#29) — the notify engine (the alarm fires)                        #
# --------------------------------------------------------------------------- #
def _discord_webhook() -> str:
    """Read the Discord webhook from .env ``discord=`` (mirrors .claude/process/notify.py). No
    .env / no key → "" (→ _notify silent-skips). Single-user, no secret store."""
    env = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.strip().startswith("discord="):
            return line.split("=", 1)[1].strip()
    return ""


def _notify(msg: str) -> bool:
    """Post a NEUTRAL reminder message to Discord. Fail-SOFT: no webhook → silent-skip (returns
    False, not an error); a post failure → log + return False (the scan continues). Returns True
    only on a successful post. Mirrors notify.py (urllib, 10s timeout, no new dependency)."""
    url = _discord_webhook()
    if not url or not msg:
        return False
    try:
        req = urllib.request.Request(
            url, data=json.dumps({"content": msg}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "life-os-reminders/1.0"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001 — fail-soft: a webhook fail must not break the scan
        logger.warning("reminders notify skipped (webhook fail): %s", exc)
        return False


def _roll_due_at(due_at: str, repeat: str, now: datetime) -> str:
    """SEMANTIC 1: roll a repeat reminder's due_at forward by its period (+1 day / +1 week),
    advancing PAST ``now`` so the next fire is in the future even if several periods were missed
    (no fire-storm catching up). ``once`` never calls this. due_at is UTC-normalized (#1A)."""
    step = timedelta(days=1) if repeat == "daily" else timedelta(weeks=1)
    try:
        nxt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        nxt = now
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=timezone.utc)
    # advance at least one period, and past now (skip missed periods → one future due, no storm)
    nxt = nxt + step
    while nxt <= now:
        nxt = nxt + step
    return nxt.astimezone(timezone.utc).isoformat()


def _should_fire(row, now_iso_str: str, now: datetime) -> bool:
    """Decide if a (un-done) reminder fires THIS scan tick.
      - first fire: due (due_at <= now) AND notified_count == 0.
      - re-notify: count>=1 AND re_notify_every set AND count < (max_times or 3) AND the cadence
        has elapsed since last_notified ((now - last_notified) >= re_notify_every minutes).
      - cap: count >= (max_times or 3) → no Discord (returns False).
    The count + last_notified gating makes the 1-min scan IDEMPOTENT (no double-fire within a window)."""
    if row["due_at"] > now_iso_str:
        return False  # not yet due
    count = int(row["notified_count"])
    if count == 0:
        return True  # first fire
    every = row["re_notify_every"]
    if every is None:
        return False  # fired once, no re-notify configured
    cap = row["max_times"] if row["max_times"] is not None else _DEFAULT_MAX_TIMES
    if count >= cap:
        return False  # cap reached → stop Discord (overdue/RED in-app takes over)
    last = row["last_notified"]
    if not last:
        return False  # defensive: count>=1 but no last_notified → wait for a clean state
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False
    return (now - last_dt) >= timedelta(minutes=int(every))


def notify_scan(now: datetime | None = None) -> dict:
    """The reminders-notify engine (one scan tick). Scans UN-DONE reminders and fires per
    _should_fire; on fire → Discord (fail-soft) + mark_notified; a REPEAT reminder also rolls its
    due_at forward (SEMANTIC 1). ``now`` is injectable (mockable clock — tests don't wait real
    minutes). Returns {scanned, fired, rolled} for the run-log detail. Fail-soft per reminder."""
    now = now or datetime.now(timezone.utc)
    now_iso_str = now.astimezone(timezone.utc).isoformat()
    scanned = fired = rolled = 0
    for row in store.undone_reminders():
        scanned += 1
        try:
            if not _should_fire(row, now_iso_str, now):
                continue
            _notify(f"⏰ Reminder: {row['title']} (due {row['due_at']})")  # fail-soft inside
            fired += 1
            if row["repeat"] in ("daily", "weekly"):
                # SEMANTIC 1: roll forward + reset count/last_notified (next period fires fresh).
                store.roll_repeat(int(row["id"]), new_due_at=_roll_due_at(row["due_at"], row["repeat"], now))
                rolled += 1
            else:
                store.mark_notified(int(row["id"]),
                                    notified_count=int(row["notified_count"]) + 1,
                                    last_notified=now_iso_str)
        except Exception as exc:  # noqa: BLE001 — one reminder must not break the scan
            logger.warning("reminders notify: reminder %s failed (continuing): %s",
                           row["id"] if "id" in row.keys() else "?", exc)
            continue
    return {"scanned": scanned, "fired": fired, "rolled": rolled}
