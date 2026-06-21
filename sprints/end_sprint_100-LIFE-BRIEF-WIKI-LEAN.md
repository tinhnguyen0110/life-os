# end_sprint_100-LIFE-BRIEF-WIKI-LEAN — brief.wiki lean projection (Cairn #100, bounded-output)

> Result. `life_brief` was ~33KB (the wiki section alone = 23KB = 70%): `_brief_wiki` pasted the ENTIRE `wiki_overview()` blob — the full inbox (41 notes WITH rawContent = 15.5KB), full orphans (12), full recentActivity (20). Fixed (agent-first bounded-output, principle #38, same family as #91/#92): `_brief_wiki` → a LEAN projection (stats + counts + top-3 stubs + recentActivity≤5 + a cairn-#295 structured `truncated` flag) — point-don't-paste; the full inbox lives on the unchanged standalone `wiki_overview`. Commit `<hash>` `fix(sprint-100-life-brief-wiki-lean): brief.wiki lean projection, source kept (#100)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live size + source-still-full on the restarted container). Cairn #100 — team-lead's dogfood finding.

## What shipped (read_server.py + test)
| File | Change |
|---|---|
| `mcp_servers/read_server.py` (`_brief_wiki`) | replaced the verbatim full-`_wiki_overview()` embed with a LEAN dict: `stats` + `proposalCount` + `inboxCount` + `inboxTop[≤3 stubs]` + `orphanCount` + `orphanTop[≤3 stubs]` + `recentActivity[≤5]` + a structured `truncated` flag. Stub = `{id,title,status}` (NO rawContent — the bloat). `_jsonable(lean)` kept (recentActivity datetimes). |
| `tests/test_mcp_read.py` (+4) | lean-shape (key-set + counts + top-3 stubs no-rawContent + truncated flag) · size<3KB on a chunky vault · the standalone wiki_overview STILL full (source not shrunk) · honest-empty vault. |

## Design (LOCKED — bounded-output, point-don't-paste, source kept)
- **lean projection at the BRIEF layer (not the source):** the brief is a daily GLANCE → it carries COUNTS + top-N STUBS, not the full inbox dump. The fix is in `_brief_wiki`'s projection ONLY; `reader.overview()` (the source) is UNTOUCHED → the standalone `wiki_overview` MCP + REST `/wiki/overview` keep the FULL inbox WITH rawContent (the full-detail surface). This is the recheck-all-consumers discipline inverted: fix the bloated CONSUMER projection, leave the shared source intact for the other consumers.
- **point-don't-paste (principle #38 / #91 bounded):** the brief gives counts + top-3 + a `truncated.fullDetailVia: "wiki_overview"` pointer → an agent wanting the full inbox calls `wiki_overview` directly. Token-cheap glance + a named drill path.
- **cairn-#295 structured truncation:** `truncated = {inboxOmitted, orphansOmitted, recentCap:5, fullDetailVia}` — STRUCTURED policy-data (the agent reads what was omitted + where the full is), NOT a transport-baked prose hint.
- **#96 honest recentActivity preserved:** the capped-5 list is the already-#96-cleaned source (no dup/empty/soft-deleted) — just capped, not re-derived.
- **honest-empty:** empty vault → counts 0 + empty top-lists + the stats warning (unchanged honest behavior).

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** `_brief_wiki` builds the lean dict (stub drops rawContent); `_jsonable(lean)` kept; the `truncated` struct; reader/overview.py UNTOUCHED (git status clean — the source constraint). ✅
- **🔴 INDEPENDENT live size teeth (restart-then-measure, read_server not in reload allowlist):**
  - `brief.wiki` = **2,210 bytes (2.2KB)** — was 23KB → **10.4× cut**, PASS <3KB. ✅
  - `life_brief` total = **~12KB** — was ~33KB. ✅
  - lean shape: inboxCount=41 (real) + inboxTop=3 stubs (NO rawContent) + recentActivity=5 + truncated{inboxOmitted:38, fullDetailVia:"wiki_overview"}. ✅
  - still answers knowledge-state (stats + inboxCount). ✅
- **🔴 source NOT shrunk (the load-bearing OUT):** standalone `_wiki_overview()` → inbox len=41 (FULL) WITH rawContent; brief.inboxCount(41) == source(41). The brief points to the full; the full still BE there. ✅
- **Suite:** test_mcp_read.py 113 passed; FULL DEFAULT (`-m 'not slow'` deterministic, `-p no:randomly`) = **2230 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (2226→2230 = +4 #100 tests); never staged backend/data/.

## 3 Gates
- **Gate 1 (MCP/agent):** brief.wiki lean (counts + top-N stubs) + structured truncated flag + fullDetailVia pointer; honest-empty; source kept full (point-don't-paste). ✅
- **Gate 2 (Function):** the distinguishing teeth (lean-shape / size<3KB / source-still-full / honest-empty); independent live size + source-full; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY read_server.py + test_mcp_read.py + end doc (NO reader/overview.py source, no FE/data/.env); commit format. ✅

## Assumptions (user-review)
- **brief.wiki = counts + top-3 stubs + recentActivity≤5** (a glance, not the full dump). **Why:** a daily brief needs the knowledge-STATE (how many fleeting/orphan, the few most recent), not 41 full notes; the agent drills via wiki_overview. **How to change:** the `[:3]`/`[:5]` caps + the stub fields in `_brief_wiki`.
- **stubs drop rawContent/aiSuggest/captured** (id/title/status only). **How to change:** widen `_stub` if the agent needs more at a glance (costs tokens).
- **source (`reader.overview()`) NOT shrunk** — the standalone wiki_overview/REST keep the full inbox. **How to change:** n/a (intentional — the full-detail surface must stay full).

## Notes
- Cairn #100 — team-lead's dogfood: life_brief 70% was the wiki full-overview paste. backend-w3 built; architect committed (§3 sole-committer). The architect pre-Rule#0-verified the bloat (measured 23KB on the container, pinpointed inbox=15.5KB) BEFORE dispatching → the dispatch named the exact source + lean shape. Same bounded-output family as #91 (dev_activity) / #92 (life_brief mock-tag) — the cairn #294/#295 structured-truncation pattern reused. BE-only stage (read_server.py; source overview.py untouched). team-lead's NB: life_brief total is now ~12-19K (the 70% chunk gone); whether other sections are next is a DOGFOOD question → the next round will tell. After #100 → architect runs the dogfood round for the next gap (or confirms clean-hold).
