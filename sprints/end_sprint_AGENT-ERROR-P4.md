# end_sprint_AGENT-ERROR-P4 — projects+career REST errors → agent_error (Cairn #46 Phase 4)

> Result. projects+career REST errors now flat agent_error (reused the P3 helper). Commit `<hash>` `fix(sprint-AGENT-ERROR-P4)`. Status: ✅ all gates pass. backend-w3 EDITED (projects+career router + tests); architect 4-step + committed (§3). ⚠️ INTENDED contract change: non-git register 400→422 (see below).

## What shipped
| File | Change |
|---|---|
| `modules/projects/router.py` | 6 raw HTTPException → agent_error_response: 5× "project not found" 404→NOT_FOUND; the ProjectError passthrough (:99) → `_PROJECT_ERR_CODE: dict[int,ErrorCode] = {400:"INVALID_INPUT", 409:"CONFLICT"}` (typed for mypy), `.get(exc.code, "INVALID_INPUT")`. RETURN not raise. Removed unused HTTPException import. |
| `modules/career/router.py` | 6 raw → agent_error_response: blog ×3 + demo ×3 bad-id 404→NOT_FOUND (hints name the real routes /career/blog + /career/demo — backend corrected the dispatch's "/career/demos" to the actual singular). Removed unused import. |
| tests | test_projects.py + test_projects_api.py (the code-map distinguishing + the 400→422 update) + test_career_backend.py (blog/demo 404 shape). |

## ⚠️ INTENDED contract change — non-git register 400 → 422
The non-git-repo register response status moved **400 → 422**: ProjectError code 400 → _PROJECT_ERR_CODE → INVALID_INPUT → _CODE_STATUS["INVALID_INPUT"]=422. This is the consistent agent-error semantic (bad-input = 422, matching the missing-field 422). The dispatch anticipated it. The 409-dup case is UNCHANGED (CONFLICT→409). **Blast radius verified safe (Rule#0):** FE api.ts has only generic 4xx handling (no hard-branch on register-400); test_projects_reader.py:399 asserts the SERVICE-layer ProjectError.code==400 (the exception attr — UNCHANGED, only the HTTP mapping moved); the 2 affected tests updated with INTENDED comments. NB for FE: if any code branches on the register-400 specifically, accept 422 now (conscious change, not a silent break).

## Design (LOCKED)
- Reused the P3 `agent_error_response` helper (the spine). projects ProjectError.code → agent_error code via a typed map (400→INVALID_INPUT, 409→CONFLICT, else INVALID_INPUT). career all NOT_FOUND. RETURN not raise.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** projects 0 raw (5 NOT_FOUND + the typed code-map at :99); career 0 raw; the 400→422 blast-radius checked (FE generic 4xx; the reader test asserts the service exc.code not the HTTP status — unaffected; 2 tests updated INTENDED); scope exactly 5 files; mypy clean.
- **backend-w3 evidence:** FULL pytest 1973/0 (baseline 1972 + 1) + mypy 0; the code-map distinguishing (non-git→422 INVALID_INPUT, dup→409 CONFLICT, bad-id→404 NOT_FOUND — an all-NOT_FOUND impl FAILS the 422/409); LIVE HTTP — all flat {error:{code}}, NO {detail}.

## 3 Gates — ALL PASS
- **Gate 1 (API):** projects+career REST errors = flat agent_error (NOT_FOUND/INVALID_INPUT/CONFLICT per case); the 400→422 is the consistent agent-error semantic (intended, verified safe). ✅
- **Gate 2 (Function):** the code-map distinguishing (3 distinct codes per case) + career 404; mypy clean (typed _PROJECT_ERR_CODE); 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (+ the 400→422 blast-radius) + backend live-HTTP; commit format; git-status clean; #46-P4-only (5 files). ✅

## Assumptions (user-review)
- **projects+career REST errors → flat agent_error** via the P3 helper. projects ProjectError.code mapped: 400→INVALID_INPUT, 409→CONFLICT. **How to change:** _PROJECT_ERR_CODE + per-route calls.
- **⚠️ non-git register status 400→422** (INVALID_INPUT) — INTENDED agent-error consistency; the service-layer ProjectError.code=400 is UNCHANGED (only the HTTP mapping). FE: accept 422 for that case now. **How to change:** _PROJECT_ERR_CODE[400] or _CODE_STATUS["INVALID_INPUT"].

## Notes
- #46 Phase 4 (P3 done; P5 journal-cluster + P6 read_server+agent_proposals+#17 pre-designed). backend-w3 EDITS; architect commits (§3). The 400→422 is the audit's one wire-status change so far — flagged for FE awareness. Next: P5 → P6 (closes #46 + #17).
