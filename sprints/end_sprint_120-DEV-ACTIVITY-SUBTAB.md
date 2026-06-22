# end_sprint_120-DEV-ACTIVITY-SUBTAB — fold Dev Activity into the Projects sub-tab (revision of #114) (Cairn #120)

> Result. #114 kept /dev-activity as a SEPARATE nav entry (then-user-CHỐT nav-IA-A). User REVISED: fold Dev Activity into the unified Projects screen as a 3rd sub-tab [Đang chạy | Nghĩa địa | Dev Activity]. Done: removed the standalone nav item, /dev-activity → redirect to ?tab=dev, DEVACT body extracted to <DevActivityView> (1:1, 40 testids). Commit `<hash>` `feat(sprint-120-dev-activity-subtab)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc + vitest 1035/0). Cairn #120 — fe-only revision of #114, CLOSES on this commit. user-CHỐT. Disjoint from #119 (BE, parallel).

## What shipped (FE — 5 mod + 1 new)
| File | Change |
|---|---|
| `lib/nav.ts` | removed the standalone `/dev-activity` "Dev Activity" nav entry. "Dự án" section = just `/projects` (label "Danh sách"). Comment documents the #114→#120 revision (separate → folded in). |
| `app/projects/page.tsx` | 3rd sub-tab "dev": `SubTab = "running"|"graveyard"|"dev"`; `?tab=dev` → `<DevActivityView>` in-page; setTab pushes ?tab=dev; the tab button (role=tab, aria-selected, data-testid=subtab-dev). |
| `app/dev-activity/page.tsx` | → REDIRECT (`router.replace("/projects?tab=dev")`) + honest interim message. Old URL/bookmarks keep working. |
| `components/DevActivityView.tsx` (NEW, 383L, 40 testids) | the DEVACT git-contribution screen body extracted 1:1 (all #97 features: range/scan/summary/loc/analyst/cpd/netloc/span/peak/velocity/yvo/...) — same extraction pattern as GraveyardView (#114). |
| tests (+2, 1033→1035) | nav (standalone Dev Activity removed), 3rd sub-tab + ?tab=dev + /dev-activity redirect. |

## Design (LOCKED — revision of #114's nav-IA, faithful extraction, scope-guarded)
- **#114 → #120 revision:** #114 decided /dev-activity STAYS separate (nav-IA-A); the user REVISED to fold it in as a 3rd sub-tab. The nav.ts comment documents the decision change honestly (no silent flip). Both /graveyard + /dev-activity routes still exist as redirects (deep-links preserved).
- **faithful 1:1 extraction:** DevActivityView carries the FULL DEVACT body (40 testids, all #97 features) — same pattern as GraveyardView's S4 extraction. Render-only; no logic change.
- **🔴 scope-guarded:** ONLY /dev-activity folded (the git-contribution screen), NOT /activity (a different screen) — the implementer correctly scoped it.

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** nav removes the standalone entry (comment documents the #114→#120 revision); 3rd sub-tab tabParam==="dev" → DevActivityView + setTab + redirect (replace, no back-trap); DevActivityView = 383L / 40 testids (the DEVACT features preserved 1:1, verified by testid grep). FE-only stage (the 6 #119 BE files left dirty + untouched — disjoint parallel lane). ✅
- **architect tsc + vitest:** tsc clean (exit 0); vitest **89 files / 1035 passed / 0 failed** (independent re-run; was 1033 → +2; tail clean). ✅
- **frontend-w3-2 Chrome :3010:** sidebar "Dự án" 1 entry (standalone Dev Activity gone), 3 sub-tabs, Dev Activity → ?tab=dev + full git view, /dev-activity → redirect, dark-mode, console clean; mock-diff 40 testids preserved. ✅

## 3 Gates
- **Gate 2 (Function):** the +2 tests (nav + 3rd sub-tab + redirect) + tsc + vitest 1035/0 + Chrome live + the 40-testid extraction preserved. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step + tsc/vitest; staged EXACTLY the 6 FE files (NO #119 BE / backend / template / data leak — the 6 BE files correctly left dirty); commit format. ✅

## Assumptions (user-review)
- **Dev Activity is now a 3rd Projects sub-tab** (?tab=dev), NOT a standalone nav item (revises #114's nav-IA-A per the new user-CHỐT). **How to change:** the nav.ts entries + the sub-tab in page.tsx.
- **/dev-activity URL redirects** to ?tab=dev (old links preserved). **How to change:** the redirect page.

## Notes
- Cairn #120 — fe-only REVISION of #114 (the user changed the nav-IA decision: /dev-activity separate → folded into the Projects sub-tab). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). **Parallel-lane staging (3rd time clean):** #120 (FE) + #119 (BE reminders) in flight in the SAME tree; staged FE-only (6 files) + left the 6 #119 BE files dirty/untouched (leak-check confirmed no BE in the staged set). The disjoint+serial pattern held across #120/#119. **#121/#122 (the bigger /daily-tracing redesign — "text + action" only, drop emoji/color/preset chips) are PAUSED** pending the user's exact spec — correctly NOT picked up. The DevActivityView extraction (40 testids) mirrors the GraveyardView (#114) pattern — the unified Projects screen now hosts all 3 project surfaces (running / graveyard / dev-activity) as sub-tabs. No restart.
