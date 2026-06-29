# End Sprint TRACING-UX3A — backfill timeless activities + bỏ bucket "Chưa đặt giờ"

Board task: #171. Reactive follow-up to #170. User flagged the "Chưa đặt giờ" bucket as contradictory; CHỐT: backfill old timeless activities to a default time → all on the rail → bucket vanishes.

## What shipped
Backfilled all 7 timeless activities to a scheduled time (via the canonical update path) → the timeline rail now shows every activity → the bucket auto-hides (it was already `{anytime.length > 0 && ...}`). A re-runnable helper + 6 tests. FE: 0 change.

### Changes implemented (4-step verified on disk + live curl)
- **BE — `backfill_timeless_time(default_time="08:00")` helper** (service.py +33) — re-runnable maintenance fn (wiki `supersede_pending` pattern, NOT a startup hook). Per-activity rule:
  - time=null + remindAt set → `time = remindAt` (so "Viết nhật ký" → 07:00, no visible jump — the FE rail already showed it at 07:00 via the `a.time || a.remindAt` fallback).
  - time=null + no remindAt → `time = default_time` ("08:00").
  - time already set → SKIP (idempotent).
  - SCOPED: sets ONLY `time`; reminder/name/goal/streak/logs untouched. Returns `{beforeTimeless, afterTimeless, set:{id:time}, touched, defaultTime}` (the #72 before/after audit discipline).
- **BE — data mutation on the live runtime store** — ran the backfill: before=7 timeless, after=0. viet→07:00 (= its remindAt), the 6 others→08:00. (Runtime SQLite is gitignored → the data change is NOT in the commit; the helper + tests are.)
- **BE — test_tracing_backfill_time.py** (new, 6 tests): default-for-no-remindAt + counts, remindAt-wins-no-jump, idempotent (re-run touches 0), reminder-preserved, name/goal/logs-preserved, archived-skipped.
- **FE — NONE.** The #170 bucket render is `{anytime.length > 0 && ...}` (page.tsx L662) → after backfill (anytime=[]) it auto-hides. Honest: an agent posting a timeless activity later makes the bucket honestly reappear.

### Verification (pass/fail)
- Live curl GET /tracing (Rule#0, architect-verified): total 7, **timeless 0**; viet time=07:00 remindAt=07:00; tap-the-duc/doc-sach/ngu/thien/di-bo/hoc all time=08:00; all streak=0 (unchanged). ✅
- pytest test_tracing_backfill_time.py: **6 passed** (architect re-ran independently via conda env — not just the report). Backend reported 169 tracing-layer pytest pass. ✅
- team-lead Chrome-gate PASS: bucket gone · all 7 on the rail (07:00 viet + 08:00 ×6) · viet=07:00 not 08:00 · streak/log intact, remindAt kept · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ N/A — uses the existing PUT/update_activity path; no new endpoint/schema.
- **Gate 2 (Function)**: ✅ 6 unit tests assert observable behavior (incl. the no-jump remindAt branch + idempotency + preservation); 0 errors; scoped 1-field write.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect curl-verified the live data + read the helper + re-ran the tests; team-lead Chrome-gate pass; commit format match.

## Risks / potential errors identified
- Data mutation on the runtime store is NOT git-tracked (gitignored SQLite) — it's applied live, not reproducible from the commit. The helper IS committed + tested, so re-running it on a fresh DB reproduces the result. Acceptable (single-user runtime data).
- The helper's remindAt-branch is built INTO the function (not a separate one-off PUT) → a future re-run on new timeless data correctly preserves any remindAt-having activity. Verified in test_backfill_uses_remindAt_when_present_no_jump.

## Assumptions (user-review)
- **Backfill: time=null + remindAt → time=remindAt; else → 08:00** — *why*: an activity with a reminder already shows at its remindAt on the rail (FE fallback); using remindAt as the time avoids a confusing visible jump (Viết nhật ký stays 07:00); a no-reminder activity gets the sensible 08:00 default (user edits later) — *how to change*: re-run `backfill_timeless_time(default_time=...)` or edit each activity's time on /tracing.
- **Bucket auto-hides when empty; honest reappear for future agent-posted timeless** — *why*: don't fabricate a time for unknown future data; the bucket is honest about real timeless rows — *how to change*: none needed (it's data-driven).

## Commit
`fix(sprint-tracing-ux3a): backfill timeless activities (viet→07:00 via remindAt, 6→08:00) + bỏ bucket Chưa-đặt-giờ`
Explicit-paths only (helper + test + sprint docs; NOT template/Life Command/* or docs or projects-tests or the gitignored runtime DB).
