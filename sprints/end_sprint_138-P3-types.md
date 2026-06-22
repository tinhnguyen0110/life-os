# end_sprint_138-P3-types — split lib/types.ts by domain (barrel, pure move)

> Sprint 138-P3 Task #1 (the TYPES half). User CHỐT: split the 2 lib monoliths by domain so the app can expand + AI agents navigate per-module files. team-lead signed off (boundaries + barrel + 2-commit-strict-serial). This is Commit 1 = types; api (Commit 2) dispatched only AFTER this verifies + team-lead Chrome-OK.

## What shipped
- **lib/types.ts (2336 lines, 215 exports) DELETED** → **lib/types/ (18 domain files + index barrel)**: _common, projects, market, finance, notes, claude, settings, brief, activity, journal, graveyard, wiki, decision, career, reminders, tracing, dev, mcp + index.ts.
- **Barrel** (`lib/types/index.ts`) = `export *` from all 18 domain files → `@/lib/types` resolves through it. ZERO call-site change across all 83 importers (verified: `@/*`→`./*` maps `@/lib/types` → `lib/types/index.ts` automatically once the file `lib/types.ts` is gone).
- **PURE MOVE** — every symbol cut verbatim (FE used a line-span extraction script, no hand-transcription).

## Verify (architect 4-step + independent reproduction — Rule#0, did NOT trust the report)
1. **git diff:** `D lib/types.ts` + 18 new files + barrel. lib/api.ts UNTOUCHED (serial respected).
2. **Read full result + EXPORT-SET completeness (reproduced myself):** `git show 855b337:frontend/lib/types.ts` exports sorted vs the new domain files exports sorted = **215 == 215, ZERO diff both directions** (`comm -23`/`comm -13` empty).
3. **CODE-LINE multiset (body-drift, reproduced myself):** old vs new code-line multiset (comments stripped) IDENTICAL — the only "extra" NEW line is a `/* ... */` header-comment tail (the split banner), zero actual type/body drift. No duplicate exports (`uniq -d` empty).
4. **tsc --noEmit exit 0** — the safety net fired clean: a missed export would be a tsc error at one of the 83 importers; none. ZERO call-site edits (git status shows only lib/types changes + the unrelated separate-lane files excluded).
5. **Live Chrome :3010 (the SWC>tsc gate, architect-run):** /finance (5898 chars, 0 console err) + /wiki (5827 chars, 0 err) + /tracing (10762 chars, 0 err) — all render real content, no blank page, no Next overlay, 0 console errors. The barrel reshuffle compiles clean in SWC.
6. **vitest 1104 passed (FE) — exact baseline, 0 err / 0 unhandled.**

## Deviation accepted (flagged by FE, my call)
- **`Severity` lives in brief.ts, not _common.ts** (the plan's §1 table was *representative*). FE kept it byte-identical under its original Brief banner rather than relocate + fabricate a comment. Re-exported once via the barrel → every importer resolves it unchanged. **Accepted: byte-identical > cosmetic relocation** (honest-mirror — don't fabricate a comment for a cosmetic move). No follow-up needed.

## Out-of-scope found (flagged, EXCLUDED from this commit)
- Working tree also had `app/settings/__tests__/settings.test.tsx` (mockResolvedValueOnce→mockResolvedValue) + `vitest.setup.ts` (comment clarification) modified = the **#141 settings-flake fix**, a SEPARATE lane. EXCLUDED from the types commit (surgical staging — explicit paths only). Owner being confirmed for its own #141 commit; does not block or mix with types.

## Gates
- Gate 2 (Function): pure refactor — NO new/removed tests (count stays 1104); tsc clean; live Chrome + console verified. ✓
- Gate 3 (Sprint): this doc + independently-reproduced completeness proof (export-set + body multiset) + live Chrome 3 routes + count == baseline. ✓

## Assumptions (user-review)
- **Barrel re-export is the zero-call-site safety net.** All 171 lib/* importers use the `@/lib/...` alias (disk-measured: 0 relative `../lib`), so a barrel `index.ts` makes every import resolve unchanged. How to change: nothing to change — this is the standard barrel pattern; future new types go in the right domain file + are auto-re-exported.
- **2-commit strict-serial (types now, api only after types verified + team-lead Chrome-OK).** Isolates blast radius — if anything regressed it's in one half. How to change: api proceeds on team-lead's OK.

## Commit
- Hash: (filled at commit) — `refactor(sprint-138-p3-types): split lib/types.ts by domain (barrel, pure move)`
- Files: frontend/lib/types/*.ts (NEW, 18+barrel) + frontend/lib/types.ts (DELETED) + sprints/plan_sprint_138-P3-LIB-SPLIT.md + sprints/end_sprint_138-P3-types.md.
- Serial: api (Commit 2) dispatched only after team-lead Chrome spot-check OK on this.
