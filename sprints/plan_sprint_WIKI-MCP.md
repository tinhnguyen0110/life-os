# Sprint WIKI-MCP — expose wiki reads over MCP (G1) + USAGE-FIX (G6/G7)

> From the consumer-agent gap round (memory `consumer-agent-round1-gaps-2026-06-15`, all Rule#0-verified).
> Backend-only. Lane A (WIKI-MCP, headline) + Lane B (USAGE-FIX, 2 real bugs).

## Kickoff — 2026-06-15 (architect)

### Verified the 3 gaps against current code (confirms team-lead's reads — no drift)
- **G1 WIKI-MCP:** the 3 "wiki" matches in `mcp_servers/read_server.py` are all COMMENTS — **ZERO wiki read tools**. Wiki module post-refactor (the deferred A5 split is done: `modules/wiki/store/` package + `reader`). The `/wiki` read endpoints call `reader.search(q)`, `reader.overview()`, `service.get_note(id)`, `reader.backlinks(id)`, `reader.folder_tree()` (the fns to wrap). WRITE_SYMBOLS (test_mcp_read.py L497) ALREADY contains the wiki write surface (`create_note/update_note/delete_note/merge_notes/create_proposal/accept_proposal/reject_proposal/enqueue/mark_decided/...`) — the gate already gates wiki writes; we just verify NO wiki write fn is imported by the read-server.
- **G6 claude_usage pct overflow — REAL (reopens my wrongly-dissolved M6):** `claude_usage/service.py:293` `pct = used/cap*100` → 3316% (cap 200k vs used 6.6M). **`brief/service.py:102` READS `claude.pct`** + L108-111 headlines "Quota Claude đốt {pct}% — sắp hết" when pct≥90 → ALWAYS fires the urgent band with an absurd number. My "no consumer reads raw pct" dissolution was WRONG — I didn't grep ALL consumers. The trigger fired.
- **G7 phantom projects:** `projects/service.py:118-120` lists `projects_dir.iterdir()` — test-fixture projects (`active` w/ repoPath `/tmp/pytest-of-watercry/...`, `crewly`) got registered into the prod projects_dir + leak into the real list.

### Design decisions
- **Lane A (WIKI-MCP)** = mirror NEWS-MCP (533ed12) EXACTLY: `wiki_search(q, limit)` / `wiki_get(note_id)` / `wiki_overview()` (+ `wiki_backlinks(note_id)` if cheap — it is) aliased-private → TOOLS dict → derive-catalog auto-picks (30→34). NEUTRAL/read-only. The capability gate already lists wiki writes; verify 0-leak + add any missing wiki write fn.
- **Lane B G6** = brief should NOT headline raw `pct` (cumulative/context-cap = nonsense >100%). Use the real quota window `pct5h`/`pctWeek` (exists + correct), OR clamp raw pct ≤100 + don't headline when it's the broken field. The brief's quota rule keys on a SANE pct. Verify daily_brief no longer shows >100%.
- **Lane B G7** = find how test projects entered `projects_dir` + filter/clean them (a prod list must not show `/tmp/pytest-*` repos). Likely a test wrote into the real projects_dir without cleanup, OR the dir isn't test-isolated.

### Lesson logged (G6 — my M6 miss)
A "dissolved-with-trigger" finding ("no consumer reads X") must grep ALL consumers, not just the ones I know — AND be re-checked when a new consumer appears. The consumer-agent caught what my static self-audit missed. → memory `dissolved-finding-recheck-all-consumers`.

### Final task list
- **Lane A [backend]** — wiki MCP read tools + gate + behavior tests + CATALOG regen.
- **Lane B [backend]** — G6 (brief uses sane pct, no >100% headline) + G7 (phantom projects filtered).
Both backend. A is bigger + the headline → A first or parallel (independent files: A=read_server/test_mcp_read/CATALOG; B=brief/service + claude_usage + projects).

## Assumptions (user-review)
- Wiki MCP = read-only tools mirroring news/macro; the agent reads the vault, cannot write (proposals stay the write path).
- G6: brief headlines a SANE quota % (pct5h-based or clamped), never the raw used/context-cap overflow.
- G7: prod projects_list excludes test-fixture (/tmp/pytest-*) projects.
