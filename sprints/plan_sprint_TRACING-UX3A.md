# Sprint TRACING-UX3A — backfill timeless activities + bỏ bucket "Chưa đặt giờ"

Board task: #171. Reactive follow-up to #170 (e91d983). User flagged the "Chưa đặt giờ" bucket as contradictory ("đã quy định mọi việc có giờ rồi"). User CHỐT (AskUserQuestion): backfill old timeless activities to a default time (08:00, user edits later) → all on the rail → bucket gone.

## Kickoff — 2026-06-29

### Live data (curl GET /tracing)
- **7 activities, ALL timeless** (time=null) — not 6. The list: tap-the-duc, doc-sach, ngu, thien, di-bo, hoc, viet (Viết nhật ký has remindAt=07:00 but time=null too). All streak=0.
- Backfill target = these 7 (every time=null). "Viết nhật ký" remindAt=07:00 is the REMINDER, untouched; only its `time` field gets 08:00 (consistent — req says backfill the scheduled time, not the reminder).

### Endpoint confirmed (no BE schema change)
- `PUT /tracing/activities/{id}` (router L90) + `ActivityUpdate.time` (schema L120, validates HH:MM) already accept a time. Backfill = pure data mutation via the existing write path. NO new endpoint/schema.

### Decisions (architect)
- **(a) Backfill method = BE run-once script via the real update path.** Backend runs a scoped, repeatable script: for each activity with time=null (or empty), `service.update_activity(id, ActivityUpdate(time="08:00"))` — uses the canonical write path (audited like any update), count before/after, idempotent (re-run skips already-timed). Repeatable for any future timeless data, not ad-hoc curl. Backend owns the store → backend runs it. SCOPED: only sets `time` where null; touches NOTHING else (name/goal/streak/logs/reminder all untouched). "Viết nhật ký" reminder 07:00 stays.
- **(b) Future timeless (MCP-agent) = hide-bucket-when-empty (honest), NO FE code change.** The #170 FE bucket render is ALREADY `{anytime.length > 0 && (...)}` (page.tsx L662) — it hides when empty by design. After backfill (anytime=[]), the bucket auto-disappears. If an agent later posts a timeless activity, the bucket honestly reappears (don't fabricate a time for future unknown data). → This is the correct honest-mirror behavior and needs ZERO FE edit. Agreeing with team-lead's lean: script + hide-when-empty.
- → **FE = no code change.** The bucket vanishes purely from the backfilled data. Verify only.

### BE/FE split
- **BE = backfill script (the only real work).** Run-once, scoped, count before(7 timeless)/after(0 timeless), idempotent, via update_activity. Optionally a small re-runnable helper fn (like wiki's supersede_pending) for auditability + a test. Report the count.
- **FE = NONE (confirm-only).** Bucket auto-hides (already coded). Tester/Chrome-gate confirms the bucket is gone + 7 on the rail at 08:00 + streak/log intact + "Viết nhật ký" reminder still 07:00.

### Final task list
- **T1 (BE):** backfill script — set time="08:00" for every time=null activity via the canonical update path; SCOPED (only `time`); count before/after; idempotent; add a small test if a helper fn is created. Report before/after counts + the 7 ids touched.
- **T2 (verify, tester):** confirm GET /tracing shows 0 timeless + 7 timed @ 08:00; streak/logs unchanged; "Viết nhật ký" remindAt still 07:00; FE bucket gone (auto-hide).

### Tier
Reactive Sprint (A-suffix) — same theme as #170, data-mutation + verify, no new feature. plan + end written together. 3 gates apply.

### Dispatch plan
- backend ← T1 (the backfill). FE = none. tester ← T2 verify. team-lead Chrome-gate (bucket gone, 7 on rail w/ giờ, Viết-nhật-ký 07:00, streak intact, console clean) → commit.

## Assumptions (user-review) — filled in end_sprint
