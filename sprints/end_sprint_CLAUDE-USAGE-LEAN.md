# end_sprint_CLAUDE-USAGE-LEAN — lean-by-default claude_usage MCP tool + honest-null-with-reason (Cairn #18)

> Result. agent-first dogfood (admin-lead raise). Committed TOGETHER with #14 (shared read_server.py + test_mcp_read.py, one backend pass) — commit `<hash>` `fix(sprint-JOURNAL-NUDGE+CLAUDE-USAGE-LEAN)`. Status: ✅ all 3 gates pass.

## Objective (met)
The `claude_usage` MCP tool dumped ~4325 chars (series7+byModel6+byProject12 = 25 nested objects) on EVERY call for what an agent usually wants = a few numbers. Made it LEAN by default, verbose=true for the breakdown — a clean agent-readable surface (the whole goal).

## Root nuance (live-traced — the honest call)
`remaining` was null NOT because of a missing computation but because `used` (today ~3.0M tokens) >> `cap` (200k — a PLACEHOLDER, "not from disk"). remaining-off-placeholder-cap is MEANINGLESS. team-lead's first ask was "fill remaining (not null)" — architect's live-trace OVERRODE it (team-lead endorsed): faking remaining from a placeholder = the honest-mirror sin the DXY arc just taught. So remaining STAYS honest-null; the lean view LEADS with the REAL live quota signal (pct5h/resetIn/weekly — populated + meaningful), and carries a one-line REASON when null (the dxy.warning honest-null-with-reason pattern).

## What shipped (mcp_servers/read_server.py — the `claude_usage` tool)
- `claude_usage(window="5h", verbose=False)` — new `verbose` param.
- **LEAN (default):** ~6-8 fields = pct5h, resetIn, weekly, today, remaining (honest-null), costUSD ($.01), + provenance (quotaSource/tokenSource) + a `remainingNote` when remaining is null-due-to-placeholder-cap ("cap is a placeholder; use pct5h/resetIn for live quota"). Drops series/byModel/byProject/raw-ctx.
- **VERBOSE (verbose=true):** the FULL current shape (series + byModel + byProject + ctx + everything) — `{usage, verbose:true}`.
- **costUSD** formatted to 2 decimals at the tool (underlying precise; cumulative magnitude is a known item, not re-litigated).
- The projection is in the read_server TOOL (presentation); `claude_usage/service.get_usage` returns the full model unchanged → GET /claude-usage REST + the FE consume the full shape (unaffected).

## Verification (Rule #0 — 3-way)
- **architect Rule#0:** read the full `claude_usage` fn (read_server.py:426) entry→exit — lean default carries pct5h/resetIn/weekly/today/costUSD/remaining/provenance + remainingNote-when-null, drops the heavy splits; verbose=true returns the full shape `{usage, verbose:true}`; costUSD round(_,2) both paths; `_claude_usage`/service.get_usage returns the full model unchanged → REST/FE unaffected.
- **team-lead live:** MCP lean default = **342 chars (was 4325, ~13× smaller)**, 9 lean fields, NO heavy splits (series/byModel/byProject absent); remaining=null + remainingNote="cap is a placeholder (not from disk); use pct5h/resetIn…" (honest-null-with-reason, dxy.warning pattern); **REST /claude-usage UNAFFECTED — still full 4326 chars** with the splits (FE/life_brief.claude intact).
- **tester:** the 5-case (lean small / verbose full / costUSD $.01 / remaining honest-null+reason / REST-unaffected) green; 1707 pytest/0 failed; 2 scaffold false-positives explained+corrected (lean⊆verbose assertion was wrong — remainingNote is lean-specific).

## 3 Gates — ALL PASS
- **Gate 1 (API):** the MCP tool gains verbose (additive); REST /claude-usage unchanged; integration green. ✅
- **Gate 2 (Function):** lean/verbose split tested; remaining-null+reason vs real-cap-computes distinguishing; costUSD format; REST-unaffected; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; team-lead live + architect Rule#0 + tester; commit format. ✅

## Assumptions (user-review)
- **claude_usage MCP tool LEAN by default (~6 fields leading with the live quota signal pct5h/resetIn/weekly/today/costUSD), verbose=true for series/byModel/byProject.** **How to change:** the lean field set is in the read_server claude_usage tool.
- **`remaining` stays honest-null when the token-cap is a placeholder** (NOT faked from cap-math — the honest-mirror lesson) + a one-line reason note when null. The live signal (pct5h/resetIn) is the real answer. **How to change:** set a real manual-override cap → remaining computes (no note).
- **costUSD formatted $.01** at the tool (cumulative magnitude is a separate known item — claude-usage-token-source memory).

## Notes
- agent-first — a clean agent-readable tool surface (the whole goal).
- The honest-null-with-reason decision directly applied the DXY-arc honest-mirror lesson (don't fake a value from a placeholder; a null carries its reason).
- Committed with #14 (journal-nudge) — same batch, independent functions, shared read_server.py + test_mcp_read.py.
