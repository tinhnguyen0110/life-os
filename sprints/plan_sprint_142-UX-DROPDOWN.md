# plan_sprint_142-UX-DROPDOWN — fix all dropdowns/modals wrong-located

> User (via team-lead): "fix all dropdown/modal wrong located" — overlays render off-screen / wrong anchor / clipped by overflow / behind siblings / not tracking trigger. HIGH priority. team-lead: kickoff = ENUMERATE every overlay → surface to team-lead for scope → then batch fixes (portal out of clipping ancestors, viewport-edge collision flip/shift, correct anchor, z-index, track-on-scroll). Behavior-preserving. team-lead Chrome-verifies EACH opens at correct on-screen position (live, test near viewport edges).

## Enumeration (Rule#0, read-only Explore sweep of frontend/ — 14 distinct overlays)

### A. Inline ANCHORED menus — 🔴 THE REAL POSITIONING HAZARD (absolute-to-parent, z-index:20, no edge-collision)
| # | Overlay | File:line | Current | Risk |
|---|---|---|---|---|
| A1 | Tracing TimelineRow ⋯ ops menu | app/tracing/page.tsx ~445 | `.tl-ops-menu` absolute right:0 top:100%, parent relative, useClickAway | clips off right/bottom edge near viewport edge; no flip |
| A2 | Tracing NoteCard ⋯ ops menu | app/tracing/page.tsx ~530 | same `.tl-ops-menu` | same |
| A3 | Wiki folder ⋯ ops menu (per-folder) | components/shared/WikiExplorer.tsx ~100 | `.wex-ops-menu` absolute right:0 top:100%, NO useClickAway (setState-only toggle) | clips in the scrollable explorer tree (overflow ancestor!); stays open on outside-click |

### B. Fixed-anchored panels — MEDIUM (no viewport-edge guard, can clip on short/narrow)
| # | Overlay | File:line | Current | Risk |
|---|---|---|---|---|
| B1 | TweaksPanel (theme) | components/TweaksPanel.tsx ~37 | `#tweaks` fixed bottom:44px right:16px z:400, max-h | no collision guard; clips on narrow/mobile |
| B2 | SidebarCustomizer | components/SidebarCustomizer.tsx ~41 | `#sbcust` fixed top:54px left:16px z:400, max-h:74vh | clips if viewport very short |

### C. Centered full-screen modals — LOW/MEDIUM (fixed inset, robust; z-index + height-on-short-viewport notes)
| # | Overlay | File:line | Current | Risk |
|---|---|---|---|---|
| C1 | PrivacyRevealModal | components/PrivacyRevealModal.tsx ~59 | fixed center translate, z:500/499 | LOW (robust centered) |
| C2 | TemplateSetsModal | app/tracing/TemplateSetsModal.tsx ~87 | `.wex-move` fixed inset grid-center z:50 | LOW; z:50 low vs panels z:400 |
| C3 | WikiImport modal | components/WikiImport.tsx ~79 | `.wimport-overlay` fixed inset z:50, modal min(640,100%) max-h:85vh | overflow on very short viewport |
| C4 | WikiTrash modal | components/WikiTrash.tsx ~31 | reuses `.wimport-*` | same as C3 |
| C5 | WikiExplorer move-note modal | WikiExplorer.tsx ~287 | `.wex-move` fixed inset center z:50 | z:50; if 2 wex modals stack, collision |
| C6 | WikiExplorer folder-op modal (create/rename/delete) | WikiExplorer.tsx ~298 | `.wex-move` | same |
| C7 | WikiExplorer import-to-folder modal | WikiExplorer.tsx ~352 | `.wex-move` | same |

### D. Inline expand editors — LOW (in-flow grid expansion, NOT floating; useClickAway). NOT positioning bugs.
- D1 Tracing TimelineRow time editor (gridColumn 1/-1), D2 reminder editor, D3 NoteCard reminder editor.
- (Listed for completeness; no position fix needed — they expand in-flow.)

### Shared-helper status
- EXISTS: `lib/useClickAway.ts` (close-on-outside, mousedown + defer-attach).
- 🔴 GAP: NO shared Popover/portal primitive · NO viewport-edge collision helper · NO z-index scale (each overlay hardcodes) · each backdrop hand-rolled.

## Proposed fix strategy (surface for team-lead scope sign-off)
**Root cause of "wrong located":** anchored menus (A1-A3) use `position:absolute` relative to a parent that may be (a) near a viewport edge → menu overflows off-screen, or (b) inside an `overflow:hidden/auto` ancestor (the wiki explorer tree IS scrollable → A3 clips). Fixed panels (B1-B2) have no edge guard. This is the user's "wrong located / clipped / off-screen" report.

**Recommended approach — build ONE shared primitive, migrate the anchored menus to it (the don't-over-build sweet spot):**
- **P1 (HIGH, the core fix): a shared `<Popover>` / `useAnchoredPosition` primitive** — portals the floating panel to `document.body` (escapes ALL overflow-clip ancestors) + computes position from the trigger's `getBoundingClientRect()` + viewport-edge collision (flip up/down, shift left/right to stay on-screen) + tracks on scroll/resize + a consistent z-index above panels. Migrate A1, A2, A3 to it (A3 also gains the missing useClickAway). This kills the actual off-screen/clip bugs.
- **P2 (MEDIUM): viewport-edge guard for the fixed panels B1, B2** — clamp `#tweaks`/`#sbcust` within the viewport (or reuse the P1 collision helper) so they don't clip on short/narrow screens.
- **P3 (LOW, optional): z-index normalization** — a small z-scale so the z:20 anchored menus sit above the z:50 modals correctly + the wex modals don't collide when stacked. Only if team-lead wants it; the C-group modals are otherwise fine (centered-fixed is robust).
- The C-group centered modals are LOW risk (fixed-center is correct) — I'd LEAVE them unless team-lead's own Chrome finds a specific one mis-rendering. Don't-over-build: the bug is the anchored menus + unguarded panels, not the centered modals.

**Behavior-preserving:** the menus/panels open from the same triggers, same contents, same close-on-click-away — only their POSITION computation changes (correct anchor + on-screen). vitest count unchanged (positioning is visual; covered by team-lead's live Chrome edge-test gate, not unit tests).

## Dispatch order (after team-lead scope sign-off)
1. P1 build `<Popover>`/`useAnchoredPosition` + migrate A1-A3 (one FE task — frontend-w3-2). The biggest win.
2. P2 fixed-panel edge guard (B1-B2) — can follow or fold into P1's helper.
3. P3 z-index normalization — only if team-lead opts in.
Each: behavior-preserving, tsc+vitest same count, team-lead Chrome-verifies EACH overlay opens on-screen incl. near viewport edges (the live gate). Serial commits (shared CSS/primitive).

## Scope SIGNED OFF (team-lead, 2026-06-23)
- ✅ **P1 (HIGH core) — GO first.** Shared `<Popover>`/`useAnchoredPosition` (portal-to-body + getBoundingClientRect anchor + viewport-edge flip/shift + track-on-scroll + z:600) + migrate A1/A2/A3 (A3 +useClickAway). DISPATCHED to frontend-w3-2.
- ✅ **P2 (MED) — YES, after P1.** B1 TweaksPanel + B2 SidebarCustomizer edge-guard reusing P1's collision helper.
- ⏸ **P3 (z-index) — DEFERRED.** No speculative churn; revisit only if team-lead's Chrome catches a menu-behind-modal during P1/P2.
- ⏸ **C-group (7 centered modals) — LEAVE.** Fixed-center robust = not misplaced. team-lead spot-checks a couple during verify; add only if one mis-renders.
- Gate: P1 diff-ready → architect 4-step → commit → HOLD push for team-lead's live Chrome edge-test (open each ⋯ near right/bottom edges + inside scrollable wiki tree → on-screen, not clipped, close on outside-click) → OK → push.
