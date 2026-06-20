# Sprint CLAUDE-USAGE-LEAN — lean-by-default claude_usage MCP tool + honest quota signal (Cairn #18)

> Created 2026-06-21 by architect. agent-first (clean agent-readable surface) — admin-lead dogfood raise. Parallel-safe vs #14 (different module: claude_usage) BUT shares read_server.py with #14's life_brief edit → backend sequences; commit serial.

## The gap (admin-lead dogfood, live-confirmed)
`claude_usage` MCP response is **4325 chars** for what an agent usually wants = 3 numbers. It dumps series(7)+byModel(6)+byProject(12) = 25 nested objects on EVERY call. AND the headline signal is confusing: `remaining: null` (the first thing a user asks), `costUSD: 53627.5276` (4 decimals, huge cumulative).

## Root nuance (live-traced — IMPORTANT, shapes the fix)
`remaining` is ALREADY computed: `max(cap - used, 0) if used <= cap else None`. It's null because `used` (today 3,019,262 tokens) >> `cap` (200,000 — a PLACEHOLDER, "NOT from disk" per the schema). So remaining-off-token-cap is MEANINGLESS (the token cap isn't real). The REAL quota signal — already populated, live — is `pct5h: 17.0` + `resetIn: "3h 18m"` + `weekly: 12` (the 5h rate-limit the user actually hits). So the fix is NOT "compute remaining from cap-math" (that stays honest-null when the cap is a placeholder) — it's **lead the lean view with the live quota signal that answers 'how close am I to the limit'.**

## Design (lean-by-default, verbose for the heavy splits — the cairn TaskList pattern)
Add a `verbose: bool = False` param to the `claude_usage` MCP tool (read_server.py).
- **LEAN (default) — the agent-useful quota answer (~6 fields):** `pct5h` (live 5h rate-limit %), `resetIn` (5h reset countdown), `weekly` (7-day %), `today` (today's tokens), `costUSD` (formatted $.01), `quotaSource`/`tokenSource` (provenance, cheap). + `remaining` ONLY if the cap is meaningful (else keep it but honest-null, with the live pct5h being the real signal). Drop `series`, `byModel`, `byProject` (the 25 nested objects) + the raw ctx fields from the default.
- **VERBOSE (verbose=true):** the full current shape (series + byModel + byProject + ctx + everything) — for when an agent genuinely wants the breakdown.
- **costUSD formatting:** round to 2 decimals ($53627.53) at the tool surface (the underlying value stays precise; format for display). NOTE the cumulative-cost magnitude is a separate known item (claude-usage-token-source memory — costUSD is cumulative, not per-window) — don't re-litigate it here, just format.
- The `remaining` honesty: keep it computed as today, but ensure the lean view doesn't make `remaining: null` read as "broken" — pct5h/resetIn ARE the answer. (Optional: a one-word note when remaining is null because the token-cap is a placeholder — log if added.)

## Scope
- **IN:** the `claude_usage` MCP tool in `mcp_servers/read_server.py` gains `verbose` + returns LEAN by default; costUSD formatted; the lean field set surfaces the live quota signal. Possibly a tiny helper in claude_usage/service.py if the lean projection belongs there (architect pick: do the projection in the read_server tool — it's a presentation concern, keep service.get_usage returning the full model; the tool slices lean/verbose). 
- **OUT:** NO data-source change (don't touch how tokens/quota are read). NO FE change. NO change to GET /claude-usage REST (the FE consumes the full shape — only the MCP tool goes lean; confirm the REST endpoint is separate from the MCP tool so FE is unaffected). NO re-litigating the cumulative-costUSD magnitude.

## Tasks
- **T1 (backend):** `claude_usage(verbose=False)` in read_server.py → lean projection (the ~6 fields) default, full shape on verbose=true; costUSD $.01; tests. **SEQUENCING: read_server.py is ALSO touched by #14 (life_brief _brief_decisions). Do whichever lands first cleanly; the two edits are in DIFFERENT functions (claude_usage vs _brief_decisions) — no logical conflict, but coordinate so a commit doesn't sweep the other's in-progress edit (content-diff at commit).**
- **T2 (tester):** lean default response is small (~6 fields, no series/byModel/byProject) + carries the live quota signal (pct5h/resetIn/weekly/today); verbose=true returns the full shape; costUSD formatted; REST /claude-usage + the FE unaffected (full shape there).
- **T3 (architect):** review + commit serial (after #14).

## HARD GATE (distinguishing)
- Default (no verbose) → LEAN: has pct5h/resetIn/weekly/today/costUSD; does NOT have series/byModel/byProject. Response materially smaller (was 4325 chars).
- verbose=true → FULL: has series + byModel + byProject (the breakdown).
- costUSD formatted to 2 decimals.
- The live quota signal (pct5h/resetIn) is IN the lean view (the "how close to the limit" answer the user wants).
- REST /claude-usage + FE unaffected (full shape preserved there — only the MCP tool slices). [the no-FE-break distinguishing]
- pytest green, mypy clean.

## Baseline
pytest (post-#14 — re-anchor at dispatch). Keep 0-failed; expect +2-3.

## Assumptions (user-review)
- **claude_usage MCP tool LEAN by default (~6 fields: pct5h/resetIn/weekly/today/costUSD + provenance), verbose=true for series/byModel/byProject.** The lean view leads with the LIVE quota signal (pct5h/resetIn) — the real "how close to the limit," because `remaining` off the placeholder token-cap is meaningless (used>>cap→null). **How to change:** the lean field set is in the read_server claude_usage tool.
- **`remaining` stays honest-null when the token-cap is a placeholder** — pct5h is the real signal. NOT faked from cap-math (faking a number from a placeholder = the honest-mirror sin the DXY arc taught). **How to change:** set a real cap (manual-override) → remaining computes.
- **honest-null WITH a reason (team-lead-endorsed, dxy.warning pattern):** when remaining is null-due-to-placeholder-cap, the lean view carries a one-line reason ("cap is a placeholder; use pct5h/resetIn for live quota") so an agent isn't confused by the bare null + knows where the real signal is. Only when null-due-to-placeholder (real cap + used≤cap → remaining computes, no note). Tested both ways. **How to change:** the note logic is in the read_server claude_usage lean projection.
- costUSD formatted $.01 at the tool (underlying precise). Cumulative-magnitude is a separate known item (not re-litigated here).

## Notes
- agent-first (the whole goal — a clean agent-readable tool surface). Single-user no-overengineering.
- Shares read_server.py with #14 → commit serial + content-diff each function at commit (commit-content-diff-not-just-filenames).
