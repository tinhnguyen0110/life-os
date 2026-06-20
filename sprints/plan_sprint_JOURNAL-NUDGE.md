# Sprint JOURNAL-NUDGE — build the rung-triggered journal-nudge + close the decision loop (Cairn #14, dogfood-R4 GAP-3)

> Created 2026-06-21 by architect. team-lead APPROVED the design (piggyback market-poll, all-3-one-sprint, episode-based dedup). A real new feature (a routine wired to ladder events) — team-lead flagged it to the user.

## The gap (dogfood-R4)
decision_entries=0, journal_entries=0, openCount=0, brier=null — the whole calibration/brier machinery sits DARK because nothing captures data, AND nothing tells the user/agent the loop is empty. The SPEC'd `journal-nudge` ("khi giá chạm rung → nhắc ghi quyết định", §172) was NEVER built (not in the 10 registered routines; the "fired once 2026-06-06" was a misread). brier=null/openCount=0 is CORRECT (0 resolved → nothing to compute) — the gap is the dark loop + no nudge to log.

## Design (APPROVED — 3 parts, one sprint)
**Part 1 — the rung-triggered nudge, piggybacked on market-poll.** The trigger IS a market event (rung hit) → fire the nudge-check INSIDE market-poll (`market/router.py` `_market_poll_work`), NOT a separate cron (responsive — catches the rung when it happens; no new routine = no-overengineering). market-poll already evals rules + writes run_log → natural home.
- Read finance overview's per-channel `LadderState.rungsIn` (finance/schema.py:140).
- Persist per-channel `lastRungsIn` (a small state — `journal_nudges` table or a tiny state row). A nudge fires when **`rungsIn > lastRungsIn`** (a NEW rung entered). Store the new rungsIn after.
- **Episode-based dedup FOR FREE:** because the trigger is `rungsIn > lastRungsIn`, a rung that's already-entered won't re-fire (rungsIn unchanged); but if price EXITS (rungsIn drops, lastRungsIn updated down) then RE-ENTERS (rungsIn rises past it again) → `rungsIn > lastRungsIn` again → re-fires. Genuine re-entry = a new episode = re-nudge. No per-rung dedup table needed. (This is cleaner than dedup-by-(channel,rung) + a reset path — the lastRungsIn comparison IS the episode logic.)
- On fire → record a **pending nudge** (NEVER a journal entry — never fabricate the user's decision): `{channel, rung, triggerPrice, observedPrice, ts, status:"pending"}` into `journal_nudges` + a `db.record_run`-style activity event under a `journal-nudge` routine_id.
- NEUTRAL (guardian-style): the nudge is a QUESTION/observation ("crypto entered buy-ladder rung -20% @ $X — log your decision?"), NEVER "you should buy." Real-data-only: no ladder data / mock → NO nudge. Fail-soft per channel (a nudge failure must NOT break market-poll's primary work — set market-poll status BEFORE the nudge add-on, per fail-closed-write-fail-soft-addon).

**Part 2 — life_brief.decisions flags the dark loop + surfaces pending nudges (the loop-closer).** In `mcp_servers/read_server._brief_decisions`: when decision_entries total == 0 → a neutral `note: "0 decisions logged — calibration/brier idle; the journal loop has no data yet"`; ALWAYS surface `pendingNudges: [...]` (the open nudges). So an MCP agent reading life_brief KNOWS to prompt the user to log. Honest-empty, never fabricated.

**Part 3 — (minor) run_log routine attribution.** The activity feed shows routine=None for some runs; small shape fix so the nudge (+ others) attribute their routine_id correctly.

## Surfaces
The nudge lands in: (a) a `journal_nudges` read (a small reader — under journal or its own tiny surface), (b) `life_brief.decisions.pendingNudges`, (c) the activity feed (the run_log event). + an MCP read tool if cheap (list pending nudges) — optional, log if deferred.

## Tasks
- **T1 (backend, gating):** the nudge engine (rungsIn-vs-lastRungsIn trigger + journal_nudges store + the pending-nudge record) piggybacked in market-poll (fail-soft add-on) + Part 2 (life_brief empty-state note + pendingNudges) + Part 3 (run_log routine attribution) + tests. Backend writes pytest.
- **T2 (tester):** the rung-trigger→nudge→surface ROUND-TRIP live (force a rung entry → nudge recorded → appears in life_brief.pendingNudges + activity) + dedup (same rung no dup; re-entry re-fires) + empty-state flag + NEUTRAL (no advice verb) + never-fabricates-an-entry.
- **T3 (architect):** 4-step review + commit.

## HARD GATE (distinguishing)
- A rung NEWLY entered (rungsIn↑) → pending nudge recorded + surfaces in life_brief.decisions.pendingNudges + activity. [the build]
- SAME rung already-nudged (rungsIn unchanged) → NO duplicate. [dedup]
- Price exits + RE-enters (rungsIn drops then rises past it) → re-fires (a new episode). [episode-based — the distinguishing vs once-ever]
- 0 decisions → life_brief.decisions flags the empty/dark state (the neutral note). [loop-closer]
- mock / no-ladder-data → NO nudge (real-data-only, guardian-style). [honest]
- The nudge NEVER fabricates a journal/decision entry (only a pending REMINDER). [boundary]
- NEUTRAL: no buy/sell/should verb in the nudge text (the NEUTRAL gate). [advice-risk]
- market-poll's primary work unaffected by a nudge add-on failure (fail-soft, status-before-addon). [fail-closed-write-fail-soft-addon]
- pytest green, mypy clean.

## Baseline
pytest 1688 (post-DXY-HONEST). Keep 0-failed; expect +6-10 (the round-trip + dedup + episode + empty-state + neutral + boundary cases).

## Assumptions (user-review)
- **journal-nudge piggybacks market-poll** (not a separate cron) — the trigger is a market event; responsive + fewer routines. **How to change:** extract to its own routine if ladder granularity needs a different cadence.
- **Trigger = `rungsIn > lastRungsIn`** (a new buy-ladder rung entered); episode-based dedup falls out of the lastRungsIn comparison (re-entry after exit re-fires). **How to change:** the comparison is in the nudge engine.
- **Nudge = NEUTRAL pending REMINDER (a question), never a fabricated decision/journal entry + never advice.** The user logs the actual decision; the nudge only prompts. **How to change:** the nudge text + the never-write-entry boundary are in the engine.
- **life_brief.decisions flags 0-logged + surfaces pendingNudges** so an agent prompts the user. **How to change:** _brief_decisions in read_server.

## Notes
- A real new feature (routine wired to ladder events) — team-lead flagged to the user for awareness.
- Fail-soft add-on on market-poll (a broken nudge must not break the poll) — fail-closed-write-fail-soft-addon.
- NEUTRAL gate is load-bearing (the nudge is advice-adjacent) — same gate as guardian/allocation.
