# end_sprint_TRUSTTIER-FIX — CREATE honors trustTier (Cairn #45)

> Result. Reactive bug-fix. Commit `<hash>` `fix(sprint-TRUSTTIER-FIX)`. Status: ✅ all gates pass. backend EDITED (wiki note path); architect 4-step + committed (§3).

## What shipped
| File | Change |
|---|---|
| `modules/wiki/schema.py` | NoteCreateInput +`trustTier: TrustTier = "verified"` (was MISSING → silently dropped) + `model_config={"extra":"forbid"}` (unknown kwarg → 422, not a silent drop). |
| `modules/wiki/service/apply.py` | `_apply_create`: `trustTier=inp.trustTier` (honor input; was a hardcoded `"verified"` literal). |
| `tests/test_wiki_trust_tier.py` (NEW) | create-honors-candidate; create-honors-all-fields (no silent drop); update-on-a-REAL-candidate preserves (impossible pre-fix); update-None-preserves-each-field. |

## The bug + the corrected cause
A note could never be born non-`verified`: NoteCreateInput lacked trustTier (silently dropped) + _apply_create hardcoded "verified". The dispatch's "update-reset" framing was a misdiagnosis — update is correct (None-means-skip); the symptom came from create dropping the tier.

## Verification (Rule#0 — the team's multi-directional catch)
- **architect 4-step:** the diff is minimal + correct (honor input, +field, +extra=forbid); the **extra=forbid blast-radius verified safe** — the only **-dict construction (proposals_service:178 NoteCreateInput(**create_payload)) carries only valid keys (propose payload + author/noteType setdefaults), so NO existing proposal-apply 422s; git-status-after-stage zero left-dirty; #45-only.
- **backend:** 1886 passed / 0 failed (1877 +9); mypy clean; 285 wiki tests incl. the proposal-apply path green (extra=forbid didn't break it); LIVE — POST trustTier=candidate → candidate; content-only PUT → STAYS candidate; POST bogusField → 422; throwaway cleaned up.
- **team-lead:** repro'd both paths; refined the fix-order (create-first, the create-bug masks the update test).

## 3 Gates — ALL PASS
- **Gate 1 (API):** create honors trustTier; extra=forbid → 422 on unknown (verified safe on the apply path); envelope intact. ✅
- **Gate 2 (Function):** the distinguishing tests (create-candidate→IS-candidate; update-on-real-candidate→STAYS; all-fields-no-drop; update-None-preserves); 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (extra=forbid blast-radius checked) + backend + team-lead; commit format; git-status-clean; #45-only. ✅

## Assumptions (user-review)
- **create honors the supplied trustTier** (default "verified" when omitted); **extra=forbid** on NoteCreateInput (unknown kwarg → 422, never a silent drop — a dropped field is a silent lie). **How to change:** schema.py field default / model_config.
- update path was always correct (None-means-skip) — now pinned with a regression test (testable since create can make a candidate).
- trustTier was the ONLY dropped field (status/noteType/tags already honored) — the class is the one missing field.

## Process note (the value of run-the-red + Rule#0)
The cause was corrected THREE times by verification: architect's symptom-based misdiagnosis (update-reset) → backend's run-the-red (create drops it) → team-lead's refinement (create masks the update test, fix create first) → backend disproving the shared-root-cause hypothesis. Each catch was verify-then-correct, never defend. The fix landed precisely right because nobody trusted a claim without running it.

## Notes
- Reactive bug-fix; backend EDITS wiki note path, architect commits (§3, the locked editor≠committer distinction). Pipeline: ✅#34 ✅#33 ✅#41 ✅#45 → #42 (project-memory, last in backend's queue) → #46-Phase1.
