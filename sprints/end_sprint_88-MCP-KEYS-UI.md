# end_sprint_88-MCP-KEYS-UI — MCP-keys manager UI, the CRUD half (Cairn #6 T3, part 1)

> Result. The `/mcp-keys` screen: list keys · create (label) with a key-shown-ONCE banner · in-page delete confirm · connect-hint · honest loading/error/empty states — all live against #86's FROZEN CRUD. The scope-editor + catalog-audit view (the user's 2nd reason) is left as a CLEAN SEAM pending `GET /mcp_keys/catalog` (being added in #87). Commit `<hash>` `feat(sprint-88-mcp-keys-ui): MCP-keys manager screen — CRUD half + scope-editor seam (#88)`. Status: ✅ verified (frontend-w3-2 built + Chrome self-verify; architect 4-step + tsc + vitest). Cairn #6 T3 part 1 (the scope-editor half follows when the catalog REST route lands). User-greenlit 2026-06-21.

## What shipped (FE — new screen + hook + types/api/nav, NO backend)
| File | Change |
|---|---|
| `app/mcp-keys/page.tsx` (NEW) | screen MCPKEYS — connect-hint (real endpoint `<base>/mcp/<server>/mcp` + key-passing PLACEHOLDER pending #87) · create form (label) · **key-shown-ONCE banner** (full token once, copy + dismiss, "won't show again") · key list (label + BE toolCount + scope summary + relative createdAt) · **in-page delete confirm** (NOT JS confirm() — doesn't block the extension) · loading skeleton (.sk-line) · error+retry · honest empty-state · **scope-editor SEAM** (`data-testid="scope-seam"` placeholder honestly stating "key sees nothing until scoped"). RENDER-ONLY (BE computes toolCount). |
| `lib/useMcpKeys.ts` (NEW) | list + create + remove; fail-CLOSED writes (throw→caller surfaces) + refetch-after-write; alive-guard drops a stale list response; honest-empty []. The scope-editor needs NO hook change (create/update already accept a full scope). |
| `lib/api.ts` | getMcpKeys/createMcpKey/updateMcpKey/deleteMcpKey + getMcpCatalog (⚠️-noted: the catalog REST route is being added in #87). |
| `lib/types.ts` | McpScope/McpKey/McpKeyCreate/McpKeyUpdate/McpCatalogTool/McpCatalog — mirror the FROZEN #86 schema (+ a real probe row). |
| `lib/nav.ts` + `nav.test.ts` | /mcp-keys (screen-id MCPKEYS, unique) under "Hệ thống" + CRUMB; nav size 29→30. |
| `lib/tokens.css` | `.key-once-token` (the once-shown token style). |
| `app/mcp-keys/__tests__/mcp-keys.test.tsx` (NEW, 11) | the CRUD + key-once + in-page-delete + empty/error states. |

## Design (LOCKED — CRUD half live, clean seam, honest)
- **render-only:** the BE owns the store + computes toolCount (the resolved union); the FE displays. No client recompute.
- **key-shown-ONCE:** the full token appears exactly once (the create response row); after dismiss it's gone (only label+scope remain in the list). Matches the no-credential-but-don't-re-expose intent.
- **in-page delete confirm** (NOT `window.confirm()` — the browser-automation note: a JS dialog blocks the Chrome extension). The Chrome verify asserts the confirm spy was NOT called.
- **honest-mirror:** did NOT fabricate a catalog (FE refused a placeholder — the catalog is MCP-only until #87's REST route). Created keys are sees-nothing (scope {[],[]}) → toolCount renders "0 tool" honestly until scoped.
- **scope-editor SEAM:** create/update already accept a full `scope`; the per-domain(`server`)+per-tool tick + catalog-audit drops into the `scope-seam` placeholder when `GET /mcp_keys/catalog` (#87) lands — NO hook/api change needed.
- **connect-hint:** real endpoint shown; the key-passing mechanism (query vs header) is a placeholder + note pending #87's choice; the .mcp.json snippet fills in then.

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **frontend-w3-2 Chrome (:3010, live CRUD):** create → key-once banner shows the full 32-char token ONCE + new row appears; row = label + "0 tool" (honest sees-nothing) + scope "domain:— · tool:—"; **delete = in-page confirm** (window.confirm spy NOT called); cancel works; confirm deletes → back to empty; nav MCP Keys under "Hệ thống" active; dark-mode (rgb(10,10,12)); console clean; no NaN/null/undefined; BE-down + malformed-body → honest error states. **Created a throwaway key, verified, then DELETED it — store confirmed back to [] at the API (no pollution).**
- **architect 4-step (read FULL):** page.tsx (key-once / in-page-delete / seam / honest states / render-only) ✅; useMcpKeys (fail-closed, alive-guard, honest-empty, no-change-needed-for-editor) ✅; api fns mirror FROZEN #86 + the ⚠️-catalog note ✅; FE-only surface (the dirty backend/main.py + mcp_keys/filter.py are #87 in-flight — staged OUT) ✅.
- **architect independent re-run:** tsc clean (exit 0); vitest FULL **82 files / 932 passed / 0 failed** (921→932, +11 mcp-keys); the #88 tests (nav 8 + mcp-keys 11) green.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest 932/0 + tsc clean + the CRUD/key-once/in-page-delete/empty-error tests + Chrome self-verify (key-once, in-page-delete-no-dialog, dark-mode, console-clean). ✅
- **Gate 3 (Sprint):** end-doc; FE-agent Chrome + architect 4-step; commit-hygiene (FE-only — the #87 BE files staged OUT, no leak); commit format. ✅

## Assumptions (user-review)
- `/mcp-keys` under "Hệ thống" nav group (settings-area). **How to change:** nav.ts.
- created keys default to sees-nothing (scope {[],[]}) until the scope-editor lands; the user scopes them after. **How to change:** N/A (the editor — #88 part 2 — adds the per-domain/per-tool tick).
- the connect-hint key-passing is a placeholder pending #87's query-vs-header choice. **How to change:** fill the .mcp.json snippet once #87 lands.

## Notes
- Cairn #6 T3 **part 1** (the CRUD half). frontend-w3-2 built the unblocked 60% (list/create/delete/connect-hint/types/tests) against live #86 CRUD + left a clean scope-editor seam, after FE honestly flagged the catalog blocker (list_tools_catalog is MCP-only → no REST → can't render the scope-editor without fabricating). The catalog REST route (`GET /mcp_keys/catalog`) folded into #87; **#88 part 2 (the scope-editor + catalog-audit) follows when #87's catalog route lands** — drops into the seam, no hook/api change. Committed from an intermixed tree (#87 BE in-flight) — FE-only surgical stage, no leak. The full user-CHỐT #6 cluster: #86 (store) ✅ · #87 (filter + catalog) in-flight · #88 (UI: CRUD ✅, scope-editor pending catalog) · #89 (test) after.
