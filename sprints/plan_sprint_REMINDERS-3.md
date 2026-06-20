# Sprint REMINDERS-3 — reminders notify engine (Cairn #29, the báo-thức payoff)

> Created 2026-06-21 by architect. LANE A (priority). DESIGN to team-lead BEFORE dispatch (a NEW scheduler routine + a notify cadence = a BUSINESS RULE — decide-and-log). User CHỐT'd the model (#29 task). Reminders are currently INERT (create/list/tick work, nothing FIRES) — #29 makes "the alarm actually fire."

## The model (user-CHỐT'd, on the #29 task)
- DEFAULT: due → Discord notify ONCE (the existing webhook pattern).
- USER-SET: `repeat` once|daily|weekly · `re_notify_every` X minutes (while UN-ticked) · `max_times` N (default 3).
- Un-ticked = not done → re-notify per cadence up to max-N → then STOP re-notifying but mark RED/overdue in-app (no infinite spam).
- Tick → notifications STOP. Discord = a ONE-WAY speaker (NOT 2-way).
- Scheduler: the existing life-os APScheduler/routine.

## Two design points I had to resolve (live-grounded)
1. **NO `last_notified` field exists** — the #27 schema has `notified_count` but NOT a `last_notified` timestamp. The re-notify-every-X cadence NEEDS it (to know when X elapsed + avoid double-firing within a poll window). → **#29 ADDS `last_notified` (ISO|None) to the reminders table** (additive, no break; default None).
2. **No in-app notify helper** — `.claude/process/notify.py` reads the webhook from `.env` key `discord=` (urllib, fail-soft, exit-0 if no webhook). → #29's in-app poster MIRRORS this: read `.env discord=` (or a settings/env webhook), fail-SOFT (a webhook error must NOT crash the routine).

## The engine (DECIDED — decide-and-log; team-lead sanity-check)
**A new `reminders-notify` routine** (APScheduler, registered via reminders MODULE.routines):
- **Cadence: interval, every 1 minute** (alarm granularity — a reminder due at 9:00 should fire ~9:00, not up to an hour late; 1-min poll is cheap single-user). (Alt: 5-min if 1-min is too chatty — lean 1-min for alarm precision; decide-and-log.)
- **Each tick (the work fn), scan all UN-DONE reminders (done_at IS NULL) and for each decide FIRE / SKIP:**
  - **First fire (default):** `due_at <= now AND notified_count == 0` → FIRE (Discord) → set notified_count=1, last_notified=now.
  - **Re-notify:** `notified_count >= 1 AND re_notify_every IS NOT NULL AND notified_count < (max_times or 3) AND (now - last_notified) >= re_notify_every minutes` → FIRE → notified_count+=1, last_notified=now.
  - **Cap reached:** `notified_count >= (max_times or 3)` → STOP re-notifying (the in-app overdue/RED state — surfaced via the reader's derived `overdue` flag, no more Discord).
  - **Repeat (daily/weekly):** on a `repeat` reminder, when it FIRES at/after due (the first fire of this period) → after firing, ROLL due_at forward by 1 day / 1 week + RESET notified_count=0 + last_notified=None (so the next period fires fresh). (Decide-and-log: roll-on-fire vs roll-on-tick — I lean ROLL-ON-FIRE for a recurring alarm: "daily 9am" fires every day regardless of tick; a `once` reminder doesn't roll. Tick on a repeat = done for THIS period; the roll already advanced it. Surface both — this is the subtle bit, flagging for your sanity-check.)
- **Double-fire avoidance:** the `(now - last_notified) >= re_notify_every` guard + `notified_count` gating + the per-poll scan is idempotent (a reminder already-fired-this-window won't re-fire until the cadence elapses). The first-fire guard is `notified_count == 0`.
- **Discord poster:** in-app `_notify(msg)` reading `.env discord=` (mirror notify.py), fail-SOFT (urllib error → log + continue, never crash the routine — the routine's run-record still completes). NEUTRAL message ("⏰ Reminder: <title> (due <due_at>)").
- **fail-soft per reminder:** one reminder's notify failure must NOT break the scan of the others (the fail-closed-write-fail-soft-add-on pattern — the routine's primary status set, per-reminder notify is the soft add-on).

## Derived `overdue` (in-app RED state)
The reader's Reminder view gains a derived `overdue: bool` = `done_at IS NULL AND due_at < now AND notified_count >= (max_times or 3)` (cap reached, still un-ticked) — so the FE (#31) + brief (#30) show RED/overdue without more Discord. (Or simpler: overdue = un-done + past-due; the cap just stops Discord. Decide-and-log the exact overdue predicate.)

## Tasks (when dispatched — after team-lead's design OK)
- **T1 (backend, gating):** add `last_notified` to the table (additive) + the `reminders-notify` routine (the fire/re-notify/cap/repeat-roll engine) + the in-app fail-soft Discord poster + the derived `overdue` + wire into reminders MODULE.routines. Tests.
- **T2 (tester):** the distinguishing cases (below) — live + with a controllable clock/fixture (don't wait real minutes).
- **T3 (architect):** review + commit `feat(sprint-REMINDERS-3)`.

## HARD GATE (distinguishing — the cadence is the risk)
- due + notified_count 0 → FIRES once (notified_count→1, last_notified set); a 2nd poll BEFORE re_notify_every elapses → does NOT re-fire (double-fire avoidance).
- un-ticked + re_notify_every=X + X elapsed + count<max → re-fires (count++); count>=max → STOPS Discord (overdue/RED in-app instead).
- TICK mid-cadence → no more fires.
- repeat=daily → fires each day (the roll-forward); repeat=once → fires once, never rolls.
- webhook FAILS → routine doesn't crash (fail-soft), other reminders still scanned, the run still records.
- NOT-yet-due reminder → not fired.
- pytest green (with a mockable now()/clock so tests don't wait real minutes), mypy clean.

## Baseline
pytest 1763 (post-f50ba34). Keep 0-failed.

## Assumptions (user-review) — LOCKED (team-lead confirmed the engine + the 2 semantics)
- notify routine cadence = 1-min interval (alarm precision). re-notify gated on last_notified + re_notify_every (MINUTES); cap = max_times or 3. Discord = one-way, fail-soft, webhook from `.env discord=` (mirror notify.py). **How to change:** each is a constant/predicate in the notify engine.
- **repeat → ROLL-ON-FIRE + TICK-ENDS-THE-SERIES** (team-lead-confirmed): on fire, roll due_at +1day/+1week + reset count=0/last_notified=None (a "daily 9am" fires every period like a real recurring alarm, regardless of tick); `once` never rolls. TICK (done_at set) ENDS the series — no more fires, any time ("I'm done with this recurring task, stop reminding"). Simple, no ambiguous per-period done state. **How to change:** the roll + the tick-stops-scan in the engine.
- **overdue = un-done AND past-due** (team-lead OVERRODE the cap-gated lean): a reminder is overdue the MOMENT due_at < now AND done_at IS NULL — INDEPENDENT of notified_count. The cap ONLY gates Discord (stop spamming after N); it does NOT define overdue. FE/brief show RED for any un-done past-due; Discord just goes quiet after the cap. **How to change:** the overdue predicate in the reader.

## Notes
- BRING THIS DESIGN TO team-lead before dispatch (new scheduler routine + notify cadence = business rule). The repeat-roll semantics + the overdue predicate are the two I most want sanity-checked.
- LANE A priority; wiki #20-24 runs parallel (LANE B). Discord = one-way speaker, fail-soft (never crash the routine).
