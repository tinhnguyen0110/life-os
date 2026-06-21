# end_sprint_51-OVERDUE-MAIL — overdue-past-cap reminder → high/mail escalation, exactly-once (Cairn #51)

> Result. User-greenlit ("process"): an un-done reminder that is OVERDUE AND past its Discord cap escalates to a HIGH-severity MAIL alert — EXACTLY ONCE per reminder (a `mail_escalated` flag, spam-proof), never a recurring nag. The engine change the #29 `notify_scan` comment already flagged as a decide-and-log. The existing #29 engine stays BYTE-IDENTICAL (the new branch is additive, `_should_fire` unmodified). Commit `<hash>` `feat(sprint-51-overdue-mail): overdue-past-cap → high/mail escalation, exactly-once (#51)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT exactly-once + guard-load-bearing teeth + the 14-#29-byte-identical confirm). Cairn #51 (the engine-change task #33-F2 forbade as delivery-only). Alert creds live post-#50 → it fires real.

## What shipped (3 reminders files)
| File | Change |
|---|---|
| `reminders/service.py` | NEW `_maybe_escalate_overdue(row, now_iso_str)` — fires `alerts.notify("high", …)` ONCE when an un-done reminder is past-cap (notified_count >= max_times or _DEFAULT_MAX_TIMES) AND overdue (due_at <= now) AND NOT mail_escalated → then `store.set_mail_escalated(id)` so it NEVER re-fires. Called from `notify_scan` INSIDE the `if not _should_fire(...): _maybe_escalate_overdue(...); continue` block — i.e. ONLY on the at-cap case `_should_fire` already declines. **`_should_fire` is UNMODIFIED; the pre-cap normal/Discord path is byte-identical to #29.** Fail-soft (the per-reminder try/except). |
| `reminders/store.py` | NEW `mail_escalated INTEGER NOT NULL DEFAULT 0` column + the idempotent migration (`if "mail_escalated" not in cols: ALTER TABLE reminders ADD COLUMN ... DEFAULT 0` — the #75 pattern; existing reminders → 0). NEW `set_mail_escalated(id)` — SCOPED `UPDATE reminders SET mail_escalated = 1 WHERE id = ?` (single id, params bound — #72). `roll_repeat` also resets `mail_escalated = 0` (a fresh period can re-escalate). |
| `tests/test_reminders_notify.py` (+6) | test_51_overdue_past_cap_escalates_high_mail_exactly_once · _done_reminder_never_escalates · _escalation_guard_is_load_bearing · _not_overdue_past_cap_does_not_escalate · _roll_repeat_resets_escalation. (mockable clock — no real-time waits, no real alert fired.) |

## Design (LOCKED — additive, exactly-once, byte-identical #29)
- **🔴 the #29 engine stays BYTE-IDENTICAL:** the escalation triggers on the case `_should_fire` ALREADY returns False for (count >= cap) → a SEPARATE branch in notify_scan, NOT a change to `_should_fire`'s returns. The 14 #29 mockable-clock tests stay green by construction (the notify file = 20 = 14 #29 + 6 new). The pre-cap → normal/Discord path is untouched.
- **fire-EXACTLY-ONCE (DECIDED + team-lead-approved decide-and-log):** "overdue-past-cap → high/mail fires EXACTLY ONCE per reminder (mail_escalated flag), not recurring; recurring-nag = a follow-up only if the user asks." Set on the first escalation → never re-fires. NOT an every-1-min loop, NOT a daily nag. (team-lead will surface the once-not-recurring inbox behavior to the user.)
- **scope (sound — matches the spec):** count >= cap means a RE-NOTIFYING reminder that exhausted its cadence (a never-re-notified one-shot at count=1 < cap=3 never escalates). Only reminders that ran out of Discord cadence + are still overdue escalate.
- **#72-scoped + #75-migration:** set_mail_escalated is WHERE id=? (single, no blanket); the column ALTER is idempotent (existing reminders read fine).
- **roll-reset:** a repeat reminder rolling forward resets mail_escalated (a fresh overdue period can re-escalate once).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** `_maybe_escalate_overdue` additive (called inside the _should_fire-False block, before continue); `_should_fire` UNMODIFIED (diff shows no change to its returns) ✅; set_mail_escalated scoped WHERE id=? ✅; the migration idempotent + roll-reset ✅.
- **the 14 #29 tests BYTE-IDENTICAL GREEN:** the notify file = 20 tests, all pass (14 #29 unchanged + 6 new #51). The additive-by-construction safety holds. ✅
- **INDEPENDENT guard-teeth (the spam-proof guard is load-bearing):** I BROKE `set_mail_escalated` (made it never set the flag) → `test_51_overdue_past_cap_escalates_high_mail_exactly_once` went RED (the 2nd scan re-fires = spam without the guard); restored → green. → the mail_escalated guard genuinely prevents spam (the teeth have teeth). ✅
- **backend's 6 #51 tests** (exactly-once / guard-load-bearing / done-never / not-overdue / roll-reset) all pass — independently re-run by name. ✅
- **honest discipline:** the verification used isolated fixtures + mockable clock + a mocked alerts.notify — NO real mail fired on the live store (no pollution). ✅
- **Suite:** DEFAULT (`-m 'not slow'` deterministic) = **2199 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2193→2199 = +6 #51 tests); never staged backend/data/.

## 3 Gates
- **Gate 1 (engine):** the escalation additive (the #29 engine byte-identical); fail-soft; alerts.notify("high") fires real (creds live post-#50). ✅
- **Gate 2 (Function):** exactly-once (proven across 2 scans) + the guard-load-bearing teeth (revert→RED, independently re-run) + the 14-#29-green + done/not-overdue/roll-reset edges; #72-scoped SQL; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent teeth + 14-#29-confirm; staged set EXACTLY the 3 reminders files + end doc (NO FE-#94/wiki/data/.env); commit format. ✅

## Assumptions (user-review)
- **overdue-past-cap → high/mail fires EXACTLY ONCE per reminder (mail_escalated flag), not recurring; recurring-nag = a follow-up only if the user asks.** (team-lead-approved decide-and-log; team-lead surfaces it to the user.) **How to change:** add a re-fire cadence (NOT recommended — spam).
- **only RE-NOTIFYING reminders that exhausted cadence + are overdue escalate** (a never-re-notified one-shot doesn't reach cap). **How to change:** the cap/escalation predicate in _maybe_escalate_overdue.
- **a repeat reminder rolling forward resets mail_escalated** (a fresh period can re-escalate once). **How to change:** roll_repeat.

## Notes
- Cairn #51 (user-greenlit "process"). The ENGINE-CHANGE the #33-F2 dispatch forbade as delivery-only + the #29 notify_scan comment flagged as a decide-and-log — now done, additively (the #29 engine byte-identical). backend-w3 built; architect committed (§3 sole-committer). Committed from an intermixed tree (FE-#94 in flight on frontend/) — BE-only surgical stage. Alert creds live post-#50 → a real missed-reminder mails the user ONCE. The exactly-once guard (revert→RED proven) is the load-bearing spam-proof. Next: FE-#94 (trash/restore UI, in flight) → the wiki user-pain batch completes.
