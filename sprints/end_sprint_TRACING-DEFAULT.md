# End Sprint TRACING-DEFAULT — Daily Tracing default = only 3 check-ins

Board task: #180. User's original intent: /tracing defaults to ONLY the 3 check-ins; drop the 7 old habits everywhere.

## What shipped
The 7 legacy habit activities are archived (recoverable); ALL THREE template surfaces now default to the 3 check-ins (the single-prefill seeds, the multi-item template-SET, and the live runtime). Pure BE, FE untouched, #168-179 intact.

### Changes implemented (4-step verified on disk + curl all 3 surfaces + independent pytest)
- **T1 — archive the 7 legacy habits** — `archive_legacy_habits()` re-runnable helper (the #171 pattern): SOFT-deletes (recoverable) exactly the 7 `_LEGACY_HABIT_IDS` (tap-the-duc/doc-sach/ngu/thien/di-bo/hoc/viet); SCOPED + IDEMPOTENT (absent/already-archived → skip; re-run archives 0); KEEPS the 3 check-ins; archive drops the linked reminder (viet). Run live → 10→3 active. All 7 were streak=0/no-log → nothing lost; restorable.
- **T2 — `_SEED_TEMPLATES` → 3 check-ins** — the single-prefill seed list = 🌅 Check-in sáng / ☀️ Check-in trưa / 🌙 Báo cáo tối (unit=lần, goal=1). → "+ Từ mẫu" single suggestions = the 3.
- **T3 — `_DEFAULT_TEMPLATE_SET` → "Check-in hàng ngày"** (the multi-item template-SET surface — caught by team-lead's Chrome-gate, a 3rd surface I'd missed): the seed set is now the 3 check-ins (Check-in sáng 07:00 custom T2-T6 / trưa 12:00 custom / Báo cáo tối 21:00 daily, via TemplateMember's #172 custom+remindDays). `reset_template_sets()` run live → the old "Buổi sáng" set replaced. SCOPED to tracing_template_set (the #72 lesson — never touches activities/logs).

### Verification (pass/fail)
- curl all 3 surfaces (Rule#0, architect-verified): activities=3 (checkin-sang/trua/report-toi) · /tracing/templates=3 (the check-ins) · /tracing/template-sets=1 ("Check-in hàng ngày" = Check-in sáng/trưa/Báo cáo tối). NO Uống nước/Tập thể dục/Đọc sách anywhere. ✅
- pytest tracing: 48 passed (architect re-ran; tests updated: archive-legacy + templates→3 + template-set→check-in). Backend reported 292 full, mypy clean. ✅
- **service.py diff is ONLY #180** (team-lead's flagged check): the #171 backfill_timeless_time + #172 remindDays are already committed in HEAD (23f6acb/c0fb74b); the uncommitted diff carries only the archive helper + _SEED_TEMPLATES + _DEFAULT_TEMPLATE_SET — no leftover #171/#172. ✅
- team-lead Chrome-gate FULL PASS (3 surfaces, eyes-on): timeline 3 check-ins · "+ Từ mẫu" → "Check-in hàng ngày · 3 việc" (no old) · console clean. ✅
- 3 active check-ins untouched by the archive (scoped). ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — uses existing endpoints; seed-data + a maintenance helper.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (archive scoped+idempotent+recoverable, _SEED→3, _DEFAULT_SET→check-in, merge intact); mypy clean; 0 errors; archive recoverable; service.py contamination-free.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect curl-verified all 3 surfaces + confirmed no #171/#172 leftover + re-ran pytest; team-lead Chrome-gate pass; commit format match.

## Risks / potential errors identified
- **3-surface enumeration miss (the lesson):** I scoped #180 to 2 surfaces (activities + _SEED_TEMPLATES) and missed the template-SET — team-lead's Chrome-gate caught it (→ T3). Reinforced the memory `kickoff-enumerate-all-surfaces` with this DATA-surface instance: a "change the default X" sprint must grep the old value across ALL seeds + runtime tables (single-prefill seed, multi-item set, runtime). No user-data lost (all recoverable / contents-only).
- The archive is recoverable (soft-delete) — if the user wants a habit back, un-archive. Logged.
- BE labeled the new code comments "#173" (a typo for #180) — cosmetic, code is correct; not worth a re-dispatch.

## Assumptions (user-review)
- **7 legacy habits archived (recoverable), not hard-deleted** — *why*: all streak=0/no-log; soft-delete keeps them restorable — *how to change*: un-archive any id to bring it back.
- **All 3 template surfaces = the 3 check-ins** (single seeds + the "Check-in hàng ngày" set) — *why*: user's "default = only the check-ins" intent across every surface — *how to change*: edit _SEED_TEMPLATES / _DEFAULT_TEMPLATE_SET in service.py.

## Commit
`fix(sprint-tracing-default): default 3 check-in only — archive 7 legacy + SEED templates + default template-set = 3 check-in`
Explicit-paths only (service.py + 3 tracing tests + 2 sprint docs; NO runtime *.db; NOT template/Life Command/* or docs or projects-tests).
