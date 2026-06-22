# end_sprint_128-129-MCP-KEYS-POLISH-TOOLDETAIL — /mcp-keys polish + tool-detail (Cairn #128 + #129-FE, merged)

> Result. ONE /mcp-keys FE pass merging two user-CHỐT asks: #128 polish (mask key VALUES + layout/dark-mode consistency) + #129-FE tool-detail (each tool row expandable → fullDescription + a params table, from the #129-BE catalog). Commit `<hash>` `feat(sprint-128-129-mcp-keys-polish-tooldetail)`. Status: ✅ verified (frontend-w3-2 built + Chrome; architect 4-step + tsc + vitest 1053/0 + the scope-math-untouched guard). Cairn #128 + #129-FE — fe-only, CLOSES both on this commit → completes the user-CHỐT batch. Disjoint from any BE.

## What shipped (FE — merged, 6 files)
| File | Change |
|---|---|
| `lib/types.ts` | `McpCatalogTool` +`fullDescription: string` +`params: {name,type,required,default?}[]` (mirror the #129-BE FROZEN catalog shape). |
| `components/McpScopeEditor.tsx` | #129 — each tool row EXPANDABLE: collapsed = 1-line label; ⓘ → a shared `ToolDetail` body (fullDescription in a `<pre>` + a params TABLE Tham số·Kiểu·Bắt buộc·Mặc định); no-arg → "không tham số" (honest-empty); ⓘ stops-propagation (expand ≠ tick). RENDER-ONLY — the scope math stays pure (lib/mcpScope UNTOUCHED). |
| `app/mcp-keys/page.tsx` | #128 — 🔴 the just-created key VALUE is MASKED by default (`maskKey`) + 👁 reveal-on-demand + copy-without-reveal (security hygiene); cleaner scope-grid; tool-detail consistent w/ /projects+/tracing. |
| `lib/tokens.css` | tool-detail panel + mask + polish tokens. |
| `mcp-keys.test.tsx` (+) · `mcpScope.test.ts` (+ additive fixture fields) | the +4 tests + the catalog fixtures gain fullDescription/params (additive, no assertion weakened). |

## Design (LOCKED — polish-only, tool-detail render-only, key-mask, scope-math untouched)
- **🔴 scope-math UNTOUCHED (the OUT-of-scope guard):** lib/mcpScope.ts is NOT modified (verified — only its TEST gained additive fixture fields). The McpScopeEditor is RENDER-ONLY against the catalog; #128 is polish, #129-FE is display — neither touches the scope computation.
- **key-mask (security):** the created key value is masked by default, 👁 reveal-on-demand, copy works without on-screen reveal (the clipboard, never the screen).
- **tool-detail (render-only, honest):** expandable rows → fullDescription + params table; no-arg → "không tham số" (honest-empty, not omitted); ⓘ stops-propagation so expand ≠ tick-the-scope.
- **all #88 features KEPT** (inverted mock-diff): LIST/CREATE/EDIT-scope/DELETE/connect-hint/scope-grid/in-page-confirm — the polish + tool-detail are ADDED, nothing dropped.

## Verification (Gate-2 FE — frontend-w3-2 Chrome + architect 4-step)
- **architect 4-step (read FULL):** 🔴 **lib/mcpScope.ts UNTOUCHED** (the scope-math guard — only the test gained additive fixture fields, no assertion weakened); McpScopeEditor = UI/tool-detail render-only (the ToolDetail body, no scope logic); the params table (Tham số·Kiểu·Bắt buộc·Mặc định) + no-arg "không tham số"; maskKey + reveal-on-demand + copy-without-reveal. FE-only stage (BE clean). ✅
- **tsc clean; vitest 89 files / 1053 passed / 0 failed** (independent; +4). ✅
- **frontend-w3-2 Chrome :3010:** finance_channel → fullDesc + params [channel|str|có|—]; project_dev_activity → [project_id|str|có|—][days|int|không|90]; no-arg → "không tham số"; create key → MASKED + 👁 reveal + re-mask; scope CRUD intact; console clean; inverted mock-diff (#88 kept). ✅

## 3 Gates
- **Gate 2 (Function):** the +4 tests (tool-detail+params / no-arg-honest / key-mask / #88-intact) + tsc + vitest 1053/0 + Chrome + the scope-math-untouched guard. ✅
- **Gate 3 (Sprint):** end-doc; frontend-w3-2 Chrome + architect 4-step; staged EXACTLY the 6 FE files (NO backend/template leak); commit format. ✅

## Assumptions (user-review)
- **key value MASKED by default, reveal-on-demand** (security). **How to change:** the keyRevealed default / maskKey.
- **tool rows expandable → fullDescription + params table; no-arg → "không tham số"** (honest). **How to change:** the ToolDetail body.
- **scope math untouched** (polish-only). **How to change:** n/a — lib/mcpScope is the pure scope contract; this pass didn't touch it.

## Notes
- Cairn #128 + #129-FE — **MERGED into one /mcp-keys FE pass** (team-lead's call, architect agreed: two passes on the same screen = file-churn + a needless 2nd 4-step/commit; one cohesive pass is cleaner). user-CHỐT (polish the key manager + show each tool's description + call-params). frontend-w3-2 built + Chrome-verified; architect committed (§3 sole-committer). 🔴 **The scope-math-untouched guard is the load-bearing 4-step check** — a "polish" pass on the scope screen must NOT change the pure scope computation (lib/mcpScope); verified it's untouched (only its test gained additive fixture fields). The key-mask is the security-hygiene win (never the raw secret on-screen). Reads the #129-BE catalog (GET /mcp_keys/catalog, frozen e9b4324) → the params table is derived-from-live. **Parallel-lane staging (13th clean):** FE-only (BE clean). **Completes the user-CHỐT batch** (the 3 new asks #123/#128/#129 + the tracing redesign #121-126 + #131). After push → team-lead Chrome-verifies → closes #128+#129. #127 (wiki work-dir) design still awaits user-greenlight.
