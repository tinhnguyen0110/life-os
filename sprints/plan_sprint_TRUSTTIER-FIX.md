# Sprint TRUSTTIER-FIX — CREATE honors trustTier (Cairn #45, reactive bug-fix)

> Created 2026-06-21 by architect. Reactive sprint (bug found while building #41 + QA). Cause CORRECTED twice (architect misdiagnosed → backend ran-the-red → team-lead refined the test-order). backend EDITS the wiki note path; architect commits (§3).

## The bug (real cause — corrected from the dispatch's assumption)
A wiki note could NEVER be born non-`verified`:
- **NoteCreateInput LACKED a `trustTier` field** → pydantic silently DROPPED `trustTier="candidate"` (no extra=forbid; a silent lie).
- **_apply_create HARDCODED `trustTier="verified"`** → never read the input.
So `create(trustTier="candidate")` → stored "verified". The original #45 framing ("NoteUpdateInput content-only resets trustTier") was a MISDIAGNOSIS — the update path is correct (None-means-skip); the symptom (a note ending up verified) came from create dropping the tier, masked in #41 tests by re-asserting the tier on every update.

## The fix (backend, confirmed)
1. `NoteCreateInput`: ADD `trustTier: TrustTier = "verified"` (default unchanged when omitted) + `model_config={"extra":"forbid"}` (an unknown kwarg now 422s — the silent-drop is what hid the bug).
2. `_apply_create`: `trustTier=inp.trustTier` (honor input, was a hardcoded literal).
3. Tests (test_wiki_trust_tier.py): create-honors-candidate; create-honors-all-fields (no silent drop); update-on-a-REAL-candidate preserves (the test that was IMPOSSIBLE pre-create-fix); update-None-preserves-each-field.

## Verifications that corrected the cause (the team's Rule#0 in action)
- architect's #41-era diagnosis (update-reset) = MISDIAGNOSIS (named the cause from the symptom).
- backend ran-the-red BEFORE fixing → found create drops it, update is correct. (run-the-red-before-naming-its-cause.)
- architect Rule#0-verified backend's repro (NoteCreateInput grep=0, hardcoded "verified", correct None-means-skip update).
- team-lead refined: the create-bug MASKS the update test (can't make a candidate to test update on) → fix create FIRST, THEN re-verify update on a now-creatable candidate.
- backend DISPROVED team-lead's shared-root-cause hypothesis (Note(**model_dump) default-fill): create + update are SEPARATE paths (create-hardcode vs update-None-skip), not one shared cause.

## extra=forbid safety (architect-verified — the one risk)
The only **-dict construction is `proposals_service:178` `NoteCreateInput(**create_payload)` (the proposal-apply path). create_payload = the propose payload ({title,content,tags} / {title,content}) + author/noteType setdefaults — ALL valid NoteCreateInput fields. So extra=forbid 422s NO existing proposal-apply. Confirmed: 285 wiki tests incl. the apply path green.

## Field-class
trustTier was the ONLY dropped field — status/noteType/tags were already in NoteCreateInput + read by _apply_create. The "class" is just the one missing field (narrower than the dispatch feared).

## Baseline
pytest 1877 (post-#41) → 1886 (+9 #45 tests). 0-failed.

## Assumptions (user-review)
- **create now honors the supplied trustTier** (default "verified" when omitted — existing behavior preserved); **extra=forbid** on NoteCreateInput (unknown kwarg → 422, never a silent drop). **How to change:** the field default / model_config in schema.py.
- update path was always correct (None-means-skip) — pinned with a regression test now that a candidate note can be created to test it on.
