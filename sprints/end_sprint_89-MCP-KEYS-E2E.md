# end_sprint_89-MCP-KEYS-E2E — per-key MCP scoping end-to-end verification (Cairn #6 T4, CLOSES #6)

> Result. The whole #6 per-key MCP scoping cluster verified end-to-end on the LIVE container: the 3 cases (no-key→all · valid→scoped · invalid→agent-error), two-keys-two-sets distinguishing, the per-mount filtering nuance, catalog REST≡MCP, and full-suite no-regression (BE + FE). Commit `<hash>` `test(sprint-89): per-key MCP scoping e2e verification (#89, closes #6)`. Status: ✅ verified (architect consolidated live-pass + team-lead independent spot-check). Cairn #6 T4 — CLOSES the #6 cluster. No new code (consolidation + formal evidence + the no-regression confirm).

## What this verified (LIVE on the container, Rule#0 — in-container HTTP, not import-cache)
| Case | Result |
|---|---|
| **CASE 1 — no key** | `/mcp/read` → **46 tools** (full read mount; no regression vs the no-filter behavior). ✅ |
| **CASE 2 — valid key (finance domain)** | finance-key on `/mcp/read` → **EXACTLY 15 finance tools**, nothing else. ✅ |
| **CASE 3 — invalid/unknown key** | bogus key → **HTTP 404 + agent-readable** `{code:NOT_FOUND, message:"the MCP key 'bogus-…' is not recognized", hint:"ask the user to create/fix the key in the MCP-keys UI, or omit the key to get all tools", retryable:false}` — NOT all-tools, NOT 500, token truncated. ✅ |
| **DISTINGUISHING — two keys, two sets** | finance-key → 15 vs reminders-key → 1 on `/mcp/read` (different tool sets — proves per-key scoping is real, not a constant). ✅ |
| **filter-honest (from #87 4-step)** | a key scoping {finance_overview, PHANTOM} → resolves to {finance_overview} only (phantom skipped, no error). ✅ |
| **empty-scope (from #87 4-step)** | empty-scope key → 0 tools (valid sees-nothing, distinct from the case-3 error). ✅ |
| **catalog REST≡MCP** | `GET /mcp_keys/catalog` (REST) tool count == `list_tools_catalog` (MCP) tool count (91), byte-identical payload. ✅ |
| **persistence / cleanup** | keys created → verified → DELETED → store back to baseline 0 (settings-backed md_store; no test pollution). ✅ |

## The per-mount nuance (team-lead's diagnosis — documented, NOT a bug)
- A reminders-scoped key on `/mcp/read` sees only the reminders tool(s) THAT MOUNT carries (e.g. 1), while on `/mcp/reminders` it sees the full reminders set (3). **Each mount filters its OWN subset of the scoped tools** — the cross-mount picture is consistent (the key's full scope spans mounts; each mount shows the intersection of its tools with the scope). The BE-computed `toolCount` on the key row is the resolved union vs the WHOLE catalog (e.g. {domains:[reminders],tools:[finance_overview]}→4), independent of which mount you query. This is correct per-mount behavior, NOT a double-count or a leak.

## Verification (Rule#0 — architect consolidated live-pass)
- The 3 cases + distinguishing RE-RUN fresh on a restarted container (the table above) — value-by-value, keys cleaned up.
- catalog REST≡MCP confirmed live (count match).
- **No-regression suite (the gate):** BE DEFAULT (`-m 'not slow'`) = **2166 passed / 6 skipped / 3 deselected / 0 failed**; FE vitest = **83 files / 947 passed / 0 failed** (on a clean run). The existing all-tools / per-domain-mount behavior intact (no-key path byte-identical).
- ⚠️ **Known FE flake (NOT a #6 regression):** one FE full-run showed `1 failed / 946 passed`; the re-run was clean 947/947 (the verbose re-run shows all green). The #6/#88 tests (mcp-keys 16, mcpScope 10) are DETERMINISTIC (proven multiple runs). The flake is a pre-existing intermittent unrelated to #6 (frontend-w3-2 saw it too + re-ran clean). Flagged as separate FE test-stability debt — not a #6 blocker.
- team-lead independently spot-checked the consolidated evidence + the mixed-scope per-mount nuance on the container.

## 3 Gates
- **Gate 1 (API/MCP):** the 3 cases agent-correct on live HTTP; catalog REST≡MCP; no-key no-regression; the invalid-key error agent-readable (code/message/hint/retryable, token truncated). ✅
- **Gate 2 (Function):** distinguishing (two-keys-two-sets, filter-honest, empty-scope) live; the #86/#87/#88 unit+integration tests green. ✅
- **Gate 3 (Sprint):** end-doc; architect consolidated live-pass + team-lead spot-check; full suite 0-failed (BE + FE); commit format `test(sprint-89)`. ✅

## Notes
- Cairn #6 T4 — **CLOSES the #6 cluster.** The full user-CHỐT per-key MCP scoping feature is complete end-to-end:
  - #86 (7503403) — the key→scope store + CRUD (get_key_scope, the empty≠None contract).
  - #87 (0d384b2) — the /mcp key-aware filter (3 cases, store-lenient/filter-honest, ContextVar/ASGI injection verified empirically) + the catalog REST route.
  - #88 (fce7317 + d784a04) — the /mcp-keys UI (CRUD + per-domain/per-tool scope-editor + catalog-audit + X-MCP-Key connect-hint).
  - #89 (this) — the end-to-end runtime verification.
- A client now configs ONE /mcp endpoint + ONE optional X-MCP-Key; the server scopes the tools that key sees; the UI manages keys + audits the tool catalog. Per-domain mounts STAY (additive). No new code in #89 — consolidation + formal evidence + no-regression. After #89: the next batch (admin-lead user-pain queue: #93 upload / #94 soft-delete) awaits the user's priority confirm.
