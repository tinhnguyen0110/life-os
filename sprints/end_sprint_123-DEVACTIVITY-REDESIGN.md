# end_sprint_123-DEVACTIVITY-REDESIGN — Dev Activity: you-only + GitHub heatmap + default-tab + underline-nav (Cairn #123)

> Result. The Dev Activity sub-tab simplified to the user-CHỐT: JUST your own commits (drop you-vs-team/team-context), default sort lastActive-desc, a real GitHub-style contribution heatmap (~1yr), the sub-nav restyled to underline-tabs + DEFAULT = Dev Activity (supersedes #120's running-default). Commit `<hash>` `feat(sprint-123-devactivity-redesign)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc + vitest 1040/0). Cairn #123 — fe-only, CLOSES on this commit. Disjoint from #124 (BE, committed parallel).

## What shipped (FE — 5 mod + tokens)
| File | Change |
|---|---|
| `app/projects/page.tsx` | DEFAULT subTab = "dev" (bare /projects → Dev Activity; ?tab=running/graveyard deep-links kept, ?tab=dev still resolves). sub-nav `.seg` → scoped `.subnav` underline-tab (active=accent-underline+bright, inactive=muted, subtle count). |
| `components/DevActivityView.tsx` | YOU-ONLY: dropped the you-vs-team comparison + team-context render (renders only YOUR byRepo + totals); byRepo [] → empty-state-for-you + the DEV_TRACING_EMAILS hint (honest). default sort lastActive-desc. GitHub-style heatmap (week-cols×T2→CN, 5 green bands, month labels, per-cell tooltip, legend, ~1yr days=365). KEPT: KPI strip + the #97 analyst row (YOUR cpd/net-LOC/span/peak/velocity) + the sortable table. |
| `lib/devStats.ts` (+`buildGithubHeatmap`, −`youVsOther`) | the GitHub-heatmap builder (per-day count → week-grid + bands); removed the you-vs-other helper. |
| `lib/tokens.css` | `.subnav` underline-tab tokens + the heatmap bands; the 2px-overflow bug fixed. |
| tests (+10 → 1040) | default-dev tab, you-only render, sort lastActive-desc, the heatmap grid/bands, underline-nav, deep-links. |

## Design (LOCKED — you-only, GitHub heatmap, default-dev, scoped underline-nav)
- **default = Dev Activity** (user-CHỐT "default dec activity") — bare /projects lands on dev; this SUPERSEDES #120's running-default (latest user directive wins; the user changed their mind — not a conflict). ?tab=running/graveyard remain explicit deep-links.
- **you-only:** the BE already splits byRepo (you) vs otherRepos (team) — the FE renders ONLY byRepo + your totals, drops the team-context (NO BE change). honest empty-state-for-you when byRepo [].
- **GitHub heatmap:** days=365 (~1yr, the BE aggregated view); week-cols × T2→CN, 5 bands by per-day count, month labels, tooltip, legend.
- **scoped `.subnav`** (NOT the global `.seg`) underline-tab restyle — so it doesn't bleed to other segmented controls.

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** the default-tab flip (subTab = running?running:graveyard?graveyard:dev → default dev; deep-links kept); you-only (dropped youVsOther import + team-context render, honest byRepo-[] empty-state); buildGithubHeatmap + days=365; scoped .subnav. FE-only stage (BE tree clean post-#124 — no cross-lane). ✅
- **tsc clean; vitest 89 files / 1040 passed / 0 failed** (independent re-run; +10 over the 1030 baseline; tail clean). ✅
- **frontend-w3-2 Chrome :3010:** bare /projects lands on Dev Activity; switching tabs works; you-only (no team-context); sort lastActive-desc; the GitHub heatmap renders (~1yr, bands, tooltip, legend); underline-nav (active accent-underline); console clean; the 2px-overflow fixed. ✅
- **mock-diff:** dropped = exactly you-vs-team/team-context; kept = your byRepo/analyst/KPI/table. ✅

## 3 Gates
- **Gate 2 (Function):** the +10 tests (default-dev/you-only/sort/heatmap/underline/deep-links) + tsc + vitest 1040/0 + Chrome. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step; staged EXACTLY the 6 FE files (NO #124 BE / template / data leak); commit format. ✅

## Assumptions (user-review)
- **default tab = Dev Activity** (supersedes #120 running-default — the latest user-CHỐT). **How to change:** the subTab default in page.tsx.
- **Dev Activity = you-only** (byRepo, no team-context). **How to change:** re-add the youVsOther/team render (the BE otherRepos split still exists).
- **heatmap = days=365 (~1yr).** **How to change:** the range default in DevActivityView.

## Notes
- Cairn #123 — fe-only user-CHỐT (3 asks: you-only + sort-recent + GitHub-heatmap + default-dev + underline-nav). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). **The default-tab is a #120 supersession** — #120 set running-default, the user later CHỐT default-dev; the latest directive wins (documented honestly in the nav comment, not a silent flip). NO BE change (the byRepo/otherRepos split + days=365 aggregated view already existed — the FE just consumes them differently). **Parallel-lane staging (8th clean):** committed FE-only while #124 BE was committed+landed in parallel — disjoint, leak-check clean. After push → team-lead Chrome-verifies (default-dev + heatmap). The TRACING-UX2 cluster: #121/#122 (tracing redesign) + #123 (dev-activity) + #124 (template-add) all shipped; #125 (note one-shot date) is the last, in flight behind #124.
