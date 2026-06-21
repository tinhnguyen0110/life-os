# end_sprint_88-MCP-KEYS-UI-P2 — MCP-keys scope-editor + catalog-audit (Cairn #6 T3, part 2 — COMPLETES #88)

> Result. The `/mcp-keys` screen now offers REAL scoping: a per-domain + per-tool tick scope-editor (in create + inline per-row edit), a catalog-audit view (all 91 tools + descriptions + per-domain counts + capability boundary — the user's 2nd reason), and the connect-hint filled with the real X-MCP-Key mechanism + .mcp.json snippet. No more sees-nothing-only half-state. Commit `<hash>` `feat(sprint-88-mcp-keys-ui-p2): scope-editor + catalog-audit (#88 part-2, completes #88)`. Status: ✅ verified (frontend-w3-2 built + Chrome live; architect 4-step + INDEPENDENT scope-logic re-run + tsc + vitest). Cairn #6 T3 part 2 — COMPLETES #88. Built against #87's live catalog route (0d384b2). Blocks #89.

## What shipped (FE — scope-editor logic + component + page wiring)
| File | Change |
|---|---|
| `lib/mcpScope.ts` (NEW) | PURE scope-editor logic: toggleDomain (tick domain → all its tools; drop now-redundant explicit) · toggleTool (per-tool; un-ticking ONE of a fully-ticked domain EXPANDS to explicit-minus-one) · resolvedTools (union, deduped) · isToolSelected / isDomainSelected / toolsInDomain / groupByDomain / EMPTY_SCOPE. Display/derivation only (BE resolves the authoritative toolCount). |
| `components/McpScopeEditor.tsx` (NEW) | McpScopeEditor (per-domain + per-tool tick UI) + McpCatalogAudit (read-only: all tools + descriptions + per-domain counts + honest capabilityBoundary). |
| `lib/useMcpCatalog.ts` (NEW) | one-shot catalog fetch (alive-guard) over #87's `GET /mcp_keys/catalog`. |
| `app/mcp-keys/page.tsx` | scope-editor in the create form + inline edit-scope per row + catalog-audit toggle; connect-hint now shows the **X-MCP-Key header** + a real .mcp.json snippet (the #87 mechanism). |
| `lib/useMcpKeys.ts` | + `update` (PUT scope). |
| `lib/types.ts` | McpCatalog extended to the real shape (counts.byMount + capabilityBoundary). |
| `lib/tokens.css` | .scope-editor / .scope-domain / .scope-tool. |
| `app/mcp-keys/__tests__/mcp-keys.test.tsx` | updated for part-2 (16 tests). `lib/__tests__/mcpScope.test.ts` (NEW, 10) — the scope LOGIC. |

## Design (LOCKED — pure scope logic, real catalog, honest)
- **scope model:** `{domains, tools}` — a DOMAIN = all its tools; `tools` = explicit extras. resolved set = (∪ domain tools) ∪ explicit. The editor keeps it clean (ticking a domain drops redundant explicit; un-ticking one tool of a ticked domain expands to explicit-minus-one). PURE → unit-tested without a DOM.
- **catalog-audit = the user's 2nd reason:** all 91 tools grouped by domain, with descriptions + per-domain counts + the capability boundary (read|propose) — the user eyeballs which tools exist/are useful. Honest counts (N total, M selected).
- **connect-hint:** the real X-MCP-Key header mechanism (#87's choice) + a copyable .mcp.json snippet for `<base>/mcp/<server>/mcp`.
- **render-only / honest-mirror:** the BE computes the authoritative toolCount (the union); the FE's resolvedTools is display-only. No fabrication; the catalog is the live 91-tool payload.

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** mcpScope.ts pure logic correct (toggleDomain drop-redundant; toggleTool expand-minus-one; resolvedTools union) ✅; McpScopeEditor + audit render-only ✅; page wiring (create-scope + inline-edit + audit toggle + X-MCP-Key hint) ✅; FE-only surface (no backend/#89 intermix) ✅.
- **architect INDEPENDENT scope-logic re-run (own throwaway):** tick a 3-tool domain → un-tick ONE → resolves to EXACTLY the other 2 (not the un-ticked), domain expanded out, others kept selected. The hardest logic (expand-minus-one) is correct. ✅ (cleaned up.)
- **architect independent re-run:** tsc clean (exit 0); vitest FULL **83 files / 947 passed / 0 failed** (932→947, +15 net = mcpScope 10 + mcp-keys net 5); the flaky non-#88 fail backend flagged did NOT recur on my run (clean 947).
- **frontend-w3-2 Chrome (:3010, live catalog + CRUD):** scope-editor renders all 7 real domains; create-with-scope (tracing domain 2 + finance_overview 1 → selected-count 3 → row toolCount 3 BE-union); persists across reload value-by-value (API-confirmed {domains:[tracing],tools:[finance_overview]}); edit-scope live (+reminders → toolCount 6); catalog-audit shows all 91 tools + descriptions + "91 tool · 7 domain · 46 read / 4 propose" + capability boundary; X-MCP-Key connect-hint + correct .mcp.json; in-page delete; dark-mode; console clean. **Throwaway key created → verified → DELETED → store back to [] (no pollution).**

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest (mcpScope logic 10 incl. expand-minus-one + mcp-keys 16) + tsc clean + the independent scope-logic re-run + Chrome (create-scope/edit-scope/audit/X-MCP-Key/persist). ✅
- **Gate 3 (Sprint):** end-doc; FE-agent Chrome + architect 4-step + independent re-run; commit-hygiene (FE-only, no backend/#89 leak); commit format. ✅

## Assumptions (user-review)
- editor keeps {domains,tools} CLEAN: ticking a domain drops redundant explicit tools; un-ticking one tool of a ticked domain expands the domain to explicit-minus-one. **Why:** minimal, unambiguous saved scope. **How to change:** mcpScope.ts toggleDomain/toggleTool.
- connect-hint uses the X-MCP-Key header (the #87 mechanism). **How to change:** the connect-hint in page.tsx if #87's mechanism changes.

## Notes
- Cairn #6 T3 **part 2 — COMPLETES #88** (one coherent screen: CRUD [part-1 fce7317] + scope-editor + catalog-audit [this]). Built against #87's live `GET /mcp_keys/catalog` (0d384b2). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). FE-only surgical stage. The #6 cluster: #86 ✅ (store) · #87 ✅ (filter + catalog) · #88 ✅ (CRUD + scope-editor) · #89 (3-case test) = the LAST #6 task. After #89 → the user-CHỐT per-key MCP scoping feature is complete end-to-end (client configs ONE endpoint + ONE key; server scopes; UI to manage + audit).
