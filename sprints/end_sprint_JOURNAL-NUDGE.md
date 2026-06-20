# end_sprint_JOURNAL-NUDGE — build the rung-triggered nudge + close the decision loop (Cairn #14)

> Result. dogfood-R4 GAP-3. Committed TOGETHER with #18 (shared read_server.py + test_mcp_read.py, one backend pass) — commit `<hash>` `fix(sprint-JOURNAL-NUDGE+CLAUDE-USAGE-LEAN)`. Status: ✅ all 3 gates pass.

## Objective (met)
The SPEC'd `journal-nudge` ("price hits a ladder rung → remind to log a decision", §172) was NEVER built. decision_entries=0/brier=null is CORRECT (0 resolved) — the gap was the DARK calibration loop + nothing telling the user/agent to log. Built: the rung-triggered nudge (piggyback market-poll) + life_brief flags the empty loop + run_log attribution.

## What shipped
| File | Change |
|---|---|
| `market/service.py` | `check_rung_nudges()` — the nudge engine. Reads finance per-channel `LadderState.rungsIn`; high-water episode logic (live>stored→fire+bump mark; ==→no-fire; <→lower mark so a genuine re-entry re-fires — the dedup IS the high-water comparison, no separate table). Records a NEUTRAL pending nudge per new rung. Real-data-only (no ladder/mock → no fire). NEVER writes a journal/decision entry. |
| `market/router.py` | `_market_poll_work` — fail-SOFT add-on: PRIMARY poll status+detail computed FIRST, THEN the nudge check (a nudge failure can't downgrade a successful poll — fail-closed-write/fail-soft-add-on). A fired nudge records its own `journal-nudge` run_log row. |
| `store/db.py` | `journal_nudges` table + the per-channel high-water state + the nudge read. |
| `finance/service.py` | the ladder-state read the nudge consumes (lazy import to avoid a cycle). |
| `mcp_servers/read_server.py` | `_brief_decisions` loop-closer: `totalLogged` + a neutral `note` when 0 logged ("0 decisions logged — calibration/brier idle; the journal loop has no data yet (log a decision to start tracking)") + `pendingNudges` (open rung nudges). So an MCP agent reading life_brief SEES the dark loop + prompts the user. |
| `automation/service.py` | Part 3 — run_log routine attribution: 2 uncatalogued routine_ids registered (the "routine=None" was uncatalogued ids, not a literal null). |
| `tests/test_journal_nudge.py` (new) + reconciled automation tests | 13 tests. |

## NEUTRAL self-catch (honest-mirror discipline, by backend)
backend's OWN NEUTRAL test caught the nudge text "buy-ladder" (contains "buy" — the banned advice substring) → reworded "**entry-ladder**". The gate is "{channel} entered entry-ladder rung N … log a decision?" — a question, no buy/sell/should verb. (Same honest-mirror discipline the team applied in the DXY arc, self-applied here.)

## Verification (Rule #0)
- **team-lead live (life_brief):** decisions.totalLogged=0 + the neutral note + pendingNudges=[] — the dark loop is AGENT-VISIBLE (the goal-critical loop-closer). ladder_states={} live (user has no golden-path ladder) → NO live nudge fire = CORRECT honest behavior (real-data-only), engine proven via simulation + the 13 tests.
- **architect Rule#0:** check_rung_nudges high-water episode logic + the fail-soft add-on (status-before-addon) + the loop-closer traced; NEUTRAL text confirmed; 197 pass (journal_nudge+market+automation+mcp_read), 0 failed. backend cleaned its simulated nudge row (live store clean).
- **tester:** the 8-case (round-trip / dedup / episode re-entry / mock-no-fire / never-fabricate / NEUTRAL / 0-logged-note / fail-soft) — green (see tester report).

## 3 Gates — ALL PASS
- **Gate 1 (API):** life_brief.decisions additive (note + pendingNudges + totalLogged); activity attributes the journal-nudge run; integration green. ✅
- **Gate 2 (Function):** 13 tests incl. the episode-distinguishing (re-entry re-fires vs same-rung no-dup), never-fabricate boundary, NEUTRAL, fail-soft; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-function spot-check; team-lead live + architect Rule#0 + tester; counts ↑ (+13); commit format. ✅

## Assumptions (user-review)
- **journal-nudge piggybacks market-poll** (not a separate cron) — the trigger is a market event; responsive + fewer routines. **How to change:** extract to its own routine if needed.
- **Trigger = high-water `rungsIn` (live > stored mark)**; episode dedup falls out of the high-water comparison (re-entry after exit re-fires; same rung no-dup). **How to change:** the comparison is in check_rung_nudges.
- **Nudge = NEUTRAL pending REMINDER (a question), never a fabricated decision/journal entry + never advice** ("entry-ladder" not "buy-ladder" to pass the NEUTRAL gate). The user logs the actual decision. **How to change:** the nudge text + never-write boundary in check_rung_nudges.
- **life_brief.decisions flags 0-logged + surfaces pendingNudges** so an agent prompts the user. **How to change:** _brief_decisions in read_server.

## Notes
- A real new feature (routine wired to ladder events) — team-lead flagged to the user.
- Committed with #18 (claude_usage lean) — same dogfood batch, independent functions, shared read_server.py + test_mcp_read.py (one backend pass). See end_sprint_CLAUDE-USAGE-LEAN.md.
