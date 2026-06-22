# end_sprint_uxpolish-tracing — #143 /tracing polish: ghost-ify the unset Đặt-giờ pill (R2)

> #143 UX-polish lane, /tracing first (daily-driver, heaviest recent rework). Architect Chrome-audit → rough-edge list → team-lead scope pick (R2 primary, R1/R5 if-real, R3/R4/R6 skip) → FE one-screen behavior-preserving pass → 4-step → commit → team-lead before/after Chrome gate. CSS-only.

## What shipped (1 file)
- **lib/tokens.css — `.tl-settime-pill` accent-tinted → GHOST/muted:** `background:transparent` (was accent 13%), `color:var(--tx-2)` (was var(--accent)), `border:1px solid var(--line-2)` (was accent 32%), `opacity:.8`, label weight 600→500, gentle neutral hover lift (bg-2/tx-1/opacity 1). SAME dimensions (padding/radius/font-size unchanged → reserves the same box → column alignment unchanged). Class/testid/label/handler untouched → behavior-identical.

## Why (R2 — the primary, team-decided)
The unset-time pill was `var(--accent)`-tinted (copper, not literal red — architect flagged the accuracy; team-lead's semantic point holds). On 6/7 rows a saturated accent pill = a loud DEFAULT-state wall that dominated the time column + competed with / buried a real SET time or alert. Ghost-ifying makes the unset state RECEDE → a set time (or a real alert) stands out. Still clearly a clickable affordance (≈ the ⋯-btn opacity:.55 discoverability bar).

## R1 + R5 — verified-and-SKIPPED (no manufactured work)
- R1 (column alignment): team-lead + FE measured — the time slot is ALREADY fixed-width (left:279/right:345 for both the timed 07:00 row and the pills; name-left:410 aligned). The ghost restyle keeps the SAME box → alignment holds. NO change.
- R5 (add-row spacing): measured add-input→time-input gap = 8px, clean. NO crowding → NO change.
- R3/R4/R6: skipped (verify-only — empty-states honest, ⋯ opacity:.55 visible, panels consistent).

## Verify (architect 4-step + live Chrome via javascript_tool — Rule#0)
1. **git diff:** 1 file (lib/tokens.css), the pill restyle + comment. (Untracked template/ + sprint docs not staged.)
2. **Read full:** accent→muted, same dimensions, behavior-identical.
3. **tsc 0.**
4. **vitest 1115** (no delta — CSS only; tracing 41/41 incl the #139 pill-structure tests which assert class/text NOT color → no test edit needed). 0 err.
5. **🔴 Live Chrome (architect, :3010):** pill computed `color: rgb(102,100,92)` (=--tx-2 muted, NOT accent), `bg: rgba(0,0,0,0)` (transparent), `border: rgb(48,48,58)` (=--line-2), `opacity:.8`, `cursor:pointer` (still clickable). 🔴 NO-REGRESSION proof: clicking the ghost pill added a per-card time editor (time-inputs 1→2) → **#139 click-to-set-time still works**. The restyle is purely visual.

## 🔶 Unrelated flake flagged (NOT this commit — separate lane)
- FE saw ONE full-suite run hit "1 failed/1114" that did NOT reproduce (5 reruns + my run all 1115). The flaky line = an unrelated **#31 Reminders** test (isolation/timing), NOT tracing — a CSS-only change cannot cause a Reminders test failure. Same class as the #141 settings flake. FLAGGED for a possible future flake-fix task (tester-owned); does NOT block this commit (current state is 1115 green).

## Gates
- Gate 2 (Function): CSS-only visual change; behavior preserved (click-to-set verified live); tsc clean; vitest no-delta; live Chrome muted + no-regression. ✓
- Gate 3 (Sprint): this doc + 4-step + live Chrome + count == baseline. ✓

## Assumptions (user-review)
- **R2: the unset-time "⏰ Đặt giờ" pill is GHOST/muted, not accent-tinted** — team-decided UX (decide-and-log). Rule: a saturated pill on most rows for a benign DEFAULT state (no time set) is a loud/semantic-noise anti-pattern; the unset state should recede so a real set-time/alert stands out. How to change: restore the accent tint in `.tl-settime-pill` if the user prefers the louder invitation.

## Commit
- Hash: (filled) — `fix(sprint-uxpolish-tracing): ghost-ify the unset Đặt-giờ pill (quiet default state)`
- Files: lib/tokens.css + sprints/plan_sprint_uxpolish-tracing.md + sprints/end_sprint_uxpolish-tracing.md.
- HOLD push for team-lead's before/after Chrome gate (pill recedes + still click-to-set, columns aligned, no #136/#137/#139 regression, console clean) → OK → push. Next polish screen: wiki → finance → projects.
