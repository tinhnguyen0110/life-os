# Sprint TRACING-REMINDERS — link a habit to a reminder (Cairn #75)

> Kickoff'd 2026-06-21 by architect (§3.3a). #75 = tracing×reminders integration: a tracing activity can NUDGE (set a daily reminder "do your run"), and a reminder shows its SOURCE (manual vs from-a-habit). admin-lead Rule#0-verified the origin (tracing has no remind field, reminders has no source field; the notify engine #29 + APScheduler + Discord already EXIST — the gap is only the NƠI-NỐI/connection point). Schema FROZEN below → FE can build #75-FE ∥ against it. backend BUILDS #75-BE after #63-P2 (1-BE-epic-at-a-time); architect commits (§3).

## Kickoff — 2026-06-21
### Origin verified (Rule#0, on disk)
- tracing `ActivityInput`/`Activity` — NO remind field (confirmed). reminders `ReminderInput`/`Reminder` — NO source/activity_id field (confirmed). The reminders notify routine (#29), APScheduler, Discord, overdue-derivation, re_notify_every — ALL EXIST. So #75 = wire the two, not build an engine.
- 3 user paths (admin-lead's framing): (A) from an activity → create a reminder w/ remind_at + repeat; (B) manual reminder unchanged; (C) a "+nhắc" at /tracing → same as A.

### Decision (decide-and-log — sync direction)
- **ONE-WAY sync (tracing → reminder)** [team-lead-recommended, ADOPTED]: setting/changing an activity's remind creates/updates its linked reminder. Deleting/ticking the source=tracing reminder at /reminders does NOT touch the activity's remind config (simpler; avoids surprising the user's activity setup). The activity's remind_at is the source-of-truth; the reminder is the materialized nudge. **How to change:** make the /reminders delete-of-a-tracing-reminder also clear activity.remind_at (2-way) — but ONE-WAY is the locked default.
- **edit/delete sync (one-way):** activity remind_at changed → upsert the linked reminder (find by activity_id + source=tracing); activity remind cleared → delete/done the linked reminder; activity archived → delete/done its linked reminder. (This is the tracing→reminder direction only.)

## FROZEN schema additions (additive — mirror for FE/tester)
**tracing/schema.py** — `ActivityInput` + `ActivityUpdate` + `Activity` + `ActivityView` gain:
- `remind_at: str | None = None` — "HH:MM" VN local time-of-day to nudge (None = no reminder). (time-of-day, not a full datetime — the reminder's due_at is computed daily from this + today-VN.) Validated HH:MM if set.
- `remind_repeat: Literal["daily","weekdays","off"] = "off"` — the nudge cadence (off = no reminder even if remind_at set; or treat remind_at None as off — pick: **remind_at None ⇒ no reminder**, remind_repeat governs daily-vs-weekdays when on).

**reminders/schema.py** — `Reminder` (+ internally on create) gains:
- `source: Literal["manual","tracing"] = "manual"` — where the reminder came from.
- `activity_id: str | None = None` — the linked tracing activity id when source="tracing" (else None).
(`ReminderInput` stays manual-facing: source defaults "manual"; the tracing link is set by the SERVICE when tracing creates a reminder, NOT by a user payload — so a manual POST /reminders can't forge source=tracing.)

> **WIRE FIELD NAMES = snake_case `source` + `activity_id`** (team-lead 2026-06-21). The reminders module is PURE snake on the wire (due_at/re_notify_every/done_at, NO alias/populate_by_name) → a new field matches that convention; camel `activityId` would make the module's payload mixed-case. The FE MIRRORS the snake names (`source` + `activity_id`) — my earlier "FE serializes camelCase" note was a slip for THIS module (reminders is snake, unlike the camel models). #75-BE already serializes snake (correct as-built); FE switched activityId→activity_id. tracing's remind_at/remind_repeat stay snake too (tracing is snake on the wire). No camel for #75.

## Logic/Algorithm (the wire — reuse the existing engine)
1. **tracing service:** on create/update activity with remind_at set + remind_repeat≠off → upsert a reminder (source="tracing", activity_id=<id>, title="<emoji> <name>", due_at = today-VN @ remind_at → UTC, repeat = daily/weekly per remind_repeat). Find-existing by (activity_id, source=tracing) to update not duplicate. remind cleared/activity archived → delete-or-done that reminder.
2. **reminders:** source/activity_id stored + surfaced (the FE source-badge). The notify engine (#29) fires it normally — NO engine change (a tracing reminder is just a reminder with a source tag). The daily due_at roll-forward (repeat=daily) already handled by the existing repeat logic.
3. **MCP/REST:** the new fields flow through the existing reader/overview (additive). reminders_list + the brief show source. tracing overview shows remind_at on the ActivityView.

## Phases
- **#75-BE** (backend, AFTER #63-P2): the schema additions + the tracing→reminder upsert/sync in tracing service + the reminders source/activity_id storage + tests. (The engine #29 is reused — no new scheduler.)
- **#75-FE** (frontend, ∥ NOW against the frozen schema): /tracing remind-toggle ("+nhắc" button + an HH:MM + daily/weekdays picker on the activity card/form) + /reminders source-badge (a "from habit" chip when source=tracing). Mirrors the frozen fields; renders honest (no badge for manual). Render-only — BE owns the sync.

## HARD GATE (BE)
- set activity remind_at=07:00 daily → a reminder appears (source=tracing, activity_id=<id>, due today-VN 07:00-UTC, repeat=daily). update remind_at → the SAME reminder updates (no dup). clear remind_at / archive → the linked reminder gone. a manual POST /reminders can't set source=tracing (forge-guard). pytest inclusive 0-failed.

## Baseline
pytest INCLUSIVE (post-#63 ~2039+). FE vitest (post-#63-P3 894+). 0-failed/0-errors.

## Test ownership split
backend (#75-BE): the upsert-not-dup, clear/archive→delete, forge-guard, the schema additions (one-way sync). frontend (#75-FE): the /tracing remind picker + /reminders source-badge render + honest-no-badge-for-manual. tester: live set-remind→reminder-appears→clear→gone.

## Assumptions (user-review)
- **#75 = ONE-WAY sync** (tracing→reminder; the activity is source-of-truth, deleting the reminder doesn't touch the activity). remind_at = HH:MM VN; remind_repeat daily/weekdays/off; remind_at None ⇒ no reminder. reminder gains source(manual|tracing)+activity_id; manual POST can't forge source=tracing. Reuses the #29 notify engine (no new scheduler). **How to change:** sync direction / the remind fields / the cadence.

## Notes
- #75 (tracing×reminders). Kickoff done; schema FROZEN → FE builds #75-FE ∥ NOW (mirror the frozen fields). backend builds #75-BE AFTER #63-P2 (1-BE-epic-at-a-time). architect commits (§3). The notify engine (#29) is REUSED — #75 is the wire, not a new engine. Disjoint from #63 (tracing/reminders vs dev_activity) → ∥-safe, serialized commits. Sequencing: #63-P2 (last #63) → #75-BE → ... ; #75-FE ∥ now.
