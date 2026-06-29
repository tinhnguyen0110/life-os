# Sprint TRACING-DEFAULT — Daily Tracing default = only 3 check-ins

Board task: #180. User's original intent: Daily Tracing should default to ONLY 3 activities (Check-in sáng/trưa + Báo cáo tối); drop the 7 old; the "+ Từ mẫu" template list too.

## Kickoff — 2026-06-29

### State (curl-verified — Rule#0)
- 10 activities: 7 old (tap-the-duc/doc-sach/ngu/thien/di-bo/hoc/viet, repeat=off) + 3 check-in (checkin-sang/trua custom, report-toi daily). **ALL 7 old are streak=0, todayDone=False, no log** → safe to archive (recoverable soft-delete, nothing lost).
- SEED template `_SEED_TEMPLATES` (service.py L391) = 8 old entries (uong-nuoc + the 7) → "+ Từ mẫu" suggests the old habits.
- `/tracing/templates` = all 8 `source=seed`, **ZERO user overrides** → changing the seed list has NO orphan-override risk (nothing keyed to the old seed ids; team-lead's "mồ-côi" concern is moot here).

### Decisions (architect)
- **T1 — archive the 7 old activities (runtime, scoped, recoverable).** `archive_activity(id)` (soft-delete) for exactly the 7 old ids; KEEP the 3 check-ins. Count before=10/after=3; idempotent (already-archived → skip). Safe: all 7 are streak=0/no-log; viet's reminder gets removed by archive (correct — it's being retired). A re-runnable helper (like #171 backfill) + run live.
- **T2 — replace `_SEED_TEMPLATES` with the 3 check-ins.** New seed list = checkin-sang "Check-in sáng" 🌅 · checkin-trua "Check-in trưa" ☀️ · report-toi "Báo cáo tối" 🌙. unit="lần", goal=1.0 (a daily binary check). icon: a sensible key (sun/sun-high/moon or reuse existing). color: distinct. → "+ Từ mẫu" now suggests only these 3. No orphan-override (0 overrides exist); no reset needed.
- KEEP: the template merge logic (SEED ⊕ override) unchanged — only the seed CONTENTS change. The archive is recoverable.

### Defensive
- Archive ONLY the 7 old ids (count after = 3 check-ins remain) — never touch the 3. Recoverable (soft-delete). Idempotent.
- Seed change is contents-only (the merge code is untouched) → no orphan templates (0 overrides), no merge break.
- Runtime DB write (gitignored) — the helper + the seed code are committed (reproducible); the archive is a live data mutation.

### BE/FE split
- **BE only.** service.py (`_SEED_TEMPLATES` + an archive helper) + run the archive live. FE untouched (the timeline + "+ Từ mẫu" just render fewer items). BE.

### Final task list
- **T1 (BE):** archive the 7 old activities (scoped helper, count before/after, idempotent, run live).
- **T2 (BE):** replace `_SEED_TEMPLATES` with the 3 check-ins (VN names + emoji + unit=lần goal=1). Test: list_templates returns the 3, not the 8; merge still works.

### Dispatch plan
- backend ← T1+T2 (same file/theme). tester: curl /tracing = 3 activities + /tracing/templates = 3. team-lead Chrome-gate: /tracing only 3 check-in on timeline · "+ Từ mẫu" 3 · old gone · console clean.

## Assumptions (user-review) — filled in end_sprint
