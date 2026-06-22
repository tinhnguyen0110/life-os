# end_sprint_108-WIKI-EXPLORER-REFRESH — Explorer folder-count live-refresh after write (Cairn #108, dogfood FE)

> Result. Writing a note to a NEW folder (e.g. Projects/fulfill-app) → the BE was correct end-to-end (`/wiki/tree` counts:1, #101-verified) but the Explorer (left column) still showed Projects=0 → the UI didn't re-fetch the tree after a write (it only refetched on a route change). The write looked like it failed → manual reload. Fixed (FE-only): a tiny module-level pub/sub bus — any tree-mutating write bumps it on success → the persistent Explorer (useWikiTree) subscribes + refetches. Commit `<hash>` `fix(sprint-108-wiki-explorer-refresh): tree-bus → Explorer count live-refresh after write (#108)`. Status: ✅ verified (frontend-w3-2 built + Chrome live-repro; architect 4-step + tsc + vitest). Cairn #108 NORMAL — dogfood (team-lead Rule#0-confirmed); BE was already correct (purely a FE cross-component refresh gap).

## What shipped (FE-only — bus + wiring + tests)
| File | Change |
|---|---|
| `lib/wikiTreeBus.ts` (NEW) | a module-level pub/sub: monotonic `version` + `listeners` Set. `markWikiTreeStale()` bumps + notifies (array-copy guard for mid-notify unsubscribe + try/catch so a bad listener can't block others); `wikiTreeVersion()` for the last-seen race-guard; `subscribeWikiTree(fn)` → unsubscribe. Pure in-memory, SSR-safe (no window), no deps. |
| `lib/api.ts` | the 6 tree-mutating writes (`createWikiNote`/`importWiki`/`updateWikiNote`/`deleteWikiNote`/`restoreWikiNote`/`bulkDeleteWikiNotes`) → `.then(bumpTree)` → bumps the bus ONLY on a resolved (successful) write. |
| `lib/useWiki.ts` (`useWikiTree`) | subscribes to the bus → a tree-stale signal bumps the refetch nonce; a `lastSeen`-vs-`version` check after subscribe catches a bump that landed between mount + subscribe (the missed-signal race). |
| `lib/__tests__/wikiTreeBus.test.ts` (NEW, 5) + `components/shared/__tests__/WikiExplorer.test.tsx` (+2) | the bus pub/sub + the Explorer-refetches-on-write integration. |

## Design (LOCKED — pub/sub bus, success-only bump, race-guarded subscribe, all-write-paths)
- **the bug:** the Explorer fetched the folder tree ONCE + only refetched on a route CHANGE. A note created/imported/moved into a folder with NO navigation left the Explorer showing the stale pre-write count. The BE was correct (#101) — purely the FE cross-component refresh wiring (the write happens in the import modal / capture form / a different component than the persistent Explorer in the layout).
- **module-level pub/sub (the right decoupling):** a write in component A must invalidate the tree query in component B (the Explorer). A module-level version+listeners bus decouples them without prop-drilling or a global store. `markWikiTreeStale()` on write → the Explorer's subscriber refetches.
- **success-only bump:** `.then(bumpTree)` runs only when the write promise RESOLVES → a failed write does NOT bump (no spurious refetch / no false "it worked" signal).
- **race-guarded subscribe (the subtle correctness):** a write may bump the version between the Explorer's mount and its subscribe → the `lastSeen`-vs-`wikiTreeVersion()` check after subscribe catches it (no missed signal). The monotonic version is what makes this detectable.
- **all 6 write paths covered (recheck-all-writes):** create / import / update(move-folder) / delete / restore / bulk-delete — every tree-mutating write bumps, not just create. A move changes BOTH the old + new folder counts; a delete/restore changes the count too.
- **BE UNTOUCHED:** the BE is correct end-to-end (#101) — this is purely FE. The wiki/* dirty in the tree during this work = #107's separate be-wiki lane (NOT #108).

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** the bus (version+listeners, array-copy + try/catch guards); api.ts `.then(bumpTree)` success-only on all 6 writes; useWikiTree subscribe + the lastSeen race-guard; bumpTree passes the result through unchanged. ✅
- **architect tsc + vitest gate:** `npx tsc --noEmit` clean (exit 0); `npx vitest run` = **998 passed** (was 991 → +5 bus +2 Explorer). ✅
- **frontend-w3-2 Chrome (the load-bearing — it's a UI-refresh bug):** on :3010, import a note → Projects/fulfill-app (NEW folder) → the Explorer count updates LIVE, no reload; dark-mode ok; console clean; cleanup scoped (probe note soft-deleted, vault back to baseline). The teeth PROVEN by neutralizing the subscribe → exactly the 2 #108 Explorer tests go red, rest green. ✅
- (one flaky non-FE settings-test under parallel load → re-ran 998/998 clean + settings 18/18 ×3 isolated; not FE's, not #108.)

## 3 Gates
- **Gate 2 (Function):** the bus pub/sub + the Explorer-refetch-on-write tests; tsc clean; vitest 998/998; the Chrome live-repro (count-updates-no-reload — the load-bearing proof); success-only bump + race-guard. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step + tsc/vitest; staged EXACTLY the 5 FE files + end doc (NO #107 be-wiki, no data/.env); commit format. ✅

## Assumptions (user-review)
- **a module-level pub/sub bus (not a global store / not prop-drilling)** for the cross-component tree-refresh. **How to change:** if the app adopts a query lib (react-query/swr), replace the bus with that lib's invalidate.
- **bump on SUCCESS only** (`.then(bumpTree)`); a failed write doesn't refetch. **How to change:** the bumpTree chaining in api.ts.
- **all 6 tree-mutating writes bump** (create/import/update/delete/restore/bulk-delete). **How to change:** add `.then(bumpTree)` to any new tree-mutating write fn.

## Notes
- Cairn #108 NORMAL — admin-lead dogfood (write to a new folder → Explorer stale count → looks like the write failed). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). FE-ONLY (BE correct end-to-end per #101 — explicitly OUT of scope). The race-guarded subscribe (lastSeen-vs-version) is the subtle correctness piece — a bump between mount+subscribe isn't missed. All 6 write paths bump (recheck-all-writes, not just create). Committed from an intermixed tree (#107's be-wiki lane in flight simultaneously) — surgical FE-only stage, zero #107 leak. team-lead live-verifies the Chrome new-folder count-updates-live on the container.
