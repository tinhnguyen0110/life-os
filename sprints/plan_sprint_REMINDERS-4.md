# Sprint REMINDERS-4 — surface reminders in the brief (Cairn #30, the "what's on my plate" payoff)

> Created 2026-06-21 by architect. LANE A (priority). DESIGN to team-lead before dispatch (touches the brief + read_server/life_brief contract). Completes the reminders arc for the consumer-agent: storage✓ MCP✓ notify✓ → now VISIBLE in the brief so an agent answering "what's on my plate" actually gets them (the literal GAP-4 question).

## Objective
Make reminders show up in the agent-facing brief. The dogfood gap was "what's on my plate this week" returning nothing useful — #30 adds reminders to BOTH brief surfaces.

## WHERE — both surfaces (recheck-all-consumers lesson)
1. **life_brief** (read_server.py:937 — the consumer-agent's ONE-call synthesis): add a `reminders` section via `_section("reminders", _brief_reminders)` alongside the existing 9 (portfolio/market/projects/claude/decisions/macro/news/wiki/decision). This is the primary surface — an agent reading life_brief gets reminders in the whole-life snapshot.
2. **daily_brief** (brief/service.py — the 5-priority-rule generator): add a reminders PRIORITY rule — overdue reminders → an urgent priority entry ("N overdue reminders"); due-today → a warn/info entry. So the numbered daily brief flags reminders too.

## WHAT + SORT + SHAPE (team-lead's parameters)
- **WHAT:** un-done reminders that are OVERDUE or DUE-TODAY or DUE-THIS-WEEK. Use the `overdue` field (#29, = un-done+past-due) for severity. (Reuse `reminders.service.list_reminders` — it already has the today/week/undone filters; combine: overdue+today+week un-done.)
- **SORT:** overdue first (most urgent) → due-today → this-week, by due_at within each band.
- **SHAPE: LEAN** (the #18 claude_usage / reminders_list lean precedent) — per item `{id, title, due_at, overdue}` + a `count` (+ maybe `overdueCount`). NOT the full 10-field reminder. Agent-first.
- **HONEST:** empty plate → empty list + count 0 (NOT omitted/fabricated). fail-soft per the _section pattern (a reminders read error → {error, source} section, doesn't break the brief).

## Logic/Algorithm
- `_brief_reminders()` (read_server): call list_reminders for the relevant bands (overdue+today+week, un-done), map to the lean shape, sort overdue→today→week by due_at, return `{reminders:[{id,title,due_at,overdue}], count, overdueCount, source:"reminders"}`. Honest-empty.
- `_reminders_priority(reminders)` (brief/service): if any overdue → an URGENT priority ("N reminders overdue"); else if due-today → a WARN/INFO. Emits 0-1 priority like the other 5 rules. Reuses the reminders read.
- DECIDE-AND-LOG: "this-week" = due_at ≤ now+7d (matches the #27 `week` filter); the brief reminders are un-done only (done ones excluded).

## Tasks (when dispatched — after team-lead's design OK)
- **T1 (backend):** `_brief_reminders` + the life_brief section + the daily_brief reminders priority rule + tests. (Reuses the reminders reader — no schema change.)
- **T2 (tester):** life_brief has a reminders section (the distinguishing fixture); daily_brief flags overdue; lean shape; honest-empty.
- **T3 (architect):** review + commit `feat(sprint-REMINDERS-4)`.

## HARD GATE (distinguishing — team-lead's)
- A brief with [1 overdue + 1 due-today + 1 due-in-window (this-week, +5d ≤7d) + 1 due-OUT-of-window (+10d >7d) + 1 DONE] → life_brief.reminders shows the **3 un-done IN-WINDOW in order (overdue→today→this-week)** with overdue flagged; EXCLUDES the done one AND the >7d out-of-window one (count 3, overdueCount 1). [respects overdue + un-done + the band order + the week=≤7d window boundary]
  - ⚠ CONTRACT NOTE: "this-week" = due_at ≤ now+7d (locked, matches the #27 `week` filter). A literal "next week" (>7d) is OUT of window → EXCLUDED. The third SHOWN band is an in-window this-week item (≤7d); the >7d item is the negative case proving the boundary. (Earlier wording said "due-next-week" as a shown item — corrected: >7d is excluded, not shown.)
- empty plate → reminders:[] + count 0 (honest, not omitted).
- daily_brief: overdue reminders → an urgent priority entry; none → no spurious entry.
- lean shape (id/title/due_at/overdue + count), NOT the full reminder.
- fail-soft (a reminders read error → section {error}, brief still assembles).
- pytest green, mypy clean.

## Baseline
pytest 1787 (post-bedd888). Keep 0-failed.

## Assumptions (user-review)
- **reminders surface in BOTH life_brief (a `reminders` section) AND daily_brief (a priority rule)** — un-done overdue/today/this-week, lean shape, sorted overdue→today→week. **How to change:** `_brief_reminders` + the `_reminders_priority` rule.
- **this-week = due_at ≤ now+7d (ROLLING, NOT calendar-week-end)** — team-lead-confirmed decide-and-log. Why: (1) consistency with #27's existing `week` filter (one predicate, not two); (2) "what's on my plate this week" naturally means the next 7 days — a calendar-week-end window would show a near-empty week on a Saturday (useless). **How to change:** the week predicate in `list_reminders` / `_brief_reminders` (one line; would also touch #27's filter for consistency). done excluded; honest-empty.

## Notes
- LANE A priority; separate commit. Completes GAP-4 (an agent answering "what's on my plate" now gets reminders).
- recheck-all-consumers: BOTH brief surfaces (life_brief + daily_brief) — don't surface in one + miss the other.
- BRING TO team-lead before dispatch (brief/read_server contract).
