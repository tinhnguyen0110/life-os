# end_sprint_MCP-DOCS — refresh MCP-CONFIG.md (Cairn #3 + #10)

> Result. Docs-only, low-risk (architect; backend stayed free). Commit `<hash>` `docs(sprint-MCP-DOCS)`. Status: ✅ done. #12 closed-by-decision (see below); #11 stays deferred.

## What shipped
`docs/MCP-CONFIG.md` (316 → 376 lines) refreshed to match the current MCP surface:

| # | Change |
|---|---|
| #3.1 | Added **`lifeos-reminders`** (the 6th mount, Sprint REMINDERS-2/#28) everywhere: server table (3 tools — reminders_list read + reminder_create/tick DIRECT write-through), HTTP mount table (`/mcp/reminders/mcp`), stdio entry, `claude mcp add` CLI, §5 sanity-check. |
| #3.2 | Fixed the stale **wiki-read** blurb (was "graph/backlinks") → now `wiki_context` (#23 consolidation); added the #23 (graph/backlinks → wiki_context, REST kept) + #24 (the REST≡MCP test-gate) note. wiki count stays 11. |
| #3.3 | Documented the **canonical doubled URL** `/mcp/<server>/mcp` + that the de-double was ABORTED (don't "fix" it). |
| #3.4 | Documented the **Tailscale host** `100.113.13.30` (= LIFEOS_API_BASE) for another-device connects, alongside localhost; noted no-auth + DNS-rebinding-OFF is why a non-localhost Host connects. |
| #3.5 | Documented **client-caches-schema-on-connect** — a tool-surface change (the #23 swap, a new server) isn't seen until the client RECONNECTS; a "stale tool" on a long session is this, not a server bug. |
| #10 | Added a **ready-to-copy finance-only `.mcp.json`** (http, lifeos-finance, /mcp/finance, no interpreter/cwd needed) + the lifeos-reminders stdio entry as the 2nd per-domain example + Tailscale-swap note. |

## #12 — CLOSED BY DECISION (not built)
#12 = "which domain servers beyond finance" — already DECIDED (Instruction.md): STOP at finance; others ON-DEMAND only (no speculative lifeos-market/projects — build only when a real agent needs that narrow view). No such need has surfaced → #12's answer is "none speculatively." Marked decided, NOT built (avoids the busywork of speculative servers). #11 (lifeos-market) stays deferred on the same basis — until a market-agent need appears.

## Verification (Rule #0 — architect, docs)
- grep-confirmed: all 6 mounts incl `/mcp/reminders/mcp` in the HTTP table (11 doubled-URL hits); reminders in server table + stdio block + CLI + sanity-check; wiki blurb reflects wiki_context; Tailscale host + doubled-URL-canonical + reconnect-for-schema notes present; the copy-paste finance-only .mcp.json block present.
- No code touched (docs-only); markdown tables intact; 316 → 376 lines.
- The facts were grounded against the LIVE source: main.py `_MCP_MOUNTS` (6 mounts), docker-compose `LIFEOS_API_BASE=100.113.13.30:8686`, reminders_server.TOOLS (3), finance_server (15).

## Assumptions (user-review)
- **MCP-CONFIG.md is the canonical connect guide** — updated to the 6-mount surface (whole-app read/write + wiki read/write + finance + reminders), the doubled-URL canonical form, Tailscale host, and the reconnect-for-schema caveat. **How to change:** edit docs/MCP-CONFIG.md (the live truth = `list_tools_catalog()` + main.py `_MCP_MOUNTS`).
- **No speculative per-domain servers** (#12 decided): finance + reminders exist because a real narrow surface was wanted; lifeos-market/projects are ON-DEMAND only. **How to change:** build a domain server when a real agent needs that narrow view (clone the per-domain pattern).

## Notes
- Docs-only; one commit `docs(sprint-MCP-DOCS)`. CATALOG.md (team-lead's) + the held #31 FE files EXCLUDED from the commit.
- After this: team-lead runs a dogfood round (consumer-agent → next genuine gap) per the goal — the real highest-value next move now reminders + wiki are done.
