# end_sprint_86-MCP-KEYS-STORE — per-key MCP scope store + CRUD (Cairn #6 T1, GATING)

> Result. The GATING store for per-key MCP tool scoping: a new `modules/mcp_keys/` module (registry auto-discovered) backs a key→scope record in `settings/mcp_keys.md` (md_store, the settings/config.md pattern but a separate LIST file) + CRUD REST + the FROZEN `get_key_scope` export #87's /mcp filter consumes. Commit `<hash>` `feat(sprint-86-mcp-keys): per-key MCP scope store + CRUD (#86, gating)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT empty-scope≠None distinction + live agent-404 + module auto-discovery). Cairn #6 T1 — blocks #87 (filter) + #88 (UI). User-greenlit 2026-06-21.

## What shipped (NEW module modules/mcp_keys/ + test — registry auto-discovered, NO main.py edit)
| File | Change |
|---|---|
| `modules/mcp_keys/service.py` (NEW) | md_store-backed store (`settings/mcp_keys.md`, YAML FM holding a `keys:` LIST, 1 commit/write, fail-open read / fail-closed write). CRUD: `create_key` (secrets.token_urlsafe(24) selector) / `list_keys` (newest-first rows) / `update_key` (partial, None→unchanged) / `delete_key` (True/False). **`get_key_scope(key)`** = the #87 gate: `{domains,tools}` if exists (empty lists if sees-nothing), else `None`. `_resolve_tool_count` = union(domain tools) ∪ (explicit tools ∩ live catalog), fail-open. |
| `modules/mcp_keys/schema.py` (NEW) | `Scope{domains,tools}` (empty=sees-nothing) · `KeyCreate{label(1-80, strip-validated), scope=default sees-nothing}` · `KeyUpdate{label?,scope?}` · `KeyRow{key,label,scope,toolCount(resolved),createdAt}`. FROZEN. |
| `modules/mcp_keys/router.py` (NEW) | CRUD at `/mcp_keys` (registry MODULE, no main.py edit). `{success,data}`; missing key on PUT/DELETE → agent_error NOT_FOUND (message names the key TRUNCATED `key[:6]…` — never echoes the full token — + hint "GET /mcp_keys"). |
| `tests/test_mcp_keys.py` (NEW, 15) | round-trip + partial-update + THE distinction (empty-scope→{[],[]} ≠ nonexistent→None, two separate tests) + toolCount (domain-union, unknown-tool-not-counted) + persistence-across-fresh-read. |

## Design (LOCKED — settings-backed list, the empty≠None contract, agent-first)
- **store:** the settings/config.md md_store pattern (YAML FM, 1 git commit/write, fail-open read / fail-closed write) but a SEPARATE `settings/mcp_keys.md` (keys are a LIST, not the singleton config). NO new db/infra layer (reuse).
- **🔴 the load-bearing contract (what #87 depends on):** `get_key_scope(key)` → `{domains,tools}` for a valid key (empty lists if sees-nothing) vs `None` for a nonexistent key. Empty-scope is a VALID sees-nothing key, NOT None. #87's 3-case filter (no-key→all / valid→scoped / invalid→error) is built on this.
- **scope = per-domain AND per-tool union** (user decided 2026-06-21): `scope.domains` (whole mount labels) ∪ `scope.tools` (explicit names).
- **store-lenient (DECIDED + logged):** an unknown domain/tool is stored as-given (forward-compat — a tool that later (dis)appears just changes the resolved count); validation is NOT a hard-fail. `toolCount` (the row) + #87's filter resolve against the LIVE catalog (store lenient, resolution honest — `test_toolcount_unknown_tool_not_counted` proves the resolution side here; #87 carries the filter-honest side).
- **agent-first:** lean rows {key,label,scope,toolCount,createdAt}; NOT_FOUND agent_error (code/message/hint/retryable) on a bad key; the full token never logged/echoed (truncated in errors).
- **no-auth:** a key is a filter-SELECTOR, not a credential (single-user). The store existing forces nothing.

## Verification (Rule#0 — architect INDEPENDENT)
- **module auto-discovery (live):** `curl /health` lists "mcp_keys" ✓; `GET /mcp_keys` → `{success:true, data:[]}` (registry prefix works, NO main.py edit).
- **architect 4-step (read FULL):** get_key_scope empty≠None correct; store mirrors settings md_store (fail-open/closed); CRUD partial-update + delete persist; toolCount resolves union ∩ catalog + fail-open; router agent_error truncates the token ✅.
- **INDEPENDENT distinction re-run (own throwaway):** empty-scope key → get_key_scope `{[],[]}` (valid, not None); a full key → its exact scope; nonexistent → None; post-delete → None. The #87 contract holds. ✅ (Did NOT trust backend's test — re-ran it.)
- **live agent-404 shape:** DELETE a nonexistent key → `{error:{code:NOT_FOUND, message:"mcp key not found: nonexi…", hint:"GET /mcp_keys for the valid keys", retryable:false}}` — agent-readable, full token NOT leaked. ✅
- **Suite:** the 15-test file green; DEFAULT (`-m 'not slow'` deterministic) = **2150 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (identical → no isolation leak; 2135→2150 = +15 mcp_keys tests); mypy clean.

## DEVIATION (decide-and-log — team-lead accepted)
- **NOT_FOUND instead of the dispatch's literal `mcp_key_not_found`:** the closed ErrorCode enum has no `mcp_key_not_found` literal; backend used canonical NOT_FOUND. ACCEPTED (team-lead, decide-and-log): enum-valid + still agent-readable (message names the key + hint + retryable:false); adding an enum value for one case = over-engineering. **Carry to #87:** the invalid-key-on-/mcp error (the user-flagged one) must still read clearly to the agent — its message+hint tell the agent "ask user to remake the key, or omit key for all tools" (the HINT is what matters to the user-flow, whatever the code).

## 3 Gates
- **Gate 1 (API):** CRUD `{success,data}`; agent_error NOT_FOUND (truncated token) on bad key; module auto-discovered; label validated (1-80, strip). ✅
- **Gate 2 (Function):** the empty≠None distinction (both sides, independently re-run); round-trip; toolCount resolution; persistence; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent distinction + live agent-404; staged set EXACTLY the new module + test + end doc (no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **store-lenient scope (unknown domain/tool stored as-given, forward-compat); resolution/filter honest (against the live catalog).** **How to change:** add a validating gate in create/update (NOT recommended — breaks forward-compat).
- **key = `secrets.token_urlsafe(24)` selector (no-auth, not a credential), never logged.** **How to change:** the `_KEY_BYTES` / generation in service.py.
- **NOT_FOUND (canonical enum) for a missing key, not a dedicated `mcp_key_not_found`.** **How to change:** add the enum literal if a distinct code is wanted (over-engineering for one case).

## Notes
- Cairn #6 T1 (GATING) — user-greenlit 2026-06-21 (un-iceboxed: per-key pushes config to the SERVER, client configs ONE endpoint+key). backend-w3 built; architect committed (§3 sole-committer). FROZEN exports (get_key_scope/list/create/update/delete) → I FREEZE-announce them, then fan out #87 (BE filter, store-lenient/filter-honest, 3 cases) ∥ #88 (FE UI) → #89 (test). Reuses the settings md_store pattern + list_tools_catalog (no new infra). Per-domain mounts STAY (additive).
