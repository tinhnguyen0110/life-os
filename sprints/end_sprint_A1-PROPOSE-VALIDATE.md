# end_sprint_A1-PROPOSE-VALIDATE — propose_* validate-at-propose-time → agent-error (Cairn #103, audit A1)

> Result. The main `write_server` propose_* tools (decision/journal/project_update/quicknote) were PROPOSALS-ONLY and enqueued the raw payload WITHOUT validating against the apply-time model. A bad field (free-string `domain`, out-of-range `confidence`, bad enum) → status=pending/applied=None/NO warning = IDENTICAL to a valid call → the agent thought it worked, but it failed LATER at human-accept with a raw pydantic error the agent never saw (deferred FALSE-SUCCESS). Fixed: `_propose` now validates the payload against the SAME apply-time Input model at propose-time → an agent-error {code,message,hint,retryable} NOW. The shaping is a SINGLE source (new `payload_builders.py`) used by BOTH propose-validation and apply → can't drift (esp the #51 journal action coercion). Commit `<hash>` `fix(sprint-A1-propose-validate): propose-time validation → agent-error not false-pending, shared payload_builders (#103)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth on the container). Cairn #103 — audit finding A1 (MED-HIGH).

## What shipped (1 new module + 3 files)
| File | Change |
|---|---|
| `mcp_servers/payload_builders.py` (NEW) | the SINGLE source of payload→Input shaping: `build_decision_input`/`build_note_input`/`build_journal_input` + `PAYLOAD_BUILDERS` map. PURE (lazy-imports ONLY the schema, NEVER a create_* fn) → gate-safe to import from write_server. The #51 journal action case-coercion ("buy"→"BUY") lives HERE (one place). |
| `mcp_servers/write_server.py` (`_propose`) | propose-time validation: build the kind's Input via PAYLOAD_BUILDERS (build-only, discard) → a ValidationError → `_payload_agent_error` returns {error:{code:INVALID_INPUT, message:<field+why>, hint, retryable:false}}; else enqueue pending (happy path unchanged). project_update (no builder) → skip (no-op-flag kind). |
| `mcp_servers/proposals_service.py` (`_apply_*`) | REFACTORED to call the SAME `build_*_input` (shaping moved OUT into payload_builders) → propose-validation + apply use ONE builder → no drift. |
| `tests/test_mcp_write.py` (+N) | bad-field→agent-error · journal "buy"→still-pending (coercion preserved) · bad-action→agent-error · valid→pending · no-mutate gate intact. |

## Design (LOCKED — single-source shaping, propose-time validation, gate-safe pure module)
- **single-source payload shaping (the anti-drift):** the load-bearing risk was that propose-time validation would use a DIFFERENT shaping than apply (esp the #51 journal "buy"→"BUY" coercion) → a NEW false-NEGATIVE (reject a valid input apply accepts) replacing the false-success. Solved by construction: ONE `build_*_input` per kind, called by BOTH `_propose` (validate-only) and `_apply_*` (validate+create). They cannot drift.
- **gate-safe pure module (the capability boundary):** write_server has a no-mutate gate (test_write_server_imports_only_enqueue_ast — it must NOT import a *.service nor proposals_service). payload_builders lives OUTSIDE the apply layer + lazy-imports ONLY the schema (never create_*) → write_server imports the pure builders, NOT the apply layer → the gate stays GREEN. (The gate firing during dev = the architecture working — backend caught it via Rule#0 + put the builders in a pure module.)
- **agent-error code = INVALID_INPUT (backend's justified deviation from the dispatched INVALID_PAYLOAD):** INVALID_PAYLOAD isn't in the agent_errors.ErrorCode closed enum; INVALID_INPUT is the canonical code → 422, retryable=False (a malformed payload is DETERMINISTIC — the agent must FIX the field, not retry the same). Per #86/#87. The message names the field + reason; the hint names the valid values. Agent-actionable.
- **A3 folded:** confidence is documented `int 0-100` (the docstring + the hint); DecisionInput already has Ge(0)/Le(100) → out-of-range int is now caught at propose-time too.

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** payload_builders is pure (schema-only lazy import); `_propose` build-only-to-validate → agent-error else enqueue; `_apply_*` call the SAME builders (single-source confirmed in the diff); the journal coercion in ONE place. ✅
- **🔴 INDEPENDENT live teeth (restart-then-call on the container):**
  - `propose_decision(confidence=999)` → agent-error {code:INVALID_INPUT, "confidence: Input should be less than or equal to 100", hint, retryable:false} — NOT pending false-success. ✅
  - `propose_decision(decision="")` → agent-error "decision: String should have at least 1 character". ✅
  - `propose_journal(action="HODL")` → agent-error "action: Input should be 'BUY' or 'SELL'". ✅
  - 🔴 `propose_journal(action="buy" lowercase)` → STILL pending (the #51 coercion preserved via the shared builder — the load-bearing drift guard). ✅
  - valid propose_decision / propose_quicknote → still pending (happy path unchanged). ✅
  - (the agent-error is nested under an `error` key — confirmed the real shape; my first predicate checked top-level + misread it, re-checked the raw output = correct.)
  - throwaway proposals cleaned up by-id (rejected — queue left clean).
- **no-mutate gate GREEN:** the capability-boundary tests (imports_only_enqueue / enqueue_ast) pass — write_server still doesn't import the apply/service layer. ✅
- **Suite:** test_mcp_write.py 24 passed; FULL DEFAULT (`-m 'not slow'` deterministic) = **2235 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2230→2235 = +5 #103 tests); never staged backend/data/.

## 3 Gates
- **Gate 1 (MCP/agent):** bad payload → agent-error {code,message,hint,retryable} (not false-pending, not raw-pydantic); valid → unchanged; the error names the field + valid values (agent-actionable). ✅
- **Gate 2 (Function):** the distinguishing teeth (bad-field→agent-error / coercion-preserved / valid→pending / no-mutate-gate); independent live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY payload_builders.py + write_server.py + proposals_service.py + test_mcp_write.py + end doc (NO A2/crud.py, no data/.env); commit format. ✅

## Assumptions (user-review)
- **propose-time validation builds the apply-time Input model** (DecisionInput/NoteInput/JournalInput) → bad payload = agent-error NOW. **How to change:** the PAYLOAD_BUILDERS map / a kind's builder.
- **error code = INVALID_INPUT, retryable=False** (malformed = deterministic fix-don't-retry). **How to change:** the _payload_agent_error code mapping.
- **single-source shaping in payload_builders.py** — propose + apply both call it (no drift). **How to change:** edit the one builder; both sides follow.
- **project_update skips propose-validation** (no apply handler — the no-op-flag kind). **How to change:** add a builder if project_update gets a real apply path.

## Notes
- Cairn #103 — audit A1 (architect read-only audit + team-lead Rule#0-pinned the real trigger = a STRING/free-field like domain, NOT the float which FastMCP catches at the arg layer). backend-w3 built; architect committed (§3 sole-committer). Two strong backend moves: (1) the shared `payload_builders.py` eliminates the coercion-drift risk by CONSTRUCTION (the load-bearing concern); (2) the no-mutate gate fired during dev → backend put the builders in a PURE module → the capability boundary held (the gate working as designed). Committed separately from #104/A2 (doc-only, different file). The agent now gets an honest, actionable error at propose-time instead of a deferred false-success.
