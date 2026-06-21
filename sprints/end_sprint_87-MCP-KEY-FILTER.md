# end_sprint_87-MCP-KEY-FILTER — /mcp key-aware tool filter + catalog REST route (Cairn #6 T2)

> Result. A client configs ONE /mcp endpoint + ONE optional `X-MCP-Key` header; the server narrows which tools that key sees — the 3 user cases: no-key→ALL · valid-key→scoped subset · invalid-key→agent-readable NOT_FOUND. + the folded-in `GET /mcp_keys/catalog` REST route (unblocks #88's scope-editor). Commit `<hash>` `feat(sprint-87-mcp-key-filter): /mcp key-aware tool filter + catalog REST route (#87)`. Status: ✅ verified (backend-w3 built; architect 4-step led with the main.py wiring + filter.py read + INDEPENDENT 3-case LIVE curl on the container + filter-honest + catalog byte-identical). Cairn #6 T2 — depends on #86 (get_key_scope), unblocks #88-part-2 + #89.

## What shipped (filter + main.py wiring + catalog route + test)
| File | Change |
|---|---|
| `modules/mcp_keys/filter.py` (NEW) | the PURE 3-case filter: `allowed_tool_names(key)` → None (no-key=all, case 1) / scoped set (case 2; empty-scope→set()) / raises `KeyNotFound` (case 3). `resolve_scope` = union(domain tools in LIVE catalog) ∪ (explicit ∩ catalog names) — **filter-honest** (phantom skipped). `mcp_key_asgi_middleware` reads `X-MCP-Key` → request ContextVar + short-circuits case-3 with the agent-readable NOT_FOUND JSON (404) before FastMCP. `install_tool_filter` overrides each server's `list_tools` to filter by the ContextVar. |
| `main.py` | (a) `install_tool_filter(srv)` on each MCP server BEFORE `streamable_http_app()` (the override is the registered tools/list handler); (b) `app.mount(path, mcp_key_asgi_middleware(sub))` wraps each MCP mount. `if mcp_servers:` guards the test-skip path. NO module-registration change (registry still auto-discovers). |
| `modules/mcp_keys/router.py` | + `GET /mcp_keys/catalog` (folded in from #88's blocker) — REST wrapper over `read_server.list_tools_catalog()`, byte-identical (REST≡MCP #24). Declared ABOVE the `/{key}` routes so the static path isn't captured as a key. |
| `tests/test_mcp_keys_filter.py` (NEW) | the 3 cases PURE (case1 None/empty/whitespace→all · case2 domain/explicit/union exact · case3 raise + agent-readable body) + store-lenient/filter-honest (phantom skipped) + empty-scope→zero. |

## Design (LOCKED — the chosen injection point, the 3 cases, two-layer honesty)
- **🔴 THE design question solved EMPIRICALLY (the risk I flagged):** each MCP mount is a FastMCP `streamable_http_app()` sub-app. The chosen injection (logged): key as the **X-MCP-Key header** (leaner than ?key=, not in URL/logs); an **ASGI middleware** wrapping each mount reads it into a **request-scoped ContextVar**; each server's **list_tools is overridden** to filter by that ContextVar. backend verified the ContextVar PROPAGATES across the anyio/stateless_http boundary EMPIRICALLY on live HTTP (not guessed) — and I independently re-confirmed it (3-case live curl below).
- **the 3 cases (user-EXACT):** no-key (absent/empty/whitespace→None)→ALL tools (byte-identical no-regression); valid→scoped subset; invalid (get_key_scope→None)→`KeyNotFound`→agent-readable NOT_FOUND (404) short-circuited in the middleware BEFORE FastMCP. None (all) vs set() (empty-scope sees zero) vs raise (case 3) — three distinct outcomes.
- **store-lenient / filter-honest:** the #86 store keeps an unknown scoped tool as-given; this filter resolves against the LIVE catalog + returns ONLY tools that EXIST (phantom skipped, no error). One source of truth (same resolution as #86's _resolve_tool_count).
- **agent-readable error:** message carries the user-flow + hint ("create/fix the key, or omit for all tools"); code = enum-bound NOT_FOUND (team-lead's ruling — the agent-readability is in message+hint); the token TRUNCATED (never echoed).
- **catalog route:** byte-identical REST wrapper over the existing MCP fn; route-ordered before /{key}.

## Verification (Rule#0 — architect INDEPENDENT, led with the wiring + LIVE curl)
- **🔴 read the FULL main.py wiring + filter.py first:** the install_tool_filter-before-streamable + the ASGI-middleware-wrap are MCP-mount wiring (not module-registration); the no-key path is byte-identical (ContextVar None→all) ✅.
- **INDEPENDENT 3-case LIVE curl (restart-then-curl on the container — the ContextVar runtime risk, NOT import-cache):**
  - CASE 1 no-key → **46 tools** (full read mount, no regression) ✅
  - CASE 2 finance-key → **EXACTLY 15 finance tools, nothing else** ✅
  - CASE 2b empty-scope key → **0 tools** (valid sees-nothing, distinct from case 3) ✅
  - CASE 3 bogus key → **HTTP 404** + `{code:NOT_FOUND, message:"the MCP key 'bogus-…' is not recognized", hint:"...create/fix... or omit...", retryable}` — NOT all-tools, NOT 500, token truncated ✅
- **INDEPENDENT filter-honest:** a key scoping {finance_overview, PHANTOM} → resolved to {finance_overview} only (phantom skipped, no error) ✅.
- **catalog route LIVE:** `GET /mcp_keys/catalog` → 91 tools + counts (read/write/total/byMount/...), self-describing rows ({name,server,capability,neutral,description}), REST≡MCP byte-identical ✅.
- **Suite:** the filter test file 16 passed; DEFAULT (`-m 'not slow'` deterministic) = **2166 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2150→2166 = +16 filter tests); test keys cleaned up (no pollution).

## 3 Gates
- **Gate 1 (API/MCP):** the 3 cases agent-correct (no-key all / valid scoped / invalid agent-readable-404); catalog REST≡MCP; no-key no-regression; the error code enum-valid + message/hint carry the user-flow; token never echoed. ✅
- **Gate 2 (Function):** the PURE filter 3-case + filter-honest + empty-scope tests; independent live 3-case curl; ContextVar propagation confirmed live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step led with the wiring + live curl; staged set EXACTLY filter.py + main.py + router.py + test + end doc (NO frontend — #88 separate; no data/.env/template); commit format. ✅

## Assumptions (user-review)
- **key = X-MCP-Key HEADER** (not ?key=) — leaner, not in URL/logs. **How to change:** HEADER_NAME + the middleware read in filter.py.
- **empty/whitespace key → treated as no-key (all tools)**, not an error. **How to change:** _normalize_key in filter.py.
- **case-3 code = NOT_FOUND (enum-bound)**; the agent-readability is in message+hint. **How to change:** add a dedicated ErrorCode enum literal if a distinct code is wanted (over-engineering for one case — team-lead ruled).
- **filter-honest:** a phantom scoped tool is silently skipped (no error). **How to change:** add a warning surface if the agent should be told a scoped tool vanished (nice-to-have).

## Notes
- Cairn #6 T2 — depends on #86 (get_key_scope, landed 7503403). The design question (key-injection on the FastMCP streamable-http mounts) was dispatched as solve-with-guidance + solved correctly + EMPIRICALLY (ContextVar propagation verified live, not guessed). The catalog route folded in (from #88's honest blocker) → **unblocks #88-part-2 (the scope-editor + catalog-audit) the moment this lands.** backend-w3 built; architect committed (§3 sole-committer). Committed from an intermixed tree (#88-part-1 already landed fce7317) — BE-only surgical stage. Next: FE does #88-part-2 (scope-editor into the seam) → #89 (3-case test). The #6 cluster: #86 ✅ · #87 ✅ · #88 (part-1 ✅, part-2 next) · #89 after.
