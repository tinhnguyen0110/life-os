# Sprint W8 — END

> A3 Agent Reliability Harness. New `modules/reliability/`. (A4 test-sweep runs in parallel on its own track — separate commit.)

## A3 — Agent Reliability Harness · ✅ SHIPPED + verified live (Rule#0 — architect + team-lead both ran the teeth)

**Commit:** `feat(sprint-W8): A3 reliability harness — grounding-eval + fail-closed gates + harness-self-test` (hash at commit).

### What shipped — the "supervise + trust the AI" thesis made a tool
A NEW `modules/reliability/` that RUNS + MEASURES the reliability of life-os's OWN agents (deterministic, no LLM):
- **grounding-eval** — an adversarial citation corpus run through the wiki citation-verify (A1b): a fabricated span MUST be rejected (`span_not_in_note`), a real one verified, null → ungrounded, nonexistent → rejected (`note_not_found`), empty → weakly_grounded. Exercises A1b through an adversarial lens.
- **fail-closed gates** — re-asserts the MCP read/write capability separation programmatically (read server has no write/mutate/enqueue symbol; write server is enqueue-only — has `create_proposal`, no accept/mutate).

### The load-bearing design: dependency injection → the harness self-tests
`run_grounding_eval(note_id, passage, checker_fn=None)` takes the checker via DI. So `test_reliability.py` runs the SAME eval against a deliberately-broken always-"verified" stub (→ harness MUST report FAIL) AND the real `verify_citations` (→ harness MUST report PASS). "A wrong harness is worse than none" — the self-test PROVES the harness discriminates. This IS the gate.

### Files
- `modules/reliability/{__init__,router,schema,service}.py` — `run_grounding_eval` (DI checker) + `run_fail_closed_check` (namespace gate) + `run_suite` (seeds a throwaway probe note, runs, cleans up). `MODULE = BaseModule(name="reliability")` auto-discovered (NO core edit). `GET /reliability` runs + reports.
- `tests/test_reliability.py` (8).

### Verified LIVE (architect Rule#0 + team-lead independently)
- **full pytest 1015 / 0 fail / 0 error** (incl. A4's parallel +20; A3 itself = +8), test_reliability 8 def==collected, mypy clean.
- **THE teeth (both run independently):** `test_harness_reports_FAIL_on_broken_target` PASSED (always-verified stub → harness reports FAIL on the fabricated/nonexistent/no-citation cases — catches the lie); `test_harness_reports_PASS_on_real_target` PASSED (real verify_citations → harness PASSES). The DI seam discriminates broken from real.
- **LIVE `GET /reliability`**: `passed=True`, checks=[grounding-eval ✓, fail-closed-gates ✓], 7/7 cases. `reliability` auto-discovered in /health (15 modules).
- (A host-side script hit a PermissionError writing container-owned `backend/data` — env quirk of running bare-metal against the container's files, NOT an A3 issue; the pytest fixture path + live API both prove the teeth.)

## Assumptions (user-review) — A3
1. **A3 = new `modules/reliability/`**, deterministic, life-os's OWN agents first (citation-verify + MCP gates). — why: cross-cutting harness, don't reinvent grounding — prove it. — to change: generalize to external/LLM agents (a bigger build) later.
2. **Harness self-test via DI** (broken-stub→FAIL, real→PASS) is the gate. — to change: nothing; this is the load-bearing correctness guarantee.
3. **`run_suite` seeds + deletes a throwaway probe note** on each `GET /reliability` (side-effect-free; cleanup best-effort + logged). — to change: use a read-only pre-seeded fixture note if the create/delete churn ever matters.
4. **fail-closed check = namespace inspection** (forbidden symbols absent + write server has create_proposal) — the same gate the AST tests prove, re-asserted at runtime. — to change: full AST walk if a symbol could be aliased.
