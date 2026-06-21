# Sprint MACRO-HISTORY-WARNING — honest warning on empty/feedless macro_history (Cairn #56 part 2)

> Created 2026-06-21 by architect (next lane after #14, design-only while #14 implements). LOW honest-mirror gap. #56 part 1 = ALREADY DONE (decision excludes mock #59 + life_brief doesn't read indicators + summarize fixed by #62 + macro_overview already warns) — verified at the #56 kickoff by grepping ALL consumers. THIS = part 2 only. HOLD dispatch until #14 commits (sequential, 1 backend/tree).

## The gap (Rule#0-grounded — #56 kickoff)
`macro/service.py get_history(indicator)` returns `MacroHistory{indicator, points:[...]}` — a feed-less indicator (dxy) or an unprimed sentiment series returns `points:[]` with **NO warning + no explanation**. The `MacroHistory` schema has NO `warning` field at all. So an agent calling `macro_history(dxy)` gets `points:[]` + (MCP) `found:true` and CANNOT tell "no data YET" from "feed-less FOREVER" = an honest-mirror gap (the agent can't interpret the empty).

Contrast: `get_overview()` ALREADY warns honestly (service.py:19-20: "macro data is mock (no live FRED source) — values are placeholders"). `get_history` should mirror that.

## The fix (DECIDED — decide-and-log, mirror get_overview)
1. **`MacroHistory` schema** (macro/schema.py:73): ADD `warning: str | None = None` (additive, defaulted → existing consumers + REST/MCP twin unaffected).
2. **`get_history`** (macro/service.py): when the series is empty OR the indicator is feed-less (`indicator in _FEEDLESS_INDICATORS`), populate `warning`:
   - feed-less (dxy): `"dxy — no live feed (dedicated API not built); series empty/mock until a real feed exists"` (reuse the `_FEEDLESS_INDICATORS` + the get_overview feedless-warning wording for consistency).
   - empty-but-trackable (sentiment not yet snapshotted): `"<indicator> — no points yet (the daily snapshot routine hasn't recorded any)"`.
   - has real points: `warning=None`.
3. NO suppression/exclusion logic (part 1 already handled by the consumers) — this is PURELY the honest warning on the read.

## HARD GATE (distinguishing)
- `get_history("dxy")` → `points:[]` (or mock) + `warning` NAMING the feed-less reason (NOT None, NOT empty). A real indicator (e.g. fed_funds_rate with FRED points) → `warning=None`. The distinguishing: a feed-less/empty read carries the warning; a real-data read does NOT (an impl that always-warns or never-warns FAILS).
- REST `GET /macro/history?indicator=dxy` == MCP `macro_history` byte-identical (#24, the warning flows through both).
- pytest 0-failed, mypy clean.

## Baseline
pytest = post-#14 count (confirm at dispatch). Keep 0-failed. +~2 tests (feedless→warning, real→no-warning).

## Assumptions (user-review)
- **macro_history carries a `warning` for empty/feed-less series** (mirrors get_overview's honest mock-warning) so an agent can interpret an empty `points:[]`. **How to change:** the warning-population branch in get_history + the MacroHistory.warning field.
- #56 part 1 (suppress mock signals in consumers) = NOT done here — already handled (decision excludes mock #59; life_brief doesn't read indicators; #62 fixed summarize; get_overview warns). Verified at kickoff by grepping all consumers.

## Notes
- LOW honest-mirror. backend EDITS macro (schema + service) → architect 4-step + commits `fix(sprint-MACRO-HISTORY-WARNING)`. Tiny (~10 lines + 2 tests). HOLD until #14 commits (sequential). SPLIT from #14 (different module: macro vs wiki) — clean single-theme commit.
- honest-mirror pillar: an empty result must SAY WHY it's empty (no-data-yet vs feed-less-forever), never a bare `points:[]` the agent can't interpret.
