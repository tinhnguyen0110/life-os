# end_sprint_97-DEV-ACTIVITY-POLISH — dev-activity analyst stats + velocity + sortable table (Cairn #97 FE)

> Result. /dev-activity gains an analyst layer on the EXISTING data (render-only, no backend): range filter 7/14/30/90 · analyst-stats row (active-span / peak-hours / net-LOC / commits-per-day) · velocity-trend (3-way honest via the REUSED #81 deltaGlyph) · you-vs-other ratio bar · per-repo sortable table. honest-mirror throughout (a no-attribution range → null/empty, never a faked stat). Commit `<hash>` `feat(sprint-97-dev-activity-polish): analyst stats + velocity + sortable table (#97)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + the honest-derivation read + tsc + vitest). Cairn #97 FE (user-raised; UI the user reviews async). NO merge with /projects (locked, kept separate).

## What shipped (FE — pure derivations + page wiring, render-only)
| File | Change |
|---|---|
| `lib/devStats.ts` (NEW) | PURE analyst derivations from the EXISTING /dev_activity fields: `netLoc` (both-null→null, no fake 0) · `commitsPerDay` (0-active→null, no div0) · `peakHours`/`peakHour` (real YOUR start-hour distribution, NOT smoothed; empty→null) · `totalActiveMinutes`+`fmtMinutes` (per-day YOUR first→last spans; no-you→null) · `velocityWindows` (recent vs prior win; no-prior→prior:null) · `youVsOther` (other=0→100, you=0→0, both-0→null) · `sortRepos` (commits/locAdded/locDeleted/activeDays/lastActive; null lastActive sorts LAST both dirs; pure). |
| `app/dev-activity/page.tsx` | RANGES [30,90,180]→**[7,14,30,90]**; the analyst-stats row + the velocity-trend (REUSES `deltaGlyph` from lib/format — IMPORT not copy: `velGlyph = deltaGlyph(prior==null ? null : recent−prior)` → ▬ honest on no-comparison) + the you-vs-other bar + the per-repo sortable table (header-click sort). render-only (BE computed the data). |
| `lib/tokens.css` | the analyst-row / sortable-table styles. |
| tests | `lib/__tests__/devStats.test.ts` (NEW) + `app/dev-activity/__tests__/dev-activity.test.tsx` — every honest-null distinguishing case + the sort. |

## Design (LOCKED — render-only, honest-mirror, reuse, no-merge)
- **render-only:** all stats DERIVED from the existing summary/byRepo/byDay (NO backend). The BE owns the data; devStats is pure display math.
- **🔴 honest-mirror (the load-bearing — the user explicitly wanted honest):** every derivation returns null/empty on no-data, NEVER a fabricated stat — commits/day null on 0-active (no fake 0/div0) · net-LOC null on no-data · peak-hour null on no-"you" · velocity ▬ "chưa đủ lịch sử" when prior is null (NOT a fabricated ▲) and ▬ on flat (no false-green) · you-vs-other honest at other=0 (100%, post-#84/#85 double-count fix) / you=0 (0%) / both-0 (null, nothing shown).
- **peak-hour shows the REAL pattern** (incl a 00:00 night-owl peak) — NOT smoothed/normalized away (the user wanted the truth).
- **velocity REUSES #81 deltaGlyph** (imported, not re-implemented) — the single 3-way honest arrow.
- **null lastActive sorts LAST** both directions ("never active" ≠ a small date — honest sort).
- **🔴 NO merge with /projects** (LOCKED — different mental models, user CHỐT). #97 is dev-activity polish ONLY.

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** devStats.ts every derivation honest (null/empty on no-data, no fabrication) ✅; page reuses `deltaGlyph` (import) for velocity + RANGES [7,14,30,90] + no /projects reference ✅; FE-only surface (the #51 BE reminders files + the landed #94-BE are NOT in this — staged OUT) ✅.
- **architect independent re-run:** tsc clean (exit 0); vitest FULL **85 files / 980 passed / 0 failed** (956→980, +24 devStats + dev-activity tests); the targeted devStats+dev-activity run = 35 passed.
- **frontend-w3-2 Chrome:** the range filter switches 7/14/30/90 (recomputes); the analyst row renders the real numbers (incl the honest night-owl peak); the per-repo table sorts (commits-desc default / name-asc / LOC-desc / lastActive-null-last); the velocity arrow honest (▬ not green-on-flat/no-prior); a no-attribution range → honest-empty; dark-mode; console clean.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest (every honest-null derivation + the sort) + tsc clean + the velocity-deltaGlyph-reuse + Chrome (range/analyst-row/sort/honest-velocity/honest-empty). ✅
- **Gate 3 (Sprint):** end-doc; FE-agent Chrome + architect 4-step; commit-hygiene (FE-only — the #51 BE + #94-BE files staged OUT, no leak); commit format. ✅

## Assumptions (user-review)
- range filter = 7/14/30/90 (was 30/90/180). **How to change:** RANGES in page.tsx.
- velocity window = ¼ of the range days (≥3), recent vs prior. **How to change:** velWin in page.tsx.
- every analyst stat is honest-null on no-data (no faked numbers — the user wanted honest). **How to change:** the devStats derivations (NOT recommended — honesty is the point).
- peak-hour is the REAL distribution (not smoothed). **How to change:** peakHours (don't normalize — the user wanted the truth).
- NO merge with /projects (separate). **How to change:** N/A (user CHỐT separate; a light cross-link is the only allowed addition).

## Notes
- Cairn #97 FE (user-raised: "thêm filter veloc hàng thống kê analyst... dựa trên data hiện có"). render-only analyst polish on the existing /dev_activity data; the dev-tracing data is correct post-#84/#85 (you-vs-other accurate). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). Committed from a 3-way-intermixed tree (#94-BE landed + #51 BE in flight on backend/reminders) — FE-only surgical stage, no leak. UI-review is ASYNC (shipped verified; the user reviews when free → reactive tweak if wanted). The honest-mirror (every stat null-on-no-data, peak-hour unsmoothed) is the load-bearing value — an analyst layer the user can TRUST. Next: FE-#94 (trash/restore UI) + #51 (in flight).
