# end_sprint_CLAUDE-USAGE-COST-LABEL — lean costUSD→costUSDAllTime (Cairn #43)

> Result. The MCP claude_usage LEAN output no longer juxtaposes an unlabeled lifetime cost with today-tokens — the key is now `costUSDAllTime` (clearly lifetime). Commit `b01abce` `fix(sprint-CLAUDE-USAGE-COST-LABEL)`. Status: ✅ all gates pass. backend-w3 EDITED (read_server lean projection + test); architect 4-step + committed (§3).

## The gap (Rule#0-grounded)
The MCP `claude_usage` LEAN output (read_server.py) put `today:211923` (token-TODAY) next to `costUSD:54956.58` — but that costUSD is the ALL-TIME LIFETIME sum (`sum(b.costUSD for b in by_model)`), NOT today's cost. An agent reads "$54,956 spent today" = absurd (211K tokens ≈ $0.5-2). Unlabeled lifetime-cost next to today-token = agent-misread (honest-mirror / agent-first-output gap).

## What shipped
| File | Change |
|---|---|
| `mcp_servers/read_server.py` | LEAN claude_usage projection: key `"costUSD"` → `"costUSDAllTime"` (value unchanged = the lifetime sum). An agent now reads "today:N tokens, costUSDAllTime:$54956 LIFETIME". Lean docstring updated (names it lifetime, not today). The VERBOSE/full shape (verbose=true) keeps `costUSD` UNCHANGED (the documented full-model field FE + REST /claude-usage consume). NO Pydantic schema change. |
| `tests/test_mcp_read.py` | 2 lean cost tests: lean has `costUSDAllTime` (NOT a bare `costUSD`); the distinguishing — lean=costUSDAllTime, verbose=costUSD (same value, distinct key per surface). |

## Design (LOCKED — decide-and-log, no-overengineering)
- **Lean-projection rename only** — the misread comes from the lean view's unlabeled key; rename it to make lifetime explicit. The FULL/verbose `costUSD` stays (renaming the schema field would break FE + REST).
- **NO costUSDToday** — a real today-cost isn't cheaply derivable (the series carries per-day TOTAL tokens, not per-day-per-model — computing today's per-model cost needs that breakdown). For a single-user app that's over-engineering. The rename alone eliminates the misread.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** lean dict line 498 = `"costUSDAllTime": cost_fmt` (renamed); verbose path (479/484) still `costUSD` (unchanged → no FE/REST break); docstring updated; scope exactly 2 files; recheck-all-consumers — grep brief/ for the lean key returned nothing (life_brief uses the FULL get_usage model, not the lean MCP projection — unaffected).
- **backend-w3 evidence:** FULL pytest 1967/0 + mypy clean; recheck-all-consumers (only the 2 tests read the lean key; FE/REST use FULL costUSD); LIVE :8686 — lean → costUSDAllTime present + bare costUSD ABSENT (next to today:2,920,075); verbose → costUSD present; values equal.

## 3 Gates — ALL PASS
- **Gate 1 (API):** the lean MCP projection key is self-describing (costUSDAllTime = lifetime); verbose/full + REST unchanged (no break); agent-first-output honored. ✅
- **Gate 2 (Function):** the lean-key-rename distinguishing (lean=costUSDAllTime, verbose=costUSD); 0 errors; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (rename + verbose-unchanged + recheck-consumers) + backend live evidence; commit format; git-status clean; 2-file stage. ✅

## Assumptions (user-review)
- **The lean claude_usage cost key = `costUSDAllTime`** (lifetime, explicit) — was a bare `costUSD` misreadable as today-cost next to today-tokens. The FULL/verbose shape keeps `costUSD`. **How to change:** the lean dict key in read_server.py.
- **NO `costUSDToday`** — not cheaply derivable (no per-day-per-model token data); the rename alone fixes the misread (no-overengineering). **How to change:** add per-day-per-model cost aggregation + a costUSDToday field if a real today-cost is ever wanted.

## Notes
- Closes Cairn #43. backend-w3 EDITS; architect commits (§3). agent-first-output pillar: a lean projection's field names must be self-describing — an agent reading only the output can't misinterpret a lifetime cost as a today cost. Next: #46-P3 → #37-40 → #17.
