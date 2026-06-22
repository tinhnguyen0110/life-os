# end_sprint_bt2-wiki-inbox-softdelete — wiki inbox excluded soft-deleted notes (the 63-vs-34 leak)

> Backend-backlog sprint, Task B-T2. The wiki triage inbox counted SOFT-DELETED fleeting notes (inbox 63 vs byStatus.fleeting 34 — irreconcilable to a user/agent). Root cause: `fleeting_notes()` was the ONE live query missing the `deleted_at IS NULL` filter its siblings have. 1-line fix. Surfaced by #143 /wiki W2.

## What shipped (2 files)
- **backend/modules/wiki/store/queries.py — `fleeting_notes()`:** added `AND deleted_at IS NULL` →
  `SELECT * FROM wiki_notes WHERE status = 'fleeting' AND deleted_at IS NULL ORDER BY created ASC, id ASC` + a docstring noting it's the live-filter the siblings (all_notes/count_notes/count_by_status) all had + the #94 intent (soft-deleted notes hide from the inbox like the tree/search).
- **backend/tests/test_wiki_inbox_softdelete.py (NEW, 5 behavior tests):** soft-deleted-excluded-from-inbox · inbox-count-reconciles-byStatus (the 63-vs-34 distinguishing case) · store-query-excludes-soft-deleted · restore-returns-to-inbox (symmetry — soft-delete is reversible) · developing-not-in-inbox (status-filter control). All BEHAVIOR-tested (create→soft-delete→assert), not field-reads.

## Why (the bug)
`count_by_status()` (queries.py:53) filtered `deleted_at IS NULL` → byStatus.fleeting = 34 (LIVE). But `fleeting_notes()` (the inbox source, queries.py:200) had NO such filter → it counted soft-deleted fleeting notes → 63. It was the ONLY live query missing the filter. Effect: a real DATA-CORRECTNESS LEAK — notes the user "deleted" still appeared in the active triage inbox, and the inbox count was irreconcilable with byStatus to any user/agent. MCP wiki_overview calls the SAME `reader.overview()` (read_server.py:97), so the one fix reconciles BOTH surfaces.

## Verify (architect 4-step + independent live reconcile — Rule#0)
1. **git diff:** queries.py (1-line + docstring) + the new test file ONLY. No stray.
2. **Read full:** the fix matches the sibling live queries exactly; 5 behavior tests cover the bug + the reconcile distinguishing-case + restore symmetry + status control.
3. **Independent LIVE REST reconcile (verify-on-http, Rule#0):** I curled `GET /wiki/overview` → `inbox.length=34 == byStatus.fleeting=34, reconciled=True` (was 63 vs 34). Ran the new test myself → **5 passed**.
4. **Hunt:** backend reported FORWARD 2506/0 + REVERSE 2506/0 + mypy clean + TEETH-PROVEN (revert the filter → the reconcile test FAILS = bug reproduces). team-lead independently verified BOTH surfaces live (REST 34/34 + MCP via full HTTP handshake 34/34, NOT import-cache).

## Gates
- Gate 1 (API): the read endpoint now returns reconcilable counts; covered by the new behavior tests + existing wiki suite. ✓
- Gate 2 (Function): behavior tests (not field-reads); teeth-proven; mypy clean; forward+reverse green. ✓
- Gate 3 (Sprint): this doc + 4-step + independent live REST reconcile + team-lead's dual-surface verify + count grew by 5 new tests. ✓

## Assumptions (user-review)
- **The inbox = LIVE fleeting only (excludes soft-deleted), matching count_by_status + the #94 soft-delete intent.** A soft-deleted note hides from the inbox like it hides from the tree/search; a restore brings it back (verified by the restore-symmetry test). How to change: nothing — this aligns the inbox with the rest of the soft-delete behavior.

## Lesson (→ memory)
Adding a #94 soft-delete filter to one query → GREP EVERY "live" query for a missing `deleted_at IS NULL`. One sibling (`fleeting_notes`) missed it → an inflated/leaky count for months. (The thread-through-family discipline, like the #117 new-required-field family.)

## Commit
- Hash: (filled) — `fix(sprint-bt2-wiki-inbox-softdelete): exclude soft-deleted from the triage inbox (the 63-vs-34 leak)`
- Files: backend/modules/wiki/store/queries.py + backend/tests/test_wiki_inbox_softdelete.py + this doc.
- team-lead gate PASSED (dual-surface live reconcile). Push after commit.
