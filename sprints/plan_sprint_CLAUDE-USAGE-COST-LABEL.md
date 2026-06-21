# Sprint CLAUDE-USAGE-COST-LABEL — lean costUSD→costUSDAllTime (Cairn #43)

> Created 2026-06-21 by architect. Reactive sprint (QA/dogfood-flagged agent-first-output misread). backend-w3 EDITS read_server lean projection; architect commits (§3).

## The gap
The MCP claude_usage LEAN output put `today:211923` (token-today) next to `costUSD:54956.58` (the ALL-TIME LIFETIME sum, `sum(by_model.costUSD)`) — an agent reads "$54,956 spent today" = absurd. Unlabeled lifetime-cost next to today-token = agent-misread.

## The fix (decide-and-log, no-overengineering)
- LEAN projection (read_server.py): rename key `costUSD` → `costUSDAllTime` (value unchanged = lifetime sum). Update the lean docstring.
- VERBOSE/full keeps `costUSD` (FE + REST consume the full-model field — don't break). NO Pydantic schema change.
- NO `costUSDToday` — not cheaply derivable (series has per-day TOTAL tokens, not per-day-per-model); over-engineering for 1 user. The rename alone fixes the misread.

## HARD GATE (distinguishing)
- Lean claude_usage → `costUSDAllTime` present, bare `costUSD` ABSENT. Verbose/full → `costUSD` present (unchanged). Same value, distinct key per surface.
- recheck-all-consumers: no other reader of the lean key (life_brief uses the FULL model; FE/REST use full costUSD).
- pytest 0-failed, mypy clean.

## Baseline
pytest 1967 (post-#56-part2). Keep 0-failed.

## Assumptions (user-review)
- **Lean cost key = `costUSDAllTime`** (lifetime, explicit); FULL/verbose keeps `costUSD`. **How to change:** the lean dict key.
- **NO costUSDToday** — not cheaply derivable; rename alone fixes the misread (no-overengineering).

## Notes
- Reactive sprint (§3.4b), agent-first-output family. backend EDITS; architect commits. Tiny (~2-line rename + docstring + 2 tests).
