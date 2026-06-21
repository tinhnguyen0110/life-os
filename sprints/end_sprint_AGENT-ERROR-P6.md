# end_sprint_AGENT-ERROR-P6 — FINAL phase, #46 PARENT CLOSED (Cairn #46 + #67)

> Result. The LAST raw errors migrated → **#46 PARENT CLOSED: every agent-facing MCP+REST error in the app is now flat agent_error.** Commit `eb96a4d` `fix(sprint-AGENT-ERROR-P6)`. Status: ✅ all gates pass. backend-w3 EDITED (5 routers + 4 tests); architect 4-step + committed (§3). Closes #46 parent + #67.

## What shipped (21 sites — the completeness-grep caught 1 my enumeration missed)
| File | Change |
|---|---|
| `modules/wiki/router.py` (13) | note/conflict-resolve(×2)/merge-NoteNotFound/proposal-not-found(×3) → NOT_FOUND; MergeError/RefineGateError/ApplyError → INVALID_INPUT; AlreadyDecided(×2) → CONFLICT. HTTPException import removed. Stale module docstring fixed ("Errors via HTTPException" → the agent_error shape). |
| `modules/agent_proposals/router.py` (4) | get/audit/accept/reject unknown id → NOT_FOUND. |
| `modules/automation/router.py` (2) | patch+run unknown routine → NOT_FOUND (hint /routines). |
| `modules/activity/router.py` (1) | unknown run id → NOT_FOUND (hint /activity). |
| `modules/macro/router.py` (1) | ⚠️ **MISSED in the dispatch enumeration** — the `detail=` sat on a continuation line so a one-line `grep \| wc` read it as 0. Caught by backend's MULTI-LINE completeness-grep, migrated + test strengthened. (The lesson: enumerate with a multi-line grep, not `grep \| wc`.) |
| tests | test_macro, test_automation_api, test_agent_proposals_apply, test_wiki_proposals. |

## read_server :837 `_section` — LEFT AS-IS (the corrected mislabel, additive declined)
My dispatch mislabeled :837 "feed-error → UPSTREAM_DOWN retryable=True (the audit's only retryable)". backend's Rule#0 caught it: :837 is `_section()`, life_brief's fail-soft section-builder (catches any exc per brief section → `{source, error}` so the brief still 200s). The `{source, error}` shape is LOAD-BEARING (test_mcp_e2e:65 + 3 unit tests assert every section carries `source`; agent_error drops top-level source → breaks them). It's a degraded-section marker in a SUCCESSFUL brief, NOT an operation-error result; the exc can be deterministic → UPSTREAM_DOWN+retryable=True would mislabel. **LEFT as-is** (already agent-readable + a different contract — the fail-closed-write-fail-soft-addon pattern + the #46-P1 found:False/degraded ≠ agent_error distinction). The ADDITIVE retryable-signal option: DECLINED (speculative — the failure isn't always upstream; the agent reads source+error already). **CONSEQUENCE: no retryable=True site exists in the current surface — all errors are deterministic → retryable:False. A real retryable error (rate-limit/transient-upstream) when added later will be the first retryable=True.**

## #46 PARENT close proof (the completeness check)
- `grep -rn "raise HTTPException" modules/ mcp_servers/` (excl agent_errors) → **EMPTY** (architect re-verified). Every router error in the app is flat agent_error.
- Remaining `detail=` (market:319 a routine-RESULT data field, wiki:29 a docstring) = NON-errors. Remaining free-text `{"error":...}` (batch-apply rows, backfill summaries, activity error-count, _section fail-soft) = per-item/data shapes, correctly NOT error envelopes.
- Raw body/path 422 still FastAPI `{detail:[...]}` → the #24 follow-up (app-level RequestValidationError handler), out of scope, tracked.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** completeness-grep 0 raw HTTPException (re-verified — #46 parent done); the missed macro site migrated; :837 untouched ({source,error} intact); wiki content-diff P6-ONLY (no earlier-sprint #53/#61/#14 bleed — it's a shared accumulator, content-diffed per commit-content-diff-not-just-filenames); CONFLICT branch present; retryable=True grep EMPTY (all deterministic, invariant holds); scope exactly 9 P6 files.
- **backend-w3 evidence:** FULL pytest 1973/0 + mypy 0 (148 files); LIVE HTTP — macro/routines/activity/agent-proposals/wiki bad-id → 404 NOT_FOUND flat {error}; the CONFLICT distinguishing (proposal reject→accept-rejected → 409 CONFLICT, NOT applied — appliedRef=None, zero vault write); all flat top-level {error}, no {detail}, all retryable:false.

## 3 Gates — ALL PASS
- **Gate 1 (API):** ALL agent-facing MCP+REST errors flat agent_error (the parent milestone); NOT_FOUND/INVALID_INPUT/CONFLICT per case; retryable:false invariant. ✅
- **Gate 2 (Function):** the CONFLICT distinguishing (accept-rejected→409, not-applied) + per-cluster NOT_FOUND; retryable:false (none wrongly True); mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (completeness-grep + wiki content-diff) + backend live-HTTP; commit format; git-status clean; #46-P6-only (9 files). ✅

## Assumptions (user-review)
- **#46 PARENT CLOSED**: every agent-facing MCP+REST error → flat agent_error {code,message,hint,retryable}. All deterministic → retryable:false (no retryable:true site exists yet). **How to change:** add a retryable error (rate-limit/transient) → first retryable:true.
- **read_server :837 _section LEFT as-is** (degraded-section marker in a 200 brief, source-load-bearing — NOT an operation error). Additive-retryable DECLINED (speculative). **How to change:** if a brief section's failure is ever known-retryable, enrich additively (keep source+error, add code/retryable).
- the missed-macro lesson: enumerate raw errors with a MULTI-LINE grep (`grep -rn` then read), not `grep | wc` (continuation lines hide).

## Notes
- **#46 PARENT + #67 CLOSED** — the audit milestone: every agent-facing error across MCP + REST is now agent-readable (a code to branch on + a hint + retryable), via the reusable agent_error/agent_error_response spine. The arc: P1/P2 (read_server) → #61/#14 (wiki note-id) → P3 (finance+market) → P4 (projects+career) → P5 (journal-cluster) → P6 (everything remaining). backend-w3 EDITS; architect commits (§3). Next: #65 Daily Tracing (awaiting user approval) + #24 (path/body-validation-422 follow-up).
