# End Sprint WRITE-LOOP-E2E — fix journal apply + lock the propose→accept→land loop

> Status: **REVIEWED — 3 gates green, committing.** Task #51. Commit hash: see `git log` (this is the sprint-WRITE-LOOP-E2E commit). The LAST backlog sprint.

## Objective (recap)
The agent write loop (`propose_*` MCP → human accept → row lands in the target module) was never exercised end-to-end (agent_proposals 0-accepted-ever). Kickoff verified it LIVE: decision_create + note_create + reject WORK, but **journal_create was BROKEN** (case-mismatch) and project_update is a deliberate documented non-handler. This sprint fixes journal + locks the whole loop with an e2e test.

## What shipped
- **`mcp_servers/proposals_service.py`** — `_apply_journal_create` now normalizes `action = cast(Action, str(payload["action"]).upper())` at the APPLY boundary before building `JournalInput`. The agent's `propose_journal` stores `action` lowercase ("buy"/"sell"); `JournalInput.action` is `Literal["BUY","SELL"]` → the raw pass-through pydantic-failed on accept → the trade never landed. The fix is minimal (apply-boundary, NOT schema-widening): `cast` only satisfies the type-checker; pydantic still validates the Literal at runtime, so a truly-bad value raises → honest apply_error, not a crash.
- **`tests/test_write_loop_e2e.py`** (NEW, 9 tests) — drives the WHOLE loop per kind, behavior-tests the SIDE EFFECT (re-GET the module): decision/note/journal LAND with DIVERGENT fields; the journal bug-killer proposes LOWERCASE "buy" → landed action=="BUY" (+ the SELL arm); project_update pinned (accept → apply_error + 0 projects rows + proposal recorded); reject applies nothing; idempotent double-accept (module count stable + applied_ref unchanged + exactly 1 accept audit row); natural REST-call (`POST /agent-proposals/{id}/accept` with no body, decided_by query param → applies, no 422).

### Verified counts (architect re-ran independently — Rule #0)
- e2e + mcp_write + mcp_read + journal: **158 passed, 0 errors**.
- Full suite: **1549 passed, 6 skipped, 0 failed, 0 errors** (1540 baseline + 9 new = 1549, matches backend), 1 benign httpx deprecation warning.
- mypy: the 5 errors in `proposals_service.py` are **PRE-EXISTING** (confirmed by stashing the fix → same 5 errors on the committed pre-fix version, at shifted line numbers). The fix introduced ZERO new mypy error (`cast(Action, ...)` correctly avoids a Literal-assignment error). Out of scope (pydantic-no-plugin false-positives on default-arg fields + a known Optional-index pattern).
- team-lead LIVE-verified incl. the DISTINGUISHING PROOF: reverted the `.upper()` fix → the 2 bug-killer tests FAILED; restored → PASS. The test genuinely catches the bug, not a happy-path false-green. REST surface showed 5 accepted/2 rejected (the loop has really run).

## Assumptions (user-review)
- **journal action normalized to uppercase at the APPLY boundary** (`_apply_journal_create`, not the journal schema) — **why:** the agent's `propose_journal` stores `action` as sent (lowercase "buy"/"sell"), but the journal's `Action = Literal["BUY","SELL"]` is uppercase-only; without normalization, accepting any journal proposal raised a validation error and the trade never landed. Normalizing at the apply boundary (vs widening the schema) keeps the REST/FE journal contract strict while making the agent loop tolerant of whatever case it sends. pydantic still validates the Literal at runtime (a non-BUY/SELL value → honest apply_error, not a crash). **How to change:** the one `.upper()` in `_apply_journal_create`; or, to also accept lowercase at the REST/FE surface, widen `Action` (not done — the agent channel is the only lowercase source).
- **project_update is an INTENTIONAL honest-defer, NOT wired to apply** — **why:** the projects module has no public partial-update service for the human-authored fields (progress/next/desc), so accepting a `project_update` proposal records an honest `apply_error` ("no apply handler") rather than fabricating a write. There is no current consumer demand for the agent to edit project fields, so building an `update_project` write path would be over-engineering (north-star). The e2e test PINS this (accept → apply_error + 0 rows) so it can't silently drift into a fabricated write. **How to change:** add `_apply_project_update` + an `update_project` service fn when a real consumer appears.

## Code review (architect — 4-step, full functions)
1. **git diff** — proposals_service +12/-2 (the normalize + imports + a doc comment), new test file. `template/`+`data/` excluded.
2. **Read full functions** — `_apply_journal_create`: `cast(Action, str(payload["action"]).upper())` then `JournalInput(action=action, ...)`. Correct — normalizes case, keeps runtime validation. Read the full e2e test: each LANDS test re-GETs the module with DIVERGENT fields; the journal test asserts the lowercase TRIGGER (`payload["action"]=="buy"`) → landed "BUY"; project_update pins apply_error+0-rows; idempotent checks count + audit; natural REST uses id-only no body.
3. **Verify against plan** — T1 journal fix (apply-boundary), T2 project_update pinned (no handler built), T3 full e2e, NG5 not touched. ✅
4. **Hunt additional issues** — none. The bug-killer uses the lowercase distinguishing fixture (team-lead independently proved its teeth by reverting). The 5 mypy errors verified pre-existing (not a regression). The fix doesn't widen the schema (REST/FE stay strict). Idempotency test even checks the audit-row count.

## The 3 Quality Gates
- **Gate 1 — API:** ☑ the accept loop applies to the module (behavior-verified) · ☑ natural REST-call shape (id + decided_by query, no body) works — no 422 · ☑ no auth · ☑ idempotent · ☑ honest apply_error on the deferred kind. **PASS**
- **Gate 2 — Function:** ☑ e2e tests assert the SIDE EFFECT (re-GET module), not the helper · ☑ DIVERGENT fields + the lowercase bug-killer · ☑ existing tests pass (full suite) · ☑ **0 errors** · ☑ edge: reject/idempotency/honest-defer · ☑ no NEW mypy error (5 pre-existing confirmed) · ☑ no self-confirming asserts. **PASS**
- **Gate 3 — Sprint:** ☑ end doc w/ verified counts · ☑ architect spot-checked full functions · ☑ counts ≥ baseline · ☑ team-lead LIVE-verified incl. the revert-the-fix distinguishing proof · ☑ assumptions logged (2) · ☑ commit format. **PASS**

## Risks / follow-ups
- The 5 pre-existing mypy errors in proposals_service.py (JournalInput default-arg false-positives + an Optional-index pattern) are tech-debt, not introduced here — a future cleanup if desired.
- **This is the LAST backlog sprint.** After it lands: MCP-HTTP + FINANCE-CORRECTNESS + FINANCE-MCP-SHAPE + WRITE-LOOP-E2E all shipped; the agent READ and WRITE loops are both verified working end-to-end. Clean checkpoint.
