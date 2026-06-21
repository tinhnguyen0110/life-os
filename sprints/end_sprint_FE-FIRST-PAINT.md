# end_sprint_FE-FIRST-PAINT — progressive render /decision + /macro (Cairn #71)

> Result. Killed the all-or-nothing render barrier on /decision (10s blank-hang → 1s first-paint) + a skeleton grid on /macro. Commit `<hash>` `fix(sprint-FE-FIRST-PAINT)`. Status: ✅ verified (FE agent + architect 4-step). frontend-w3-2 BUILT; architect committed (§3, FE-domain commit-hygiene). Reactive NEVER-FREE fill-lane; disjoint from #65-P4 + #58 → committed FIRST in arrival-order (it was the only verified-DONE commit).

## What shipped (5 FE files)
| File | Change |
|---|---|
| `lib/useDecision.ts` | the render-barrier fix — replaced `Promise.allSettled`-then-batch with per-section `wire(promise, setter)`: each section's `.then` updates ITS section + marks ok/fail as it settles. status → "ready" on the FIRST success; "error" ONLY when all 5 settled AND all failed. `alive` guard preserved; sections reset to EMPTY on reload (no stale). |
| `app/decision/page.tsx` | dropped the all-or-nothing `status==="loading"` gate → renders shell + every panel immediately; a not-yet-arrived section shows `SectionPending` ("đang tải…"). |
| `app/decision/__tests__/decision.test.tsx` | 2 progressive teeth: "shell + per-section placeholders render (NO all-or-nothing blank gate)" + "a FAST section paints while a SLOW one is still pending (the win)". |
| `app/macro/page.tsx` | a 6-card skeleton grid (aria-busy, sk-line shimmer, aria-hidden skeleton) instead of a bare "loading" line — layout appears immediately while macro (~1-2s, slower cold from FRED) resolves. |
| `lib/tokens.css` | the skeleton CSS: `.sk-line` (shimmer gradient), `.macro-skeleton`, `@keyframes sk-shimmer`, `@media (prefers-reduced-motion: reduce)` guard. |

## Design (LOCKED — progressive, honest-partial)
- Each section paints as its OWN promise settles (no barrier on the slowest). First-success → render the tower; a partly-thin tower is HONEST (not an error screen). error ONLY when the whole backend is down (all 5 failed).
- reduced-motion safe (the shimmer animation is disabled under prefers-reduced-motion).

## Verification (FE agent + architect 4-step)
- **frontend-w3-2:** vitest 877/0/0, tsc clean, Chrome before/after: /decision 10s→1s first-paint, /macro skeleton renders. Root-cause = render-barrier (allSettled gated on slowest); teeth-tested.
- **architect 4-step (read FULL files on disk):** useDecision progressive `wire` correct — first-success→ready; all-5-failed→error; NO flip-back to error after ready (error branch requires `!results.includes("ok")`); `alive` guard; EMPTY reset on reload ✅; decision/page drops the gate → per-section pending/data/error ✅; macro skeleton grid (aria-busy/aria-hidden/reduced-motion) ✅; the 2 test assertions are real progressive teeth (not field-reads) ✅; **tokens.css diff = PURELY the skeleton block, ZERO P3 tracing leftover** (re-verified the cross-sprint boundary myself — content-diff-not-just-filenames) ✅.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 877/0/0 + tsc clean + Chrome before/after; progressive teeth (fast-while-slow-pending); reduced-motion guard. ✅
- **Gate 3 (Sprint):** plan+end docs; FE-agent + architect 4-step; commit-hygiene (explicit 5 FE + 2 docs; tokens.css boundary clean; no template/data/.mcp/Instruction leak; git-status-after-stage zero-dirty incl. the decision test); commit format. ✅

## Assumptions (user-review)
- **/decision + /macro first-paint = progressive render** (sections paint as they settle; skeleton placeholders for pending). status "ready" on first success, "error" only if all 5 fail. **How to change:** the useDecision wire/mark logic.

## Notes
- Cairn #71. Reactive NEVER-FREE fill-lane (team-lead-raised while FE was idle). frontend-w3-2 BUILT; architect committed (§3). Committed FIRST in arrival-order (team-lead-confirmed: first-verified-first-committed; #71 was ready while #65-P4 + #58 were still building; all 3 disjoint → git-safe). team-lead Chrome-verifies /decision + /macro first-paint post-push + closes #71. Queue continues: P4 / #58 in arrival order as they finish; #65 EPIC completes when P4 lands.
