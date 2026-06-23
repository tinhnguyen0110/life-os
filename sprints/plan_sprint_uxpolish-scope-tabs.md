# plan_sprint_uxpolish-scope-tabs (#165) — McpScopeEditor → domain TABS

> USER feedback: "Phạm vi... ko làm giới hạn box + 1 domain 1 filter ở trên chọn cho dễ ko flat ra" → CHỐT tab-domain. The scope-editor renders all 7 domains + ~98 tools FLAT at once (overwhelming). Redesign to a domain-tab nav: a tab row on top, click a domain → only that domain's tools below. LAYOUT/nav only — scope MATH unchanged. Shared component (create + edit). Spec'd against McpScopeEditor.tsx (HEAD 84623fa) + lib/mcpScope + the existing tests.

## Source of truth — scope MATH stays UNCHANGED (lib/mcpScope)
`toolsInDomain · isToolSelected · isDomainSelected · toggleDomain · toggleTool · resolvedTools · groupByDomain · EMPTY_SCOPE`. The redesign calls the SAME functions; it only changes WHICH tools are rendered at once (active domain) + the nav. Do NOT touch lib/mcpScope.

## Current (McpScopeEditor.tsx L85-133)
- L86 `.scope-editor` wrapper + selected-count line (keep).
- L92 `groups.map` renders EVERY domain: a `.scope-domain-head` (domain checkbox + name + count chip) + ALL `.scope-tools` inline → the flat-98 problem.
- Box-scroll: tokens.css L1240 `.scope-editor { max-height:380px; overflow:auto }` → the "box giới hạn" to remove.

## Redesign #165 (TAB domain — layout only)
1. **TAB ROW on top** — one tab per domain (read·finance·market·reminders·tracing·write…), each showing the domain name + its count. Add `activeDomain` state (default = first group's domain). Clicking a tab sets activeDomain → only that domain's tools render below.
   - Each tab ALSO carries the whole-domain tick affordance (`toggleDomain`) — so the user can tick a whole domain from its tab. Put the domain checkbox IN the tab (or a tick indicator on the active tab's header). The `domain-check-{domain}` testid MUST stay on the per-domain tick control AND be present for every domain (the tests click `domain-check-finance` etc — see Test section).
   - Keep `scope-domain-{domain}` + `domain-count-{domain}` testids per domain on the tab.
2. **Below the tabs = ONLY the active domain's tools** — reuse the existing tool-row exactly (`.scope-tool-wrap` / `.scope-tool` / `tool-row-{name}` / `tool-check-{name}` / DetailToggle `tool-expand-{name}` / ToolDetail). Same per-tool tick (`toggleTool`), same ⓘ detail expand.
3. **REMOVE the box-scroll** — tokens.css `.scope-editor` drop `max-height:380px; overflow:auto` (+ border/radius/padding can stay or move). Natural flow.
4. **KEEP the counter** L87-90: "Đã chọn N / TOTAL tool (X domain + Y tool lẻ)" with `scope-selected-count` testid.
5. Per-tool tick + whole-domain tick both work (call the same math fns).

## 🔴 SHARED COMPONENT — applies to BOTH contexts
McpScopeEditor is used in:
- the create-form (`createScope`/`setCreateScope`) — page.tsx
- the inline edit-scope ("Sửa phạm vi", `editScope`/`setEditScope`) — page.tsx, inside `edit-scope-{keyId}`
The redesign is in the component → both get it automatically. tester MUST verify BOTH (create flow + edit-scope flow).

## 🔴 TEST IMPACT — lockstep update REQUIRED (the main risk)
Existing tests (mcp-keys.test.tsx) click controls that, post-redesign, may be on a non-active tab:
- L177 `domain-check-finance`, L195 `domain-check-finance`, L212 `domain-check-finance` (edit) — domain ticks. If domain-check lives in the always-visible TAB row, these still work (good — put domain-check in the tab). CONFIRM.
- L196 `tool-check-trc_a` (a TRACING tool) clicked directly — post-tabs, trc_a only renders when the tracing tab is active. → the test MUST first `click(tab-tracing)` (or `scope-domain-tracing`) THEN click `tool-check-trc_a`. UPDATE this test lockstep.
- L295 `scope-domain-finance` toBeInTheDocument — keep `scope-domain-{domain}` on every tab so this holds.
fe updates the tests in lockstep (per tester-scaffold-ownership: the author updates its own tests; here the component+test move together). Add a new test: "click a domain tab → only that domain's tools render (other domain's tool-row absent)".

## Scope OUT
- lib/mcpScope (math) — UNCHANGED.
- `McpCatalogAudit` (the read-only catalog view, same file L139+) — NOT in scope, leave it flat.
- No new API, no scope-shape change. ⓘ tool-detail (ToolDetail/DetailToggle) — keep as-is.
- Dark, scoped (`.scope-*` rules can change for the tab layout, but NO global-token mod). The `.scope-*` classes are mcp-scope-specific (not shared with other screens) — safe to restyle for tabs.

## Verify-criteria
1. Tab row on top, one per domain + count. Click a domain tab → ONLY that domain's tools below (other domains' tool-rows NOT in DOM).
2. Whole-domain tick (from tab) works → scope.domains updates, count updates.
3. Per-tool tick works → scope.tools updates, count updates.
4. Counter "Đã chọn N/TOTAL (X domain + Y tool lẻ)" correct.
5. NO box-scroll (max-height/overflow removed) — natural flow.
6. BOTH contexts: create-form scope-editor + edit-scope ("Sửa phạm vi") — same tab UI, both functional.
7. Full create flow still works (tick via tabs → Tạo key → key-once). Cleanup any test key.
8. Tests updated lockstep (tab-then-tool where needed) + a new "tab filters tools" test. vitest green, tsc clean, dark no-leak, console clean (SWC — JSX restructure).
9. testids preserved: scope-editor, scope-selected-count, scope-domain-{d}, domain-check-{d}, domain-count-{d}, tool-row-{n}, tool-check-{n}, tool-expand-{n}, tool-detail-*. 0 dropped (comm) unless a test is updated to match a renamed one.

## Risk: MEDIUM-HIGH (shared component, JSX restructure, test lockstep). 4-step MUST verify both contexts + the math-unchanged + test-survivors-recovered.
