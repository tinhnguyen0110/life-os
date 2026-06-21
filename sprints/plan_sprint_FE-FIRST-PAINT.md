# Sprint FE-FIRST-PAINT — progressive render /decision + /macro (Cairn #71)

> Reactive sprint (NEVER-FREE fill-lane, team-lead-raised while FE was idle). FE first-paint: kill the all-or-nothing render barrier on /decision (+ a skeleton on /macro) so a slow endpoint shows layout, not a blank-hang. frontend-w3-2 BUILT; architect commits (§3, FE-domain). Disjoint from #65-P4 + #58 — committed in arrival-order.

## Context
/decision fetched its 5 sections via `Promise.allSettled` then rendered ONCE after the slowest settled (weight ~3s) → a 10s blank-hang before ANY section painted. /macro showed a bare "loading" line. Fix = progressive render (each section paints as its own promise settles) + skeleton placeholders.

## Scope
IN: `lib/useDecision.ts` (the progressive hook) + `app/decision/page.tsx` (per-section pending render) + `app/decision/__tests__/decision.test.tsx` (progressive teeth) + `app/macro/page.tsx` (skeleton grid) + `lib/tokens.css` (the skeleton CSS — .sk-line/.macro-skeleton/@keyframes sk-shimmer/reduced-motion).
OUT: no BE change; no other screen.

## Logic (the render-barrier fix)
- **Before:** `await Promise.allSettled([5 fetches])` → all setState in one batch → `setStatus(anyOk?ready:error)` → page gated on the SLOWEST.
- **After:** `wire(promise, setter)` per-section — each `.then` updates ITS section + marks ok/fail as it settles. status → "ready" on the FIRST success (render the tower immediately); "error" ONLY when all 5 settled AND every one failed (backend down). `alive` guard preserved. Sections reset to EMPTY on reload (no stale during re-fetch).
- decision/page renders shell + every panel immediately; a not-yet-arrived section shows `SectionPending` ("đang tải…"); macro shows a 6-card skeleton grid (aria-busy, sk-line shimmer, reduced-motion safe).

## Verification (FE agent + architect 4-step)
- **frontend-w3-2:** vitest 877/0/0, tsc clean, Chrome before/after: /decision 10s→1s, /macro skeleton. Root-cause = render-barrier; teeth-tested.
- **architect 4-step (read FULL files):** useDecision progressive wire correct (first-success→ready; all-5-failed→error; no flip-back since error requires !includes("ok"); alive guard; EMPTY reset) ✅; decision/page drops the all-or-nothing gate → per-section pending/data/error ✅; macro skeleton grid (aria-busy/aria-hidden, reduced-motion) ✅; test teeth = 2 real progressive assertions (shell+placeholders render; fast-paints-while-slow-pending) ✅; tokens.css diff = PURELY the skeleton block, zero P3 tracing leftover (re-verified the cross-sprint boundary) ✅.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 877/0/0 + tsc clean + Chrome before/after; progressive teeth (fast-while-slow); reduced-motion guard. ✅
- **Gate 3 (Sprint):** docs; FE-agent + architect 4-step; commit-hygiene (explicit 5 FE files + 2 docs; tokens.css boundary clean; no leak); commit format. ✅

## Assumptions (user-review)
- **/decision + /macro first-paint = progressive render** (each section paints as it settles; skeleton placeholders for pending) instead of an all-or-nothing barrier. status "ready" on first success, "error" only if all 5 fail. **How to change:** the useDecision wire/mark logic.

## Notes
- Cairn #71. Reactive fill-lane (NEVER-FREE). frontend-w3-2 BUILT; architect commits fix(sprint-FE-FIRST-PAINT). Disjoint from #65-P4 + #58 → committed in ARRIVAL order (team-lead-confirmed): #71 was the only verified-DONE one → committed first. team-lead Chrome-verifies /decision + /macro first-paint post-push + closes #71.
