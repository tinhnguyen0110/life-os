# end_sprint_bt1-settings-flake — fix the reproducible settings test flake (StrictMode mid-interaction re-render)

> Backend-backlog sprint, Task B-T1. Original target (reminders flake) = CONFIRMED HEALED (tester 55× clean — #141's vitest.setup.ts fix cured it; the FE's "1/6" sighting was pre-#141). B-T1 reframed to fix the REAL active flake tester REPRODUCED: settings.test.tsx. Tester-owned (test isolation).

## What shipped (1 file: app/settings/__tests__/settings.test.tsx)
- Added `act` to the testing-library import.
- 2 write-test methods (briefHour + riskCapitalSmallUsd) get `await act(async () => { await Promise.resolve(); })` after `waitFor(input visible)` and BEFORE the `clear`+`type` interaction → flushes the StrictMode 2nd-effect re-render so the controlled input is stable before interaction.
- Test-only change. No production code, no logic.

## The flake (root-caused + reproduced)
- tester REPRODUCED it: run 16/30 isolated — `edit briefHour + Lưu` asserted `patchSettings({briefHour: 89})` instead of `{briefHour: 9}`.
- ROOT CAUSE: React StrictMode double-invokes the mount `useEffect` that calls `getSettings`. The 2nd invocation's state update (`{briefHour: 8}`) lands MID-interaction — between `user.clear(input)` (empties it) and `user.type("9")` — restoring the input to "8", so type appends → "89". (Same StrictMode class as the original #141 settings fix.)
- `tripleClick` did NOT fix it (the selection is lost when the re-render overwrites the value). The `act()` microtask flush DOES — it settles the 2nd effect + re-render FIRST, so interaction runs on a quiescent DOM.

## Verify (architect 4-step + independent determinism — Rule#0)
1. **git diff:** settings.test.tsx only (act import + 2 act-flush insertions). No stray.
2. **Read full:** targeted fix; both vulnerable write tests covered (riskCapitalSmallUsd would've produced "5000075000" on the same bug); line-61 `mockResolvedValueOnce` correctly LEFT (PATCH is user-triggered, not a mount effect → no StrictMode risk). Clear root-cause comment.
3. **Independent determinism (local binary, per the npx-vitest lesson):** `./node_modules/.bin/vitest run settings.test` **15× consecutive → 15/15 green** (+ tester's 30/30). tsc 0.
4. **Full suite 1115** (settings 18/18, no regression).

## Out-of-scope found (parked, NOT this commit)
- tester saw `sync.test.tsx > renders open conflicts` fail 1/30 (a DIFFERENT file, did not reproduce in 29 + my run) = a separate pre-existing low-rate flake → parked P-6 in BACKLOG_parked.md (tester-owned future micro-task). Not B-T1 scope.

## Gates
- Gate 2 (Function): test-isolation fix; reproduced-first then 15×+30× green (determinism gate); tsc clean; full suite no-regression. ✓
- Gate 3 (Sprint): this doc + 4-step + independent 15× determinism + count unchanged (1115). ✓

## Assumptions (user-review)
- **Reminders flake = confirmed-healed, not fixed here** (no repro in 55 runs; #141 cured it). B-T1's real deliverable became the settings flake tester reproduced. How to change: if the reminders flake ever recurs, re-open with a specific repro.
- **The act-flush pattern for StrictMode-sensitive controlled-input tests:** flush pending effects before interaction when a mount effect re-fetches + resets a controlled input. How to change: nothing — it's the standard testing-library settle pattern.

## Commit
- Hash: (filled) — `fix(sprint-bt1-settings-flake): flush StrictMode effect before input interaction (deterministic settings write tests)`
- Files: app/settings/__tests__/settings.test.tsx + sprints/end_sprint_bt1-settings-flake.md + sprints/BACKLOG_parked.md (P-6).
- Push after commit. Closes the backend-backlog sprint (finance-FE + B-T2 pushed; B-T3/B-T4 closed; B-T1 done).
