# end_sprint_129-CATALOG-PARAMS — tool catalog +fullDescription +params (Cairn #129-BE)

> Result. The MCP tool catalog (`list_tools_catalog`) gained per-tool `fullDescription` (the full docstring) + `params:[{name,type,required,default?}]` (from inspect.signature + type hints) so the user (in /mcp-keys, #129-FE) knows what each tool does + how to call it. ADDITIVE (existing fields + count-asserts intact). Commit `<hash>` `feat(sprint-129-catalog-params)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT no-write-gate-test + live param sample + parity). Cairn #129-BE — be-only, CLOSES on this commit. FREEZE done → unblocks the merged /mcp-keys FE (#128+#129-FE). Disjoint from #131 (FE, parallel).

## What shipped
| File | Change |
|---|---|
| `mcp_servers/read_server.py` (+62) | `_full_doc(fn)` (full `fn.__doc__`, dedented) + `_params_of(fn)` ([{name,type,required,default?}] from inspect.signature + get_type_hints; skips *args/**kwargs; required = no-default; type = resolved hint, fall back to raw annotation). Each catalog entry +`fullDescription` +`params`. |
| `tests/test_mcp_read.py` (+61) | 5 new incl 🔴 `test_catalog_params_derived_no_write_leak` + param-shape (project_dev_activity → project_id req + days int=90) + no-arg → params:[] + fullDescription = full doc + parity. |

## Design (LOCKED — additive, metadata-only, honest, derived-from-live)
- **ADDITIVE:** +fullDescription +params on each entry; the existing fields (name/server/capability/neutral/description) + `counts` + the count-asserts UNCHANGED (no new tool → no count change). The shape is FROZEN for #129-FE.
- **🔴 metadata-only (the no-write gate holds):** `_params_of` uses `inspect.signature(fn)` + `get_type_hints(fn)` — reads the SIGNATURE OBJECT, NEVER calls fn; `_full_doc` reads `fn.__doc__`. So building the catalog (now reading signatures too) binds/calls NO write fn — the no-write gate stays pristine (the catalog is the agent's self-discovery index; it must never reach a write).
- **honest:** no-arg tool → `params: []` (not omitted); NO per-param `description` (the docstring param-section isn't reliably parseable → omit rather than fabricate — the honest-mirror).
- **derived-from-live-signature:** can't drift from the actual tool signature (no hard-coded param lists).
- **REST≡MCP parity:** the catalog is exposed via MCP `list_tools_catalog` AND `GET /mcp_keys/catalog` (the #88 wrapper returns list_tools_catalog()) → both carry the new fields byte-identical (98 tools).

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** `_params_of`/`_full_doc` are metadata-only (inspect.signature reads the sig object, no fn call — confirmed in the code + comment); additive (existing fields/counts untouched); required/default/type derivation correct. Staged #129-BE BE-only (the #131 FE files left dirty — disjoint parallel). ✅
- **🔴 the no-write-gate test — RAN IT MYSELF (must stay green):** `pytest -k "no_write or leak or catalog_params"` → **9 passed** (the namespace-leak + the new catalog-params-no-write-leak). The signature-read introduces no write-symbol binding/call. ✅
- **🔴 LIVE param sample (REST, hot-reloads):** `GET /mcp_keys/catalog` → project_dev_activity `params=[{project_id,str,required:true},{days,int,required:false,default:90}]` (correct required/default/type); insights (no-arg) `params:[]` (honest-empty); fullDescription len=752 (full doc, not line-1). 98 tools. ✅
- **mypy --no-incremental clean; 133 passed** (mcp_read + mcp_keys, independent); backend FORWARD 2416/0 == REVERSE; NO count-assert change (additive). ✅

## 3 Gates
- **Gate 1 (MCP/agent):** catalog +fullDescription +params (agent-readable self-discovery — an agent now knows how to CALL each tool, not just its name); honest params:[]; REST≡MCP parity. ✅
- **Gate 2 (Function):** the 5 tests (params-derived + no-write-leak + no-arg-empty + fullDesc + parity) + the no-write-gate green (ran myself) + live sample + 133 passed + mypy. NOT self-confirming (the no-write-leak test + the live param sample are the real surfaces). ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent no-write-gate + live; staged EXACTLY #129-BE (read_server + test, NO #131 FE / template leak); count-asserts UNCHANGED (additive); commit format. read_server touched → RESTART for the MCP surface. ✅

## Assumptions (user-review)
- **catalog +fullDescription (full docstring) + params (from inspect.signature), no per-param description** (honest — not fabricated from an unparseable docstring). **How to change:** _params_of (add a docstring param-section parser if a reliable format is adopted).
- **params metadata-only** (inspect.signature, no fn call) → the no-write gate holds. **How to change:** n/a (the gate is load-bearing — never call a tool fn to build the catalog).

## Notes
- Cairn #129-BE — be-only user-CHỐT (each MCP tool needs a description + call-params so the user knows). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The no-write-gate is the load-bearing constraint** (the catalog is the agent's self-discovery index across read+write servers — it must NEVER reach a write fn): the params come from `inspect.signature` which reads the signature object WITHOUT calling the fn, so the gate stays pristine — VERIFIED by running the no-write-leak test myself (9 passed) + the new test_catalog_params_derived_no_write_leak. **honest params** (no fabricated per-param desc; no-arg → []). **REST path = `GET /mcp_keys/catalog`** (NOT /mcp-keys/tool-catalog — relayed to #129-FE). **Parallel-lane staging (11th clean):** committed BE-only while #131 FE in flight — disjoint, leak-check clean. **read_server TOUCHED → RESTART for the MCP surface** (backend did it; team-lead live-verifies post-push-restart). **FREEZE done → the merged /mcp-keys FE (#128+#129-FE) unblocks** — dispatch after #131. REST hot-reloads; the MCP needs the restart.
