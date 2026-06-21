# Sprint HARDENING — wiki_clusters topMembers + macro_cycle warnings + mypy 9→0 (#39/#40/#57)

> Created 2026-06-21 by architect. Hardening sprint (3 small diverse reversible tasks; priority-bumped to break the honest-mirror streak + clear small board tasks). Kickoff DROPPED #38 (already done). backend EDITS; architect commits (§3).

## Kickoff scope correction (Rule#0)
- **#38 DROPPED** — exchange dust-fold already applied (service.py:158 in get_overview path; MCP returns folded). Not a task.
- **#40 NARROWED** — macro_overview already forwards warnings; only macro_cycle missing.

## The 3 tasks
- **T1 #39 wiki_clusters +topMembers** (graph.py detect_clusters + ego builder): add `topMembers` = top-N member titles (deterministic, no-AI) for agent label-synthesis.
- **T2 #40 macro_cycle forward warnings** (read_server): {macroCycle} → {macroCycle, warnings}, mirror macro_overview.
- **T3 #57 mypy 9→0** (4 files): run-the-red each suspected real-bug; FIX at the right level (assert for invariants, scoped ignore-w-reason for plugin gotchas, annotation for genuine), NOT blanket-ignore.

## HARD GATE (distinguishing)
- #39 topMembers present, ≤N, subset of members. #40 macro_cycle mock-axis → warnings non-empty, all-real → empty. #57 mypy 0 (real bugs fixed not ignored).
- pytest 0-failed. Verify MCP changes on LIVE HTTP.

## Baseline
pytest 1971 (post-#46-P3). Keep 0-failed. mypy 9→0.

## Assumptions (user-review)
- #39 topMembers top-N deterministic; #40 macro_cycle forwards warnings; #57 no real bug existed (plugin-gotcha false-positives + provable invariants, fixed at the right level); #38 dropped (already done).

## Notes
- Hardening (§3.4b reactive-tier, multi-task). backend EDITS; architect commits. The #57 run-the-red verdict: no hidden bug behind the mypy errors.
