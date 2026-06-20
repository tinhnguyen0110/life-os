# end_sprint_REMINDERS-4 — reminders in the brief (Cairn #30, the "what's on my plate" payoff)

> Result. LANE A. The GAP-4 PAYOFF: reminders went from INERT-then-FIRING (#27/#28/#29) to VISIBLE in the agent-facing brief — an agent answering "what's on my plate this week" now gets them. Commit `<hash>` `feat(sprint-REMINDERS-4)`. Status: ✅ all 3 gates pass. **THE REMINDERS ARC IS COMPLETE** (storage→MCP→notify-fire→brief-visible); only #31 (FE tick UI) remains.

## Objective (met)
Surface un-done reminders in BOTH brief surfaces (recheck-all-consumers) so the consumer-agent's GAP-4 question is functionally answered. Additive, no reminders schema change — reuses the #29 reader.

## What shipped
| File | Change |
|---|---|
| `mcp_servers/read_server.py` | `_brief_reminders()` (life_brief section) — un-done overdue+today+week, LEAN {id,title,due_at,overdue}, band sort overdue→today→week, count+overdueCount, honest-empty + wired as the 10th `_section("reminders", _brief_reminders)`. |
| `modules/brief/service.py` | `_reminders_priority()` (daily_brief rule: overdue→urgent, due-today→warn, none→nothing) + `_RULE_ORDER` +reminders:6 + **`PRIORITY_CAP` 5→6** (so the 6th rule can't silently drop a sibling) + wired into the `rules` list. |
| `modules/brief/reader.py` | `Sources.reminders` field + `pull()` reads `reminders.service.list_reminders("undone")` in a fail-soft try/except (a reminders read error → warning, doesn't crash the pull). |
| `modules/brief/schema.py` | `PrioritySource` Literal +`reminders`. |
| tests | test_brief_reminders.py (new — both surfaces, the distinguishing fixture, fixture-timing note) + test_mcp_read.py + test_mcp_e2e.py (the new life_brief section). |

## The logic (both surfaces)
- **life_brief `_brief_reminders`:** week-view (un-done, due ≤ now+7d) ∪ undone-overdue (catches an overdue item MORE than a week past-due — it's outside ≤7d but MUST show). Band: overdue(0)→today(1)→this-week(2), due_at asc within band. LEAN 4-key per item; `count` + `overdueCount`; honest-empty `{reminders:[],count:0,overdueCount:0}` (source added by `_section`). fail-soft via `_section`.
- **daily_brief `_reminders_priority`:** any overdue → URGENT ("N nhắc nhở quá hạn"); else any due-today (un-done, not-overdue, due ≤ end-of-today UTC) → WARN ("N nhắc nhở đến hạn hôm nay"); none → nothing. 0-1 priority like the 5 siblings. Reads `src.reminders` (all-undone; the rule filters).
- **window:** this-week = due ≤ now+7d (ROLLING, team-lead-confirmed — matches #27, not calendar-week-end); a >7d item is EXCLUDED. done excluded (un-done only). overdue = the #29 reader field (un-done AND past-due).

## Verification (Rule #0 — architect 4-step + team-lead container)
- **architect 4-step (full functions):** `_brief_reminders` week∪undone-overdue union (correctly catches overdue >1wk past), band sort, lean shape, honest-empty; `_reminders_priority` overdue→urgent / due-today→warn / none→None, due-today predicate excludes overdue+done; reader.pull fail-soft try/except; schema Literal +reminders; PRIORITY_CAP 5→6 so the new 6th rule surfaces (not capped out). Confirmed mcp_servers/read_server.py carries ONLY #30 (no wiki #21/#22 — different file from modules/wiki/mcp/read_server.py, already in 8e0584f; grep-verified clean).
- **team-lead independent container (Rule#0, 5-reminder fixture):** life_brief.reminders count=3 overdueCount=1, order [OVERDUE(overdue:true)→TODAY(false)→INWEEK(false)]; OVERDUE+TODAY+INWEEK(≤7d) shown, NEXTWEEK(>7d) EXCLUDED (window boundary holds), DONE EXCLUDED. daily_brief.priorities: `reminders` source PRESENT (sources [reminders, projects, finance]) — the PRIORITY_CAP 5→6 ACTUALLY surfaces it (the built-but-not-surfaced risk, confirmed wired end-to-end), severity=urgent. Cleanup: none left (no pollution). 1806 suite green (+12), mypy clean.

## 3 Gates — ALL PASS
- **Gate 1 (API):** life_brief gains a `reminders` section (fail-soft via `_section`); daily_brief priorities carry a reminders entry; envelope intact. ✅
- **Gate 2 (Function):** the distinguishing fixture (overdue+today+in-window+OUT-of-window+done → 3 shown in band order, >7d+done excluded, count 3/overdueCount 1); daily_brief overdue→urgent; lean 4-key; honest-empty; fail-soft; the due==now-instantly-overdue fixture-timing note; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; architect 4-step + team-lead container; commit format; staged ONLY #30 files — git diff --cached confirms NO wiki #21/#22 (already in 8e0584f), no template/data leak. ✅

## Assumptions (user-review)
- **reminders surface in BOTH life_brief (a `reminders` section) AND daily_brief (a priority rule)** — un-done overdue/today/this-week, lean shape, sorted overdue→today→week. **How to change:** `_brief_reminders` (life_brief) + `_reminders_priority` (daily_brief).
- **this-week = due_at ≤ now+7d (ROLLING, NOT calendar-week-end)** — team-lead-confirmed. Why: consistency with #27's `week` filter (one predicate) + "this week" naturally = next 7 days (a calendar-week-end shows a near-empty week on a Saturday — useless). **How to change:** the week predicate in `list_reminders` / `_brief_reminders` (one line; touches #27's filter for consistency).
- **life_brief unions week ∪ undone-overdue** (so an overdue item >1wk past-due still shows, though outside ≤7d); daily_brief reads all-undone + the rule filters. done excluded; honest-empty.
- **PRIORITY_CAP bumped 5→6** (backend's own honest call) so the new 6th rule can't silently drop a sibling priority. **How to change:** `PRIORITY_CAP` in brief/service.py.

## Notes
- LANE A; separate commit. The wiki #21+#22 (modules/wiki/*) are already in 8e0584f — NOT re-staged. mcp_servers/read_server.py (the shared read-server) is a DIFFERENT file from modules/wiki/mcp/read_server.py (the wiki one) → no overlap.
- **GAP-4 ("a consumer-agent answers what's on my plate") is functionally MET** — storage→MCP→notify-fire→brief-visible all shipped. The reminders arc is complete; only #31 (FE tick UI, the user-facing surface) remains.
- Pipeline after: #31 (FE — needs the frontend agent) + wiki #23 (consolidate graph⊇backlinks⊇clusters → wiki_context) / #24 (test-gate REST≡MCP).
