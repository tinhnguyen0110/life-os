# end_sprint_HARDENING — wiki_clusters topMembers + macro_cycle warnings + mypy 9→0 (#39/#40/#57)

> Result. 3 small diverse hardening tasks (#38 dropped — already done). Commit `<hash>` `fix(sprint-HARDENING)`. Status: ✅ all gates pass. backend-w3 EDITED (wiki/macro/exchange/career/claude_usage + 2 tests); architect 4-step + committed (§3).

## Kickoff corrections (Rule#0 — caught before dispatch)
- **#38 DROPPED** — exchange dust-fold ALREADY applied (service.py:158 _fold_dust in get_overview path; MCP returns folded). Not a task.
- **#40 NARROWED** — macro_overview already forwards warnings; only macro_cycle was missing.

## What shipped
| File | Change |
|---|---|
| `modules/wiki/reader/graph.py` (#39) | `topMembers` = top-5 member titles (_TOP_MEMBERS_N=5), deterministic (first N of id-sorted members), NO AI — in BOTH detect_clusters (:113) AND the ego-graph visible_clusters builder (:209, derived from the FILTERED visible members → a true subset). Lets an agent synthesize a cluster label. |
| `mcp_servers/read_server.py` (#40) | MCP macro_cycle → `{macroCycle, warnings}` (was {macroCycle}) — lifts the model's honest mock/thin-axis warning to a top-level list, mirroring macro_overview's {macro, warnings}. All-real axes → warnings empty. |
| `mcp_servers/proposals_service.py` (#57) | `assert row is not None` (the mark_decided transitioned=True ⇒ rowcount>0 ⇒ row non-None invariant — documents the store contract + catches a violation at runtime, NOT a blanket ignore) + scoped `# type: ignore[call-arg]` for the JournalInput pydantic-plugin gotcha (fields ARE defaulted). |
| `modules/career/schema.py` + `claude_usage/service.py` + `exchange/service.py` (#57) | career: removed a stale unused ignore. claude_usage:345: narrowed as_of to str via isinstance. exchange:58/144: narrowed the usd float guard + scoped ignore for the OkxBalance plugin gotcha. |
| tests | test_wiki_clusters.py (topMembers subset+deterministic), test_decision.py (macro_cycle warnings both arms). |

## #57 run-the-red verdict (the value of NOT blanket-ignoring)
The dispatch SUSPECTED 3 real bugs; backend ran-the-red on each → verdict: **NO real bug existed** — all 9 were either pydantic-plugin-gotcha false-positives (the env has no pydantic mypy plugin → defaulted model fields read as required [call-arg]) OR unprovable-but-true invariants. Each fixed at the RIGHT level: scoped `# type: ignore[call-arg]` w/ reason for the plugin gotcha · `assert` for the provable invariant (proposals_service rowcount) · annotation/narrowing for the genuine type issues. NONE blanket-ignored. (The honest "no real bug" verdict is itself the win — run-the-red prevented both a missed-bug AND a mask-the-symptom.)

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step:** #39 topMembers in both builders (deterministic, ego=subset); #40 macro_cycle → {macroCycle, warnings}; #57 — the `assert row is not None` is the right call for the invariant (not a mask), the scoped ignores are genuine plugin-gotchas (fields defaulted, verified); mypy "Success: 0 issues / 148 files"; scope exactly 8 files (no leak).
- **backend-w3 evidence:** FULL pytest 1972/0 (baseline 1971 + 1) + mypy 0; LIVE HTTP — #39 topMembers real subset, #40 macro_cycle {macroCycle, warnings:[]} (all-real → empty, honest).

## 3 Gates — ALL PASS
- **Gate 1 (API):** macro_cycle MCP now forwards warnings (agent-first context); topMembers self-describing. ✅
- **Gate 2 (Function):** topMembers deterministic+subset; macro_cycle warnings both arms (mock→non-empty, real→empty); #57 fixed at the right level (assert/ignore-w-reason/annotation); mypy 0; 0 errors. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend live-HTTP evidence + run-the-red verdict; commit format; git-status clean; HARDENING-only stage (8 files). ✅

## Assumptions (user-review)
- **#39 topMembers = top-5 id-sorted member titles** (deterministic, no-AI); ego version = subset of visible. **How to change:** _TOP_MEMBERS_N / the slice.
- **#40 macro_cycle forwards warnings** (mock/thin-axis → non-empty; all-real → empty), mirroring macro_overview. **How to change:** the warnings-lift in read_server macro_cycle.
- **#57: no real bug existed** — all 9 mypy errors were plugin-gotcha false-positives or provable invariants; fixed at the right level (assert/scoped-ignore/annotation), none blanket-ignored. #38 dropped (already done). **How to change:** the per-error fix.

## Notes
- Closes #39/#40/#57 (#38 dropped). backend-w3 EDITS; architect commits (§3). Next: #46-P4 (projects+career, pre-designed plan_sprint_AGENT-ERROR-P4.md) → P5 → P6 (+#17 folded) → #15. The run-the-red discipline confirmed no hidden bug behind the mypy errors — honest verdict, right-level fixes.
