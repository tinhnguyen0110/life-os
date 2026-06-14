# Sprint W8 — A3 Agent Reliability Harness · PLAN

> DISPATCH Sprint 3. New `modules/reliability/`. Single gating piece (backend). FE reliability-view = optional follow-on.

## Objective
Close the scattered agent-reliability defenses (DevCrew red-team, OutboundOS grounding/provenance) into ONE
life-os module that runs/measures the reliability of life-os's OWN agents — concretely the wiki citation-verify
(A1b) + the MCP no-write/no-mutate gates. = the "supervise + trust the AI" thesis made a tool.

## Kickoff — 2026-06-14

### Reuse references (read on disk, not just cited)
- **DevCrew** `lab/security/attack_payloads.py` — attack-corpus shape `(label, payload, expected: deny|allow)`,
  grouped by technique, WITH allow-case regression guards (don't over-reject legit input). + `test_attacks.py` runner.
- **OutboundOS** `test_reply_validator.py` + `validate_golden.py` — validator-as-tool with a clean-payload-PASSES
  regression case (no-false-positive guard); refuse-path-as-first-class.
- **life-os own targets** (test FIRST): `modules/wiki/citations.py` `verify_citations` (deterministic grounding
  checker: verified/rejected/ungrounded/weakly_grounded) + `modules/wiki/mcp/{read,write}_server.py` (AST no-write/no-mutate gates).

### Architecture decision (logged)
**NEW `modules/reliability/`** (router/schema/service), auto-discovered like decision_journal. NOT folded into wiki —
it's cross-cutting (will test multiple agents over time). Deterministic only (no LLM/live-agent calls), no new deps,
life-os's own agents first (generalize later).

### The critical constraint (the gate)
**A wrong harness is worse than none → the harness has its OWN teeth-tests.** A deliberately-broken target stub
(always-returns-verified) run through the harness → harness REPORTS FAIL on the fabricated cases; the real
`verify_citations` → harness PASSES. Both asserted. This is the distinguishing case — without it a green harness is meaningless.

### Final task list (W8)
- **A3 [backend]** — new `modules/reliability/`: grounding-eval (citation-verify corpus) + fail-closed checker (MCP gates) + the harness-self-test teeth. `GET /reliability` runs the suite + reports. Full §3.3b dispatched.
- FE reliability-view → optional follow-on (not this sprint unless A4/A5 lanes idle).

## Assumptions (user-review) — finalized in end_sprint_W8.md
- A3 = new `modules/reliability/`, deterministic, life-os's own agents first (citation-verify + MCP gates). Generalize to external/LLM agents later.
- Harness self-test = the gate (broken-stub→FAIL, real→PASS).
