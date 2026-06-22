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

import logging
from datetime import datetime, timedelta, timezone

from . import store
from .reader import map_rows, row_to_reminder
from .schema import Reminder, ReminderInput, ReminderList, now_iso

logger = logging.getLogger("life-os.reminders.service")

# REMINDERS-3 (#29): default re-notify cap when a reminder sets re_notify_every but no max_times.
_DEFAULT_MAX_TIMES = 3
NOTIFY_ROUTINE_ID = "reminders-notify"


# --------------------------------------------------------------------------- #
# TRACING-UX T3 (#111) — delivery channels (REUSE the alerts engine's detection) #
# --------------------------------------------------------------------------- #
def _channel_available(channel: str) -> bool:
    """Is a channel deliverable? in_app always; email/discord via the alerts engine's configured-
    detection (the ONE source — no separate .env read here)."""
    from modules.alerts import service as alerts
    if channel == "discord":
        return alerts.discord_configured()
    if channel == "email":
        return alerts.mail_configured()
    return True  # in_app always available


def list_channels() -> list[dict]:
    """The delivery-channel list for the FE/agent: ``[{id,label,available,reason?}]``. ``available``
    REUSES the alerts engine's configured-detection (single source, can't drift from /alerts/config).
    An unavailable channel carries a ``reason`` so the picker can explain why it's disabled."""
    out: list[dict] = [{"id": "in_app", "label": "In-app", "available": True}]
    for cid, label, cred in (("email", "Email", "SMTP credentials"),
                             ("discord", "Discord", "Discord webhook")):
        avail = _channel_available(cid)
        entry: dict = {"id": cid, "label": label, "available": avail}
        if not avail:
            entry["reason"] = f"{label} not configured ({cred} absent in .env)"
        out.append(entry)
    return out


def resolve_channel(inp: ReminderInput) -> tuple[ReminderInput, str | None]:
    """#111 unavailable-channel fallback: if ``inp.channel`` is email/discord but NOT configured →
    return a copy DOWNGRADED to in_app + a warning string (honest-mirror — the reminder still works,
    the warning explains the downgrade). Available channel (or in_app) → unchanged + None."""
    if inp.channel != "in_app" and not _channel_available(inp.channel):
        warning = (f"{inp.channel} not configured → reminder created as in_app "
                   f"(it shows in /reminders but won't send via {inp.channel})")
        return inp.model_copy(update={"channel": "in_app"}), warning
    return inp, None


def create(inp: ReminderInput) -> Reminder:
    """Create a reminder from a validated input (due_at already validated parseable by the schema
    → the router never reaches here with a bad due_at). Returns the stored Reminder."""
    rid = store.create_reminder(
        title=inp.title, note=inp.note, due_at=inp.due_at, repeat=inp.repeat,
        re_notify_every=inp.re_notify_every, max_times=inp.max_times, created=now_iso(),
        channel=inp.channel,  # #111: user-settable delivery channel (default in_app)
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


# --------------------------------------------------------------------------- #
# TRACING-REMINDERS (#75) — the tracing→reminder wire (one-way, internal-only).  #
# The forge-guard: source='tracing' is set ONLY here (the tracing service calls   #
# these); the public create(ReminderInput) can't set source (not an input field).  #
# --------------------------------------------------------------------------- #
def upsert_for_activity(*, activity_id: str, title: str, due_at: str, repeat: str,
                        channel: str = "in_app") -> Reminder:
    """Create-or-update the reminder linked to ``activity_id`` (source='tracing'). find-by-activity:
    none → create (source=tracing), else → update title/due_at/repeat/channel. Idempotent — a re-sync
    on the same activity UPDATES, never duplicates. Returns the linked Reminder. (Called by the tracing
    service when an activity has remind_at + remind_repeat≠off.) ``due_at`` is already a UTC ISO.
    ``channel`` (#111) = the activity's remindChannel (default in_app)."""
    existing = store.find_by_activity(activity_id, source="tracing")
    if existing is None:
        rid = store.create_reminder(
            title=title, note=None, due_at=due_at, repeat=repeat,
            re_notify_every=None, max_times=None, created=now_iso(),
            source="tracing", activity_id=activity_id, channel=channel,
        )
        row = store.get_reminder(rid)
    else:
        row = store.update_reminder(int(existing["id"]), title=title, due_at=due_at,
                                    repeat=repeat, channel=channel)
    assert row is not None
    return row_to_reminder(row)


def delete_for_activity(activity_id: str) -> bool:
    """Delete the tracing-linked reminder for ``activity_id`` (if any). True if one was removed. Called
    when the activity clears its remind / is archived. ONE-WAY (only tracing drives this)."""
    existing = store.find_by_activity(activity_id, source="tracing")
    if existing is None:
        return False
    return store.delete_reminder(int(existing["id"]))


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
# ALERT-ROUTING (#33): the local Discord poster (_discord_webhook + _notify) was REMOVED — the
# reminders-notify scan now delegates delivery to the shared alerts engine (modules.alerts.notify),
# de-duplicating the per-module webhook code. The ENGINE below (cadence/cap/roll/tick/_should_fire)
# is unchanged; only the delivery channel moved. See notify_scan() for the call-site.


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


def _maybe_escalate_overdue(row, now_iso_str: str) -> None:
    """#51: the overdue-past-cap → HIGH/MAIL escalation (fires EXACTLY ONCE per reminder).

    Fires when ALL hold for an un-done reminder _should_fire already declined (at cap):
      - notified_count >= cap (the Discord cadence is exhausted), AND
      - OVERDUE: due_at <= now (the scan's mockable now_iso_str — consistent with _should_fire's own
        due-check; the reader's _is_overdue is the real-clock variant, not used here so the test's
        injected clock governs), AND
      - NOT already escalated (mail_escalated == 0) → the spam-proof guard.
    → ``alerts.notify("high", …)`` ONCE → ``store.set_mail_escalated(id)`` so it NEVER re-fires.
    Fail-soft: any error is swallowed by notify_scan's per-reminder try/except (the scan continues)."""
    count = int(row["notified_count"])
    cap = row["max_times"] if row["max_times"] is not None else _DEFAULT_MAX_TIMES
    keys = row.keys()
    already = bool(row["mail_escalated"]) if "mail_escalated" in keys else False  # pre-migration tolerant
    if count >= cap and row["due_at"] <= now_iso_str and not already:
        from modules.alerts import notify as _alert_notify
        _alert_notify("high", f"🔴 Overdue: {row['title']}",
                      f"un-done past {cap} reminders — due {row['due_at']}")  # fail-soft inside
        store.set_mail_escalated(int(row["id"]))


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
                # #51 ADDITIVE branch (the ENGINE change, decide-and-log): _should_fire returns
                # False at cap (count >= cap → Discord stops). For an un-done reminder that is now
                # OVERDUE AND past-cap AND not-yet-escalated → escalate ONCE to a HIGH-severity MAIL
                # alert (alert creds live post-#50), then set mail_escalated so it NEVER re-fires
                # (spam-proof — fires EXACTLY ONCE per reminder, not a recurring nag). The normal
                # pre-cap Discord path above is UNTOUCHED (byte-identical to #29).
                _maybe_escalate_overdue(row, now_iso_str)
                continue
            # ALERT-ROUTING (#33) + TRACING-UX T3 (#111) — route the fire by the reminder's CHANNEL:
            #   in_app (default) → NO external send. The reminder ROW already exists + shows in the
            #     /reminders UI (the in-app surface) — calling alerts here would be a DOUBLE-fire.
            #     in_app fires still advance the counter/roll below (the engine is unchanged) — they
            #     just don't ring an external channel. (Byte-identical to "the reminder is overdue in
            #     the UI", which is #29's in-app behavior.)
            #   email / discord → route through the shared alerts engine's CHANNEL override (the #111
            #     additive `channels=` param) — EXACTLY that channel, severity-independent, fail-soft
            #     + configured-checked (no creds → honest skip, never a crash). The ENGINE
            #     (cadence/cap/roll/_should_fire) is UNCHANGED — only WHERE a fire goes.
            channel = row["channel"] if "channel" in row.keys() else "in_app"  # pre-migration tolerant
            if channel in ("email", "discord"):
                from modules.alerts import notify as _alert_notify
                _alert_notify("normal", f"⏰ Reminder: {row['title']}", f"due {row['due_at']}",
                              channels=[channel])  # fail-soft inside; routes to EXACTLY this channel
            # in_app → no alerts call (the row/UI is the surface; no double-fire)
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
