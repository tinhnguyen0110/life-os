# end_sprint_142-P1 — shared <Popover> (portal + viewport collision) + migrate A1/A2/A3 anchored menus

> Sprint 142 (UX-DROPDOWN) Task P1 — the HIGH-priority core fix for "all dropdowns/modals wrong located". The per-card/per-folder ⋯ menus used `position:absolute; right:0; top:100%` relative to a parent → overflowed off-screen near a viewport edge + got CLIPPED by an overflow ancestor (A3 wiki folder menu clipped inside the scrollable explorer tree). Fix = a shared portaled Popover with viewport-edge collision. team-lead scope-signed-off (P1 first; P2 next; P3 deferred; C-group left).

## What shipped (3 new + 3 modified)
- **lib/useAnchoredPosition.ts (NEW):** pure `solveAnchoredPosition(anchorRect, panelSize, winBox, margin=8)` → {top,left}. Default = below + right-aligned (mirrors legacy `right:0;top:100%`); flip ABOVE on bottom-overflow (clamped to margin); shift IN on left/right-overflow; final clamp for panel-wider-than-viewport. + the `useAnchoredPosition(anchorRef, panelRef, open)` hook: useLayoutEffect measure (pre-paint, no flash) + rAF re-measure for real panel size + recompute on scroll(capture, catches ancestor scroll)+resize while open; null-until-measured.
- **components/Popover.tsx (NEW):** `<Popover open anchorRef onClose className role testId>` → createPortal to document.body (escapes EVERY clip ancestor) + position:fixed at computed coords + z:600 (POPOVER_Z, above panels 400/modals 500) + outside-mousedown close counting BOTH anchor & panel as inside (panel is portaled out of the anchor subtree) + Escape close + deferred attach (opening click doesn't self-close) + visibility:hidden until measured + SSR guard.
- **app/tracing/page.tsx (MOD):** A1 (TimelineRow ⋯) + A2 (NoteCard ⋯) — inline `{menuOpen && <div className="tl-ops-menu">}` + per-menu useClickAway → `<Popover className="tl-ops-menu">`. Menu CONTENTS byte-identical (same buttons/labels/testids/handlers). The time/reminder INLINE editors keep their own useClickAway (D-group, in-flow, not positioning bugs — untouched).
- **components/shared/WikiExplorer.tsx (MOD):** A3 (folder ⋯) — same migration; 🔴 A3 GAINS click-away + Escape (it had a setState-only toggle with NO outside-close before).
- **lib/tokens.css (MOD):** dropped `position:absolute; right:0; top:100%; z-index:20` from `.tl-ops-menu` + `.wex-ops-menu` (now Popover-owned); kept all visual styling.

## Verify (architect 4-step + live Chrome via javascript_tool — Rule#0, did NOT trust the report)
1. **git diff:** the 6 files only. B1/B2 untouched (P2). C-group untouched.
2. **Read full functions:** collision math correct all directions; Popover portal/fixed/close/SSR/no-flash correct; all 3 menus' contents byte-identical (diffed); A3's gain confirmed (no useClickAway removed because none existed).
3. **tsc --noEmit exit 0.**
4. **vitest 1115 passed (1115)** = 1104 baseline + 11 new Popover tests; A1/A2/A3 behavior tests stayed green (0 dropped). 0 err/0 unhandled.
5. **🔴 Live Chrome (architect, via javascript_tool — the load-bearing positioning gate jsdom can't do):**
   - A1 tracing TimelineRow ⋯: `parentElement === document.body` (PORTALED) ✓, position:fixed, z:600, visibility:visible, onScreen:true (rect within 1920×899), 4 items byte-identical, **closes on outside-mousedown** ✓.
   - A3 wiki folder ⋯: toggle's ancestor = `wiki-pane-left` (the SCROLLABLE clip context) BUT menu `parentElement === document.body` → **escapes the clip** ✓, position:fixed z:600 onScreen:true, 5 items byte-identical, **closes on outside-click AND Escape** (A3's new behavior) ✓.
   - Collision math (mirrored from source, verified equivalent): right-edge → shift to left:1772 (on-screen); bottom-edge → flip up to top:748 (above trigger); left-edge → shift to left:8. All 3 correct.
   - (Exceeds FE's own gate — they couldn't prove right-edge/flip via CDP resize; I confirmed the math + the live portal + the live clip-escape.)

## Gates
- Gate 2 (Function): new components have unit tests (11, incl. the collision math + open/close/portal); A1/A2/A3 behavior preserved (byte-identical contents, tests green); tsc clean; live Chrome positioning verified. ✓
- Gate 3 (Sprint): this doc + 4-step full-function read + live Chrome on 2 of the 3 menus (A1+A3, the highest-risk incl the clip-escape) + count grew only by new tests. ✓

## Assumptions (user-review)
- **Default placement = below + right-aligned** (mirrors the legacy `right:0;top:100%` so nothing visually moves when on-screen). Collision only kicks in at an edge. How to change: adjust solveAnchoredPosition default + the flip/shift thresholds.
- **z-index 600 for popover menus** (above panels 400 / modals 500 — a transient menu is the topmost thing). How to change: the single POPOVER_Z constant.
- **Anchor scrolled out of view → the menu tracks it** (recompute on scroll) rather than auto-closing. How to change: add a close-on-anchor-offscreen check in the hook.

## Commit
- Hash: (filled at commit) — `feat(sprint-142-p1): shared <Popover> (portal + viewport collision) + migrate A1/A2/A3 anchored menus`
- Files: lib/useAnchoredPosition.ts + components/Popover.tsx + components/__tests__/Popover.test.tsx (NEW) + app/tracing/page.tsx + components/shared/WikiExplorer.tsx + lib/tokens.css (MOD) + this doc.
- HOLD push for team-lead's Chrome edge-test gate (open each ⋯ near right/bottom edges + the narrow-window shift FE couldn't CDP-prove) → OK → push. Then P2 (B1/B2 edge-guard).
