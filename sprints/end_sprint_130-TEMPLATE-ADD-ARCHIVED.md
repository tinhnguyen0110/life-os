# end_sprint_130-TEMPLATE-ADD-ARCHIVED — re-adding an archived template un-archives it (Cairn #130)

> Result. The #126-flagged gap: clicking "+ Từ mẫu" for a template whose id was ARCHIVED → added:false + invisible (no un-archive). Fixed: an archived matched id → UN-ARCHIVE + re-surface → (activity, added=True), SAME row (logs/history preserved). Commit `<hash>` `fix(sprint-130-template-add-archived)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live add→archive→re-add→un-archived). Cairn #130 — be-only, CLOSES on this commit. tracing — DISJOINT from #127 W1 (wiki).

## What shipped
| File | Change |
|---|---|
| `tracing/service.py` (`add_template_to_today`) | archived matched id → `store.unarchive_activity(id)` + return refreshed, added=True (same row, logs preserved); live id → existing, added=False (no dup); new id → create. add_all DELEGATES to add_template_to_today (DRY — archived semantics flow through). |
| `tracing/store.py` | NEW `unarchive_activity(id)` — `UPDATE tracing_activities SET archived=0 WHERE id=?` (SCOPED single-id, #72). |
| `tests/test_tracing_template_add.py` (+4) | archived→un-archive+same-row-no-dup / live-id-skips / logs-preserved / add-all-unarchives. |

## Design (LOCKED — "add" = "I want this today" → un-archive)
- **archived id → un-archive (decide-and-log):** clicking "+ Từ mẫu" / add = "I want this on today's board." A silently-archived id used to no-op (the FE-found gap). Now it UN-ARCHIVES the SAME row (archived=0) → logs/history preserved (not a new row). added=True (it IS now on the board).
- **live id → idempotent skip** (existing, added=False, no dup). new id → create.
- **SCOPED:** unarchive_activity is a single-id UPDATE (#72 — never blanket).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the archived→unarchive branch (same row, logs preserved); live-id→skip; add_all delegates (DRY); unarchive_activity SCOPED single-id. Staged #130 tracing-only (NO W1-wiki leak — wiki clean). ✅
- **🔴 INDEPENDENT LIVE (the distinguishing case):** add uong-nuoc → activity (added:True, archived:False); archive it (200); **re-add the archived template → added:True, archived:False** (un-archived back onto the board — the exact gap fixed). scoped cleanup. ✅
- **mypy --no-incremental clean; 18 passed** (template-add, independent); backend FORWARD 2420/0 == REVERSE; +4 tests. ✅

## 3 Gates
- **Gate 1 (API):** add → archived-id un-archives (added:true); live-id idempotent (added:false); agent-readable. ✅
- **Gate 2 (Function):** the 4 tests (un-archive+same-row / live-skip / logs-preserved / add-all) + live + mypy. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY #130 tracing (NO wiki/frontend/template leak); commit format. ✅

## Assumptions (user-review)
- **re-adding an archived template UN-ARCHIVES it (same row, logs preserved), added=True.** **Why:** "add" = "I want this today"; a no-op was the gap. **How to change:** the archived branch in add_template_to_today.

## Notes
- Cairn #130 — be-only; fixes the low-pri gap team-lead logged during #126 (template-add on an ARCHIVED activity → added:false + invisible). backend-w3 built; architect committed (§3 sole-committer). The decide-and-log: "add = I want this today" → un-archive the same row (logs preserved) rather than no-op or create-a-dup. SCOPED single-id unarchive (#72). **Parallel-lane note:** #130 is tracing — DISJOINT from #127 W1 (wiki), but ONE BE committer serial → #130 commits first, then W1 (backend's next lane). **BE queue: #130 (this) → W1 (wiki folders) → W2.** REST-only, no restart, no count-assert.
