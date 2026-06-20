# Sprint MCP-DOCS — refresh MCP-CONFIG.md (Cairn #3 + #10)

> Created 2026-06-21 by architect. Grouped #3 (MCP connect guide) + #10 (a finance-only .mcp.json) — both MCP-config docs, shared theme → one docs sprint. Docs-only, low-risk (architect owns it; backend stays free for the dogfood round). Zero user-input needed.

## Objective
docs/MCP-CONFIG.md exists (316 lines) but is STALE vs this session's work. Refresh it so a consumer-agent connects cleanly + a finance-only agent has a copy-paste config. Serves the goal (an external Claude connecting to life-os over MCP).

## Drift to fix (#3)
1. **`/mcp/reminders` (lifeos-reminders) MISSING** — main.py has 6 mounts; the doc listed 5 (no reminders server, added Sprint REMINDERS-2/#28). Add it everywhere (server table, HTTP mount table, stdio entry, CLI, sanity-check).
2. **wiki-read tool blurb stale** — listed graph/backlinks as wiki-read tools; #23 removed those MCP tools (→ wiki_context). Fix the capability blurb + add the #23/#24 note.
3. **Canonical doubled URL** — document `/mcp/<server>/mcp` (the doubled path) as CANONICAL + that the de-double was ABORTED (don't "fix" it).
4. **Tailscale host** — document `100.113.13.30` (the Tailscale IP, = LIFEOS_API_BASE) for another-device connects, alongside localhost.
5. **Client-caches-schema-on-connect** — a tool-surface change (e.g. #23 swap) isn't seen until the client RECONNECTS (re-initialize). The "stale tool on a long session" finding.

## #10 — finance-only .mcp.json
A ready-to-copy `.mcp.json` for a finance-only agent (lifeos-finance, /mcp/finance, 15 tools) + mention lifeos-reminders as a second per-domain example. http transport (no interpreter/cwd needed).

## Scope
IN: edit docs/MCP-CONFIG.md only.
OUT: backend/CATALOG.md (team-lead's); any code change; the root .mcp.json (untracked cairn config).

## Verification
- All 6 mounts (incl /mcp/reminders) in the HTTP table; reminders in server table + stdio block + CLI + sanity-check.
- wiki blurb reflects wiki_context (not graph/backlinks); #23/#24 note present.
- Tailscale host + doubled-URL-canonical + reconnect-for-schema notes present.
- A copy-paste finance-only .mcp.json block present.
- No code touched; markdown renders (no broken tables).

## Notes
- Docs-only; one commit `docs(sprint-MCP-DOCS)`. Low-risk → quick-scan review, no 4-step.
- #12 closed-by-decision separately (no speculative domain servers — Instruction.md). #11 stays deferred.
- After this: team-lead runs a dogfood round (the real next-gap finder) per the goal.
