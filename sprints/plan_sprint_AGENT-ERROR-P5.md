# Sprint AGENT-ERROR-P5 — journal-cluster REST errors → agent_error (Cairn #46 Phase 5)

> Created 2026-06-21 by architect (pre-grounded ∥ while backend does P4). #46-family Phase 5. Reuses the agent_error_response helper (P3 spine). HOLD dispatch until P4 commits (sequential, 1 backend/tree). backend EDITS; architect commits (§3).

## Context
P5 = journal + decision_journal + reminders + notes REST (~13 raw HTTPException). All 4 are agent-facing (reminders_list / journal_entries / decision_entries are MCP-consumed) → all migrate (selectivity passes). Almost all NOT_FOUND 404 + ONE special corrupt-file 422 (the nuance).

## Scope (Rule#0 pre-grounded — exact sites)
IN: journal/router.py + decision_journal/router.py + reminders/router.py + notes/router.py (+ helper import) + tests.
OUT: P6 modules. NO helper change (reuse P3's). NO service-logic change. NO 200-path change.

### All clean NOT_FOUND 404 (12 sites) → agent_error_response("NOT_FOUND", <msg>, hint="GET /<list> for valid ids")
- journal/router.py :42/58/66 "journal entry {id} not found"
- decision_journal/router.py :44/62/70 "decision {id} not found"
- reminders/router.py :57/67/76 "reminder {id} not found"
- notes/router.py :43/59/67 "note {id} not found"

### The ONE nuance — decision_journal :42 corrupt-file 422
`if entry is None: if entry_file_exists(id): raise 422 "malformed (corrupt entry file)"; else raise 404 "not found"`. The 422 = the file EXISTS but parses to None (data corruption) — distinct from not-found. Code choice (decide-and-log): **INVALID_INPUT is the closest closed-6 enum fit** BUT it's not really bad-input (the id is valid; the stored data is corrupt). Options: (a) INVALID_INPUT with a clear message+hint ("entry file corrupt; the id is valid but the stored data can't be parsed"), or (b) leave THIS one as a raw 422 (it's an honest data-integrity signal, agent rarely branches on it) + flag. LEAN (a) INVALID_INPUT for consistency (all errors agent-readable) with a message that makes the corrupt-vs-bad-input distinction clear. Confirm at kickoff / with team-lead if unsure — it's a genuine enum-fit judgment.

## HARD GATE (distinguishing)
- Each module bad-id → 404 flat {error:NOT_FOUND}. decision_journal corrupt-file → 422 flat {error:INVALID_INPUT} (the nuance — distinct from not-found; a flat all-NOT_FOUND impl FAILS the corrupt case). All flat {error:{code}}, NO {detail}.
- Verify on LIVE HTTP. pytest 0-failed, mypy clean.

## Baseline
pytest = post-P4 count (confirm at dispatch). Keep 0-failed.

## Assumptions (user-review)
- **journal/decision_journal/reminders/notes REST errors → flat agent_error** (NOT_FOUND) via the P3 helper. decision_journal corrupt-file → INVALID_INPUT (a valid id but unparseable stored data — honest, distinct from not-found). **How to change:** the per-route calls + the corrupt-file code choice.

## Notes
- #46 Phase 5 (P3/P4 done). Mostly mechanical (NOT_FOUND × the helper); the only judgment = the decision_journal corrupt-file 422 code (lean INVALID_INPUT). backend EDITS; architect commits fix(sprint-AGENT-ERROR-P5). HOLD until P4 commits. Verify LIVE HTTP. Next: P6 (read_server free-text + agent_proposals/automation/activity + the conflict/sync/proposal 404s = #17 folded).
