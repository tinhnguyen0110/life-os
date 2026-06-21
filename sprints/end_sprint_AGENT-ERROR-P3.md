# end_sprint_AGENT-ERROR-P3 — finance+market REST errors → agent_error (Cairn #46 Phase 3)

> Result. finance+market REST errors now match their MCP twins (flat agent_error), via the new reusable `agent_error_response` helper (the spine for P4+). Commit `f517b29` `fix(sprint-AGENT-ERROR-P3)`. Status: ✅ all gates pass. backend-w3 EDITED (core + finance + market + tests); architect 4-step + committed (§3).

## Context
The MCP twins already returned agent_error (#46-P2). The REST routers still raised raw HTTPException(detail=str) → REST≠MCP for errors. P3 brings finance+market REST to parity (the heavily-MCP-consumed surfaces).

## What shipped
| File | Change |
|---|---|
| `core/agent_errors.py` | NEW `agent_error_response(code, message, hint, retryable)` → JSONResponse with the HTTP status from a new `_CODE_STATUS` map (NOT_FOUND→404, INVALID_INPUT→422, AMBIGUOUS/CONFLICT→409, UPSTREAM_DOWN→502, RATE_LIMITED→429). The canonical REST error helper (generalizes wiki's _note_not_found) — the reusable SPINE for P4-P6. TYPE_CHECKING JSONResponse import. |
| `modules/finance/router.py` | 5 raw HTTPException → `return agent_error_response`: holding 404 (NOT_FOUND), simulate 422×3 (INVALID_INPUT), channel 404. Removed now-unused HTTPException import. |
| `modules/market/router.py` | 9 raw → agent_error_response: asset-not-tracked ×4 (404), alert-rule/indicator-alert-asset/indicator-alert-rule/watchlist 404s, backfill 422. PLUS the raise-in-helper: `_parse_symbols` converted to a SENTINEL-RETURN `(parsed, error: JSONResponse|None)` — callers /correlation (min_n=2) + /compare (min_n=1) `return err` — mirrors the MCP _parse_symbols_mcp pattern → REST≡MCP parity. 0 raw HTTPException left. Removed unused import. |
| tests | test_agent_errors.py (helper status-map + flat-not-nested), test_finance_api.py (simulate/holding/channel agent_error shape), test_market.py (history-404 + correlation-422-sentinel). |

## Design (LOCKED)
- **The reusable `agent_error_response` helper** — one canonical REST error builder (code→status map), NOT per-module dup. P4-P6 reuse it (the audit spine). RETURN it (not raise) — a JSONResponse.
- **MCP-twin parity** — each migrated REST error now matches its MCP twin's shape (finance_simulate, market_correlation already agent_error in read_server). REST≡MCP for errors.
- **raise-in-helper solved cleanly** — `_parse_symbols` (called by 2 routes) can't `return` a Response to the client, so it returns a `(parsed, error)` sentinel + the caller returns the error. The MCP twin's exact pattern. No ugly refactor, no unconvertible site to defer.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** the helper + _CODE_STATUS correct; finance 0 raw HTTPException (5 migrated); market 0 raw (9 migrated + the sentinel-return); the 2 sentinel callers `return err`; scope exactly 6 files (no HARDENING leak); mypy clean (helper + both routers).
- **backend-w3 evidence:** 185 targeted green + FULL pytest **1971 passed / 6 skipped / 0 failed** (baseline 1967 + 4); mypy clean; LIVE HTTP curl (per verify-mcp-on-http-not-import-cache): finance/simulate empty→422 INVALID_INPUT+hint, holdings/NOPE→404, channel→404, market/correlation 1-symbol→422 (the sentinel path), market/history bogus→404 — ALL flat {error:{code,...}}, NO raw {detail}; MCP-twin parity confirmed.

## 3 Gates — ALL PASS
- **Gate 1 (API):** finance+market REST errors = flat agent_error (404/422), MCP-twin parity; envelope; the helper maps code→status. ✅
- **Gate 2 (Function):** the per-route distinguishing (flat {error:code}, NOT {detail}) + the sentinel-return path (correlation 422) + helper status-map test; mypy clean; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend live-HTTP evidence; commit format; git-status clean; #46-P3-only stage (6 files). ✅

## Assumptions (user-review)
- **finance+market REST errors → flat agent_error** (404 NOT_FOUND / 422 INVALID_INPUT) via the new `agent_error_response` helper (code→HTTP-status map). MCP-twin parity. **How to change:** the helper / _CODE_STATUS / per-route calls.
- **`_parse_symbols` sentinel-return** (the raise-in-called-helper pattern) — returns `(parsed, error)`, caller returns the error. **How to change:** the helper signature + the 2 callers.

## Notes
- #46 Phase 3 of the phased audit. The `agent_error_response` helper is the reusable spine — P4 (projects+career) / P5 (journal-cluster) / P6 (read_server+agent_proposals) reuse it (roadmap: plan_sprint_AGENT-ERROR-ROADMAP.md). backend-w3 EDITS; architect commits (§3). Next: HARDENING (#39/#40/#57) — deferred to after this. agent-first-error pillar: REST errors an agent hits = a code to branch on + a hint, matching the MCP surface.
