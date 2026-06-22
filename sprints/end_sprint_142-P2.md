# end_sprint_142-P2 — keep B1/B2 fixed panels on-screen (portal out of transformed ancestor + viewport clamp)

> Sprint 142 (UX-DROPDOWN) Task P2 — the fixed-corner panels (B1 TweaksPanel, B2 SidebarCustomizer). Dispatched as a viewport-clamp; live verify found B1's REAL bug was deeper (a transform ancestor trapping position:fixed → off-screen) → root-cause fix = portal, beyond the CSS-clamp scope. team-lead scope-ACK'd the clamp approach; the portal is the correct deeper fix (flagged + accepted). Closes #142's actionable P1+P2 (P3 deferred, C-group left).

## What shipped (3 files)
- **components/TweaksPanel.tsx (MOD):** wrap the returned `<>backdrop + panel</>` in `createPortal(…, document.body)` + `if (!open || typeof document === "undefined") return null` SSR guard. JSX contents byte-identical.
- **components/SidebarCustomizer.tsx (MOD):** identical portal change (B2 had no transform ancestor but portaled for consistency/future-proofing).
- **lib/tokens.css (MOD):** `#tweaks`/`#sbcust` gain `max-width: calc(100vw - 32px)` + body `max-height: min(<orig>vh, calc(100vh - <offset>))` so the panel can't exceed a narrow/short viewport. Visual styling untouched.

## 🔴 The deeper bug (FE found at live-verify, beyond the dispatch's CSS-clamp scope — accepted)
- B1 TweaksPanel rendered OFF-SCREEN (FE measured top:1024 bottom:1472 vs 955 viewport) despite `position:fixed`. ROOT CAUSE: it's mounted in the settings view, and the route-change fade-in `@keyframes viewin { from { transform:translateY(7px) } }` (lib/tokens.css:461) applies a `transform` to the view container. **A transform ancestor becomes the containing block for its `position:fixed` descendants** → the panel anchored to the transformed ancestor, not the viewport → off-screen. A CSS max-w/max-h clamp CANNOT fix that (the panel is mis-anchored, not just oversized).
- FIX = `createPortal` to document.body (escapes the transform — same mechanism as the P1 Popover) + the CSS clamp (orthogonal, for narrow/short viewports).
- **Verified the transform-trap is real** (architect): grepped lib/tokens.css → `@keyframes viewin` transform on the view container confirmed; FE's `matrix(1,0,0,1,0,7)` = translateY(7px) mid/lingering-animation. The diagnosis + the portal fix are correct. This is the implementer-flag-a-deeper-root-cause pattern done right — divergence from the dispatch's CSS-only scope ACCEPTED because it's the correct fix.

## Verify (architect 4-step + live Chrome via javascript_tool — Rule#0)
1. **git diff:** 3 files only (TweaksPanel, SidebarCustomizer, tokens.css). Minimal portal wrapper + SSR guard; JSX byte-identical; CSS clamp added.
2. **Read full functions + verified the transform-trap claim on disk** (the @keyframes viewin transform).
3. **tsc --noEmit exit 0.**
4. **vitest 1115** (no new tests — CSS+portal; TweaksPanel/SidebarCustomizer/Sidebar tests green, 0 dropped). 0 err.
5. **🔴 Live Chrome (architect, settings :3010, javascript_tool):**
   - B1 TweaksPanel (open-tweaks): `parentElement===document.body` (PORTALED), position:fixed, rect top:407 right:1904 bottom:855 → **fullyOnScreen:true** (was off-screen top:1024 before), maxWidth:1888px (the clamp), closes on Escape ✓.
   - B2 SidebarCustomizer (sb-customize): `parentElement===document.body`, position:fixed, rect top:54 left:16 → fullyOnScreen:true, maxWidth:1888px, **closes on backdrop-click** ✓.
6. 🔶 Honest live-gate limit (same as P1): CDP couldn't shrink the page viewport → the SHORT-viewport max-height clamp is correct-by-construction (CSS calc) but un-forced live; the PORTAL + max-width ARE proven live. team-lead's gate to test a real short window.

## Gates
- Gate 2 (Function): portal + SSR guard; behavior preserved (close paths Escape+backdrop verified live); tsc clean; live Chrome on-screen verified both panels. ✓
- Gate 3 (Sprint): this doc + 4-step full-function read + transform-trap verified on disk + live Chrome both panels + count == baseline. ✓

## Assumptions (user-review)
- **Portal-to-body for fixed overlays inside an animated view.** Any `position:fixed` overlay mounted inside a view with the `viewin` route-transition (or any transform/filter ancestor) must portal to body to anchor to the viewport. How to change: the systemic fix is to not transform the view container, but portal is the safe local fix matching P1's Popover.
- **CSS calc clamp (max-width/max-height) for narrow/short viewports** — preferred over JS (simpler, no measure loop). How to change: a JS clamp if a future panel needs dynamic repositioning.

## Commit
- Hash: (filled) — `fix(sprint-142-p2): keep B1/B2 fixed panels on-screen — portal out of transformed ancestor + viewport clamp`
- Files: components/TweaksPanel.tsx + components/SidebarCustomizer.tsx + lib/tokens.css + this doc.
- HOLD push for team-lead's Chrome gate (open both on a SHORT + NARROW viewport) → OK → push → #142 actionable scope DONE.
