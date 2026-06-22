# end_sprint_119-REMINDERS-DONE-FILTER — reminders done/completed filter + doneCount + unsupported→422 (Cairn #119)

> Result. Reminders had no done/completed filter, and an unsupported filter silently fell through to 'all' (GAP-A bug — a dishonest fallback). Added: filter=done|completed (done_at NOT NULL), `doneCount` (honest-mirror sibling of undoneCount), and STRICT validation at the agent-facing surfaces (router GET + MCP) → 422/agent-error on an unsupported filter (no silent fallthrough), while the SERVICE stays store-lenient for internal callers. Commit `<hash>` `fix(sprint-119-reminders-done-filter)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT mypy + suite + router/MCP boundary check). Cairn #119 — be-only, CLOSES on this commit. Disjoint from FE #120.

## What shipped (reminders + MCP + test)
| File | Change |
|---|---|
| `reminders/service.py` | `VALID_FILTERS` (one place: today/week/undone/done/completed/all; completed=alias for done) + `is_valid_filter(key)` (empty/None→True=legit 'all' default; else strip().lower() ∈ set) + `filter_hint()`. `list` adds `doneCount = sum(r.done_at is not None)`; the done/completed filter (done_at NOT NULL). 🔴 service stays STORE-LENIENT (unknown→all) — validation is the agent-facing surfaces' job, so internal callers (brief→'undone') never 422. |
| `reminders/store.py` · `schema.py` | done filter (done_at NOT NULL) + doneCount in the list shape. |
| `reminders/router.py` | `GET /reminders` calls `is_valid_filter` FIRST → 422 agent-error + `filter_hint()` on unsupported (the strict boundary). |
| `mcp_servers/read_server.py` | `reminders_list` calls the SAME `is_valid_filter`/`filter_hint` → `agent_error("INVALID_INPUT", hint, retryable=False)` on unsupported. NO new tool → NO count-assert change. |
| `tests/test_reminders.py` (+10) | done-only/alias/honest-empty/doneCount/REST-422/REST-empty→all/MCP-parity. |

## Design (LOCKED — two-layer contract: store-lenient + agent-facing-strict)
- **🔴 the two-layer contract (the load-bearing design):** the SERVICE `list` is STORE-LENIENT (unknown filter → 'all', never raises) so internal callers (brief → 'undone', etc.) that pass known-good filters aren't forced through validation. The STRICT validation lives at the AGENT-FACING surfaces — `router GET /reminders` + MCP `reminders_list` both call `is_valid_filter` first → 422/agent-error on unsupported (honest-mirror — NO silent fallthrough to 'all', the GAP-A bug). `VALID_FILTERS` + `is_valid_filter` + `filter_hint` in ONE place → router == MCP, can't drift.
- **completed = alias for done** (both → done_at NOT NULL). empty/None filter = the legit 'all' default (NOT unsupported → not a 422).
- **doneCount** = honest-mirror sibling of undoneCount (done_at SET count); 'all' carries both.

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the two-layer split (service lenient + router/MCP strict via the shared is_valid_filter); router GET → 422+hint on unsupported; MCP reminders_list → agent_error+hint (same validation source); doneCount = sum(done_at not None); read_server adds NO new tool (verified — only the filter-validation import + agent_error → NO count-assert change). Staged #119-only (the read_server diff is #119 reminders-filter, NO #120 FE / other-lane stray). ✅
- **🔴 mypy --no-incremental (cache off, #113 lesson):** reminders → ZERO non-yaml errors. ✅
- **INDEPENDENT suite:** 152 passed (reminders + mcp_read, forward); backend: 200 reminders+mcp + FORWARD 2368/0 == REVERSE; LIVE REST (unsupported→422+hint, empty→all, seed→tick→filter=done+doneCount=1, undone excludes the done one, SCOPED cleanup id=76) + LIVE MCP after restart (#24 parity byte-identical). ✅

## 3 Gates
- **Gate 1 (API/MCP/agent):** GET /reminders + MCP reminders_list strict-validate (422/agent-error + hint on unsupported, agent-readable); doneCount honest; empty→all default; MCP≡REST parity (one validation source). ✅
- **Gate 2 (Function):** the 10 tests (done/alias/honest-empty/doneCount/REST-422/empty→all/MCP-parity) + the two-layer contract + 152 passed + mypy clean. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent; staged EXACTLY #119 (reminders + read_server + test, NO FE #120 / tracing #121-122 / data leak); commit format. read_server touched → restart for the MCP live-verify. ✅

## Assumptions (user-review)
- **unsupported filter → 422/agent-error at the agent-facing surfaces** (router + MCP), service stays lenient for internal callers. **How to change:** VALID_FILTERS / is_valid_filter (one place).
- **completed = alias for done; empty/None = the 'all' default** (not unsupported). **How to change:** is_valid_filter + the filter map.

## Notes
- Cairn #119 — be-only (the GAP-A bug half: reminders done-filter + honest unsupported-filter handling). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The two-layer contract is the standout:** strict validation belongs at the AGENT-FACING boundary (router + MCP — where an agent passes an arbitrary filter and deserves an honest 422+hint, not a silent wrong-answer), while the SERVICE stays lenient so internal callers (brief) aren't broken. One validation source (VALID_FILTERS/is_valid_filter/filter_hint) → router == MCP. **read_server.py touched** (the MCP filter-validation) → the commit needs a container RESTART for the MCP to serve new code (backend did it, stack UP); NO count-assert change → no shared-file serialization concern (#119 is the only BE lane). **Parallel-lane staging (4th clean):** committed BE-only while #120 FE was in flight (then committed) — disjoint, leak-check clean. **#121/#122 (the /daily-tracing redesign) still PAUSED** — user reshaping the spec (tracking→NOTICE/nudge + simple text+tick+remind + note-with-optional-remind, NOT hard-coded templates) → team-lead re-scopes from scratch once confirmed. Not picked up.
