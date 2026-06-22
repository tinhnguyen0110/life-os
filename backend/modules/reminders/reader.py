"""modules/reminders/reader.py — row→model mapping, FAIL-OPEN (REMINDERS-1, #27).

Maps raw ``reminders`` rows to the Reminder model. Fail-open: a malformed row is SKIPPED with a
warning, never crashes the list (raw-data-first — one bad row must not 500 the agenda). Read-only.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Literal, cast

from .schema import Channel, Reminder, now_iso

_CHANNELS: frozenset[str] = frozenset({"in_app", "email", "discord"})

logger = logging.getLogger("life-os.reminders.reader")


def _is_overdue(due_at: str | None, done_at: str | None) -> bool:
    """SEMANTIC 2 (#29): overdue = un-done AND past-due, INDEPENDENT of notified_count. due_at is
    UTC-normalized (#1A) so a string compare vs now-UTC-ISO is a correct time comparison."""
    if done_at is not None or not due_at:
        return False
    return due_at < now_iso()  # due_at is non-None+non-empty here (narrowed above)


def row_to_reminder(row: sqlite3.Row) -> Reminder:
    """Map one row to a Reminder + derive ``overdue`` (#29). Raises (caught by the list mapper)
    on a malformed row. ``last_notified`` tolerates a pre-migration row missing the column."""
    keys = row.keys()
    last_notified = row["last_notified"] if "last_notified" in keys else None
    # TRACING-REMINDERS (#75): tolerate a pre-migration row missing source/activity_id. Coerce
    # source to the known set (an unexpected value defensively reads as "manual").
    raw_source = row["source"] if "source" in keys else "manual"
    source: Literal["manual", "tracing"] = "tracing" if raw_source == "tracing" else "manual"
    activity_id = row["activity_id"] if "activity_id" in keys else None
    # TRACING-UX T3 (#111): tolerate a pre-migration row missing channel → default in_app; coerce an
    # unexpected value defensively to in_app (the safe no-external-send default).
    raw_channel = row["channel"] if "channel" in keys else "in_app"
    channel: Channel = cast(Channel, raw_channel) if raw_channel in _CHANNELS else "in_app"
    return Reminder(
        id=int(row["id"]),
        title=row["title"],
        note=row["note"],
        due_at=row["due_at"],
        repeat=row["repeat"],
        re_notify_every=row["re_notify_every"],
        max_times=row["max_times"],
        notified_count=int(row["notified_count"]),
        last_notified=last_notified,
        done_at=row["done_at"],
        created=row["created"],
        overdue=_is_overdue(row["due_at"], row["done_at"]),
        source=source,
        activity_id=activity_id,
        channel=channel,
    )


def map_rows(rows: list[sqlite3.Row]) -> tuple[list[Reminder], list[str]]:
    """Map rows → (reminders, warnings). A row that fails to map is SKIPPED + a warning recorded
    (fail-open) — never raises, so a single malformed row can't crash the whole list."""
    out: list[Reminder] = []
    warnings: list[str] = []
    for row in rows:
        try:
            out.append(row_to_reminder(row))
        except Exception as exc:  # noqa: BLE001 — fail-open: skip the bad row, keep the rest
            rid = None
            try:
                rid = row["id"]
            except Exception:  # noqa: BLE001
                pass
            logger.warning("reminders: skipping malformed row id=%s: %s", rid, exc)
            warnings.append(f"skipped malformed reminder id={rid} ({exc})")
    return out, warnings
