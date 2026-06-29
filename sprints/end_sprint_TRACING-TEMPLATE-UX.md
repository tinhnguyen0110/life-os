# End Sprint TRACING-TEMPLATE-UX — import=replace + idempotent-by-id (slug converge) + list-render

Board task: #181. Follow-up #180. User asks on "+ Từ mẫu": import should REPLACE (not add); the template should render as a per-member list.

## What shipped
Import a template-set → the board becomes EXACTLY that template (atomic replace), idempotent by a stable slug id (re-import reuses ids, no suffix/trash growth, seed + import converge on ONE id-scheme); the modal renders each member as a timeline-like list row. Mostly BE + FE modal; FE untouched elsewhere.

### Changes implemented (4-step verified on disk + curl + independent pytest)
- **T1 — import = ATOMIC replace** — import_template_set: snapshot old active ids → create/upsert all members FIRST → THEN archive the old non-member ids (only if ≥1 landed). Create-first → never empties the board on a partial failure. Returns (memberViews, skipped, archivedCount).
- **T3 — idempotent-by-id** — each member's id = `_slug(content)` (STABLE, NOT slug+suffix): ARCHIVED → un-archive+update (the #130 pattern, logs preserved); ACTIVE → update; absent → create. Re-import same set → old_ids ⊆ member_ids → archives 0 → no /trash growth, same ids. (Fixes the suffix-id + trash-bloat debt team-lead's gate found.)
- **T3b — slug convergence (option c)** — `_SEED_TEMPLATES` + `seed_checkin_activities` ids changed to the slugs (check-in-sang/check-in-trua/bao-cao-toi = `_slug(name)`), so the SEED path and the IMPORT path produce the SAME id (one id-scheme). Live board migrated to the slug ids via a scoped create+archive (NOT an import-loop). Internal cleanup — user sees only name/time, no UX change.
- **T2 — modal list-render (FE)** — TemplateSetsModal LIST view renders each set's members as per-member rows (time · content · remind-chip) like the /tracing timeline, + an import toast (created/archived counts); no confirm (replace is recoverable + fast).

### Verification (pass/fail)
- curl /tracing (Rule#0): board = check-in-sang (custom [0-4]) / check-in-trua (custom [0-4]) / bao-cao-toi (daily) — 3 slug-ids, reminders intact. ✅
- pytest tracing: 61 passed (architect re-ran; incl. import-replace, atomic-on-failure, idempotent-re-import-same-ids-no-trash, seed-id===import-id convergence). Backend reported 296. ✅
- FE tsc 0; vitest tracing 72/72. ✅
- **service.py is #181-ONLY** (team-lead's flagged check): #180 markers (archive_legacy_habits/_LEGACY) committed in HEAD (039fdb7); the uncommitted diff is purely #181 (import_template_set + slug ids). No #180 leftover. ✅
- team-lead Chrome-gate PASS (T1+T2+T3+T3b): import=replace (tmp gone, noDouble) · mẫu=list (eyes-on) · idempotent (2× import → same id, archived 0) · slug-converged board · console clean. ✅

### 3 Quality Gates
- **Gate 1 (API)**: ✅ import endpoint response extended (additive archivedCount); no auth/manual-core change.
- **Gate 2 (Function)**: ✅ tests assert observable behavior (replace, atomic-on-failure, idempotent-no-trash, seed===import convergence); mypy/tsc clean; 0 errors; archive recoverable + scoped.
- **Gate 3 (Sprint)**: ✅ this report w/ verified counts; architect read the import logic + slug ids on disk + confirmed no #180 leftover + curl-verified the board + re-ran pytest; team-lead Chrome-gate pass; commit format match.

## Risks / potential errors identified
- **Verification incident (team-lead, self-recovered — logged):** re-gating the idempotent-import via the import-API on the LIVE board emptied the board momentarily (import=replace has NO sandbox — importing a throwaway set still REPLACES the real board; then deleting the throwaway item left it empty). team-lead un-archived the 3 check-ins → recovered (the recoverable archive saved it). **Lesson:** import-replace cannot be safely verified via the live API (no board-sandbox) — verify it at the pytest/DB layer. Reinforces `verify-mutating-op-on-throwaway-not-live-board` with the import-replace-no-sandbox variant. No code impact; board is clean + correct now.
- BE comments label the work "#173" (a typo for #181) — cosmetic, code correct, not worth a re-dispatch.

## Assumptions (user-review)
- **Import = atomic replace** (board becomes exactly the template; create-first never-empty; old archived recoverable) — *how to change*: the import logic in service.py.
- **Idempotent by slug id; seed + import converge on one id-scheme** (check-in-sang/check-in-trua/bao-cao-toi = _slug(name)) — *why*: re-import reuses ids → no suffix/trash growth; import (user path) is the canonical reference — *how to change*: n/a (it's the cleanup).
- **No confirm on import** (recoverable + fast, toast shows counts) — *how to change*: add a confirm in TemplateSetsModal if the user later wants one.

## Commit
`feat(sprint-tracing-template-ux): import=replace + idempotent-by-id (slug converge) + mẫu list-render`
Explicit-paths only (service.py + router.py + 4 tracing tests + TemplateSetsModal + tracing page + modal test + types + 2 sprint docs; NOT wiki/page.tsx [that's #182], NOT template/Life Command/* or docs or projects-tests or runtime db).
