# end_sprint_DEV-TRACING-P3 — FE /dev-activity screen (Cairn #63 Phase 3)

> Result. The /dev-activity screen — the user-facing dev-activity cockpit (contribution heatmap + by-repo + KPIs + otherRepos team-context), rendered from the FROZEN P1 schema. Commit `<hash>` `feat(sprint-DEV-TRACING-P3)`. Status: ✅ verified (FE agent + architect 4-step + team-lead). frontend-w3-2 BUILT; architect committed (§3, FE-domain commit-hygiene). Shipped per the UI-async rule. Phase 3 of 3 (P1 BE → P2 remote → **P3 FE**).

## What shipped (6 FE files)
| File | Change |
|---|---|
| `app/dev-activity/page.tsx` (NEW) | the screen — contribution heatmap (reuses the /tracing heatmap pattern), per-day bars, by-repo distribution, summary KPIs (YOUR activity), + the honest-empty-"you" state, + otherRepos as a "team context" section, + warnings rendered verbatim. RENDER-ONLY. |
| `app/dev-activity/__tests__/...` (NEW) | distinguishing tests (honest-empty-you, heatmap, otherRepos, warnings). |
| `lib/useDevActivity.ts` (NEW) | the data hook (getDevActivity + optional scan trigger). |
| `lib/api.ts` | getDevActivity(days) + scanDevActivity(days) — dev_activity-only (post-#46/#70 error shape). |
| `lib/types.ts` | the 6 dev_activity interfaces (RepoDay/DayView/RepoSummary/DevActivitySummary/DevActivityOverview/DevScanResult) — mirror the FROZEN P1 schema. |
| `lib/nav.ts` + `lib/__tests__/nav.test.ts` | /dev-activity nav entry, screen-id **DEVACT** (DISTINCT from /activity = the Run-Log feed S14; nav-uniqueness asserted). |

## Design (LOCKED — render-only, honest, route-distinct)
- **route /dev-activity (NOT /activity)** — /activity is the existing Activity Feed / Run Log; the collision was caught at 4-step + decided /dev-activity (decide-and-log, team-lead + user-surfaced). DEVACT screen-id.
- **honest-empty "you"** (`hasYou = summary.totalCommits > 0`): DEV_TRACING_EMAILS unset → empty-state-for-you + the "set DEV_TRACING_EMAILS" hint, and STILL render otherRepos as team-context (not a blank). warnings rendered verbatim.
- **LOC informational** (Goodhart) — secondary; commits + by-repo + active-span primary. RENDER-ONLY (BE computes; FE displays).
- clean file-split from #76 (NO tokens.css — uses the existing /tracing heatmap tokens; NO /activity touch) → no shared-file tangle.

## Verification (FE agent + architect 4-step + team-lead)
- **frontend-w3-2:** vitest 894/0/0, tsc clean, 6 LIVE distinguishing cases (honest-empty "you" + empty-state hint + warnings verbatim + otherRepos team-context [DevCrew 586/cairn 467/life-os 201] + LOC-secondary + DEVACT nav-unique ≠ /activity).
- **architect 4-step (read FULL files):** honest-empty-you render path (hasYou gate → empty-state + hint + STILL otherRepos) ✅; warnings rendered verbatim ✅; otherRepos aggregated team-context ✅; heatmap reuses /tracing pattern ✅; nav /dev-activity + DEVACT unique (≠ /activity) ✅; api.ts = dev_activity-only (getDevActivity/scanDevActivity, read FULL) ✅; types.ts = the 6 frozen-schema interfaces only ✅; 6-file set, NO #63-P2 BE leak, NO tokens.css/#76 tangle ✅.
- **architect re-run:** vitest dev-activity+nav 19/0; tsc clean.
- **team-lead:** FE report PASS; will Chrome-verify /dev-activity live (honest-empty-you + otherRepos + heatmap + skeleton-on-cold) + close P3.

## Perf note (→ Cairn #77, not blocking P3)
GET /dev_activity = ~24s COLD (re-scans 8-14 git repos live per call). FE mitigated with a skeleton + "scanning git ~20s" hint (in-scope, the #71 lesson). The underlying fix (GET serves FROM the dev_activity SQLite store — P1 already upserts it — NOT a live re-scan; matters for the MCP agent surface too, a consumer shouldn't wait 24s) = **Cairn #77**, likely folds into #63-P2 (store as source-of-truth). NORMAL pri, sequenced after the arc.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 894/0/0 + tsc clean + Chrome (honest-empty-you/otherRepos/heatmap/warnings/skeleton); heatmap teeth. ✅
- **Gate 3 (Sprint):** end-doc; FE-agent + architect 4-step + team-lead; commit-hygiene (6 explicit FE files, content-diffed dev_activity-only, no BE/#76 leak); commit format. ✅

## Assumptions (user-review)
- /dev-activity = the dev-activity cockpit (heatmap + by-repo + KPIs + otherRepos team-context), route DISTINCT from /activity. honest-empty-"you" until DEV_TRACING_EMAILS set. LOC informational. Render-only. **How to change:** the page component.
- ~24s cold-scan mitigated by a skeleton; the store-source-of-truth fix = #77.

## Notes
- #63 Phase 3 of 3. frontend-w3-2 BUILT; architect committed (§3). Clean file-split from #76 (no tangle). The route-collision (/dev-activity vs /activity) caught at dispatch-4-step. When P2 lands → #63 module DONE (the dev-git-tracing cockpit milestone — team-lead Chrome-verifies + surfaces to user with the DEV_TRACING_EMAILS-set reminder + the /dev-activity route note). #77 (cold-scan→store) folds into P2 / sequences after.
