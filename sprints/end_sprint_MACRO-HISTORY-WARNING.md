# end_sprint_MACRO-HISTORY-WARNING — honest warning on empty/feedless macro_history (Cairn #56 part 2)

> Result. `get_history` now carries an honest `warning` so an agent can tell feed-less-forever vs not-yet-recorded vs real-data apart on an empty series. Commit `<hash>` `fix(sprint-MACRO-HISTORY-WARNING)`. Status: ✅ all gates pass (committed LOCAL — push batch-pending, credential 403). backend-w3 EDITED (macro schema+service+test); architect 4-step + committed (§3).

## The gap (#56 part 2 — Rule#0, from the #56 kickoff)
`macro/service.py get_history` returned `MacroHistory{indicator, points:[]}` for a feed-less (dxy) or unprimed series with NO warning + no `warning` field on the schema. An agent calling `macro_history(dxy)` got `points:[]` and couldn't tell "no data YET" from "feed-less FOREVER" = honest-mirror gap. (#56 part 1 — suppress mock signals in consumers — was ALREADY done: decision excludes mock #59, life_brief doesn't read indicators, #62 fixed summarize, get_overview already warns. Verified by grepping all consumers at the kickoff.)

## What shipped
| File | Change |
|---|---|
| `modules/macro/schema.py` | `MacroHistory` +`warning: str \| None = None` (additive, defaulted → consumers + REST/MCP twin unaffected). Documented: feedless \| not-yet-recorded \| None (real data). |
| `modules/macro/service.py` | `get_history` populates `warning` by case (proper if/elif/else, display label via _LABELS): feedless (dxy ∈ _FEEDLESS_INDICATORS) → `"no live US Dollar Index (DXY) feed (dedicated API not built) — mock"` (mirrors _indicator_view); empty-but-trackable (0 points, not feedless) → `"<label> — no points yet (the daily snapshot / FRED refresh hasn't recorded any)"`; has real points → `None`. |
| `tests/test_macro.py` | +5: dxy→feedless warning (DXY label not raw 'dxy'); fear_greed empty→"no points yet"; fear_greed WITH a real point→warning None (THE distinguishing — an always-warn/never-warn impl FAILS); REST≡MCP byte-identical. |

## Design (LOCKED — mirror get_overview's honest-warning)
- **3-case warning** on get_history: feed-less / empty-trackable / real-data → distinct honest messages (or None). Uses the display label for consistency with _indicator_view.
- **Additive schema** — `warning` defaulted None; the REST + MCP twins both serialize the same MacroHistory (model_dump / _jsonable) → byte-identical (#24), warning flows through both.
- **SCOPE: get_history ONLY** — NOT get_overview (already warns), NO suppression/exclusion (part 1 already done), NO other indicator behavior.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** read the full warning block — control flow is correct `if feedless / elif not points / else None` (the earlier diff snippet stripped the elif/else keywords — confirmed proper branching on disk); schema additive; the 3 tests genuinely distinguish (feedless/empty/real); REST (router.py:41) + MCP (read_server.py:594) both call the same service.get_history → byte-identical by construction; scope = exactly 3 macro files (no leak).
- **backend-w3 evidence:** FULL pytest 1967/0 (LOCAL baseline 1962 + 5) + mypy clean; LIVE :8686 — dxy → feedless warning + points:0; cpi (10 real FRED points) → warning None; REST==MCP byte-identical.

## 3 Gates — ALL PASS
- **Gate 1 (API):** GET /macro/history + MCP macro_history carry the warning byte-identical (#24); additive schema (no break). ✅
- **Gate 2 (Function):** the feedless/empty/real distinguishing (warns-when-empty, None-when-real); proper if/elif/else; 0 errors; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step (control-flow verified) + backend live evidence; commit format; git-status clean; macro-only stage. ✅

## Assumptions (user-review)
- **macro_history carries a `warning` for empty/feed-less series** (feedless / not-yet-recorded / None-for-real) so an agent can interpret an empty `points:[]`. **How to change:** the if/elif/else block in get_history + the MacroHistory.warning field.
- #56 part 1 (suppress mock signals in consumers) NOT done here — already handled (verified at kickoff). part 1 = SKIP (no-overengineering; the symptom was fixed by #62 + the consumers already exclude mock).

## Notes
- Closes Cairn #56 (part 2; part 1 already done). Committed LOCAL — push batch-pending (credential 403, user re-auth). backend-w3 EDITS; architect commits (§3). Next (batch cap): #43 (costUSD) → STOP + reassess auth. honest-mirror pillar: an empty result must SAY WHY it's empty, never a bare points:[] the agent can't interpret.
