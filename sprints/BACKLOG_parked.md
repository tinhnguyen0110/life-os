# Parked backlog (architect-tracked) — surface to team-lead when a relevant lane opens

> Low-priority, non-blocking items found during #142/#143. NOT dispatched (don't expand the current sprint). Surface to team-lead for prioritization when a tester/dogfood/parity lane opens.

## P-1 — reminders-test-isolation flake (tester-owned, LOW)
- **What:** a #31 Reminders vitest test fails ~1/6 full-suite runs, non-reproducing (isolation/timing). 2nd sighting of a reminders-suite isolation flake.
- **Class:** same as the #141 settings flake (a once-Once mock / spy-isolation timing leak — a `mockResolvedValueOnce` consumed by StrictMode double-invoke, or an afterEach reset gap).
- **Found:** #143 /tracing (FE saw it on a CSS-only change → definitely not caused by the change).
- **Fix direction:** audit the reminders test's mock setup (mockResolvedValueOnce → mockResolvedValue, or per-test reset) like #141 settings.test:33. tester-owned.
- **Why parked:** flaky 1/6, not a product bug; doesn't block any feature. team-lead noted "low-pri follow-up after, not blocking."

## P-2 — MCP/REST wiki_overview parity bug (dogfood/parity lane, MEDIUM)
- **What:** `mcp wiki_overview` returns totalNotes **80** / fleeting **63**; REST `GET /wiki/overview` returns totalNotes **50** / fleeting **34** for the same vault. They DISAGREE.
- **Root cause:** MCP counts soft-deleted notes; REST excludes them (active-only). The agent-surface (MCP) and the human-surface (REST/FE) report different totals → an AGENT-FIRST honesty/parity violation (an agent reading MCP gets inflated counts).
- **Found:** #143 /wiki W2 trace (the 63-vs-34 confusion traced back to this; team-lead pulled both surfaces).
- **Fix direction:** align MCP wiki_overview to REST's active-only semantics (or document the difference explicitly in the MCP output — e.g. separate `total` vs `activeTotal` fields so an agent isn't misled). Backend-owned; fits a dogfood/parity round.
- **Why parked:** not blocking #143 (the FE label fix handles the UI clarity); it's a separate backend parity concern for a dogfood lane.

## P-3 — wiki inbox "fleeting" scope exceeds the vault's fleeting partition (backend, MEDIUM)
- **What:** REST `/wiki/overview` returns `inbox.length = 63` (all status:"fleeting") but `stats.byStatus.fleeting = 34` and `totalNotes = 50`. So the inbox's fleeting count (63) > the whole-vault fleeting partition (34) > totalNotes (50) — the two "fleeting" scopes don't reconcile.
- **Why it matters (agent-first):** a consumer-agent reading the API sees two irreconcilable "fleeting" numbers (inbox 63 vs stats 34) with no field explaining the scope difference. The FE now labels them distinctly (inbox = "cần refine"), so the UI isn't misleading — but the API itself is ambiguous to an agent.
- **Root cause (hypothesis):** the inbox likely counts pre-vault captures / a broader source set than the byStatus partition (which is active vault notes). Needs a backend look.
- **Found:** #143 /wiki W2 trace (FE flagged, architect confirmed via REST).
- **Fix direction:** either reconcile the two scopes, or add an explicit semantic to the inbox count (e.g. an `includesPreVaultCaptures` flag / a `scope` field) so an agent can interpret it. Backend-owned, dogfood/parity lane.
- **Why parked:** UI is honest post-#143; the API-level scope clarity is a separate backend concern.
