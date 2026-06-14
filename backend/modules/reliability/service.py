"""modules/reliability/service.py — the reliability harness runner (Sprint W8 A3).

Deterministic, no LLM. Runs life-os's own agent-reliability checks:
  - grounding-eval: an adversarial citation corpus through `verify_citations` —
    a fabricated span MUST be rejected, a real one verified, etc.
  - fail-closed gates: the MCP read/write servers have no write/mutate capability.

DEPENDENCY INJECTION is the load-bearing design (verify-with-the-distinguishing-case):
``run_grounding_eval`` takes the ``checker_fn`` as a parameter, so the harness can be
run against the REAL `verify_citations` (→ PASS) OR a deliberately-broken stub that
always returns "verified" (→ the harness REPORTS FAIL on the fabricated cases). A
harness that can't tell those apart is worthless — the self-test proves it can.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from modules.wiki import citations as wiki_citations
from modules.wiki import service as wiki_service

from .schema import CaseResult, CheckResult, ReliabilityReport

logger = logging.getLogger("life-os.reliability.service")

# The checker contract: takes a list of claim dicts, returns {results:[{status,reason,...}], ...}
CheckerFn = Callable[[list[dict[str, Any]]], dict[str, Any]]


# --------------------------------------------------------------------------- #
# Grounding-eval corpus — built against a seeded note (id + a known passage P)  #
# --------------------------------------------------------------------------- #
def _grounding_corpus(note_id: int, passage: str) -> list[dict[str, Any]]:
    """The adversarial citation corpus (label, input, expected_status, expected_reason?).
    Mixes attack cases (fabricated/nonexistent → must reject) WITH legit cases
    (real span → verified) so the harness doesn't over-reject (DevCrew allow-guard)."""
    return [
        {"label": "real_span", "input": {"noteId": note_id, "span": passage},
         "expected": "verified", "expected_reason": None},
        {"label": "fabricated_span",
         "input": {"noteId": note_id, "span": "this string is definitely NOT in the note"},
         "expected": "rejected", "expected_reason": "span_not_in_note"},
        {"label": "no_citation", "input": {"noteId": None, "span": "x"},
         "expected": "ungrounded", "expected_reason": None},
        {"label": "nonexistent_note", "input": {"noteId": 999999, "span": "x"},
         "expected": "rejected", "expected_reason": "note_not_found"},
        {"label": "weak", "input": {"noteId": note_id, "span": ""},
         "expected": "weakly_grounded", "expected_reason": None},
    ]


def run_grounding_eval(note_id: int, passage: str,
                       checker_fn: CheckerFn | None = None) -> CheckResult:
    """Run the grounding corpus through ``checker_fn`` (default: the REAL
    verify_citations). Each case passes iff the checker's status (+ reason where
    specified) matches expected. A target that RAISES → that case FAILS (the harness
    never crashes on a target error). The check passes iff every case passes."""
    checker = checker_fn or wiki_citations.verify_citations
    cases: list[CaseResult] = []
    for c in _grounding_corpus(note_id, passage):
        expected = c["expected"]
        try:
            out = checker([c["input"]])
            result = out["results"][0]
            actual = result.get("status", "")
            ok_status = actual == expected
            # where a reason is specified, it must match too (the anti-fabrication
            # check is "rejected FOR span_not_in_note", not just "rejected").
            exp_reason = c.get("expected_reason")
            ok_reason = exp_reason is None or result.get("reason") == exp_reason
            passed = ok_status and ok_reason
            detail = None if passed else f"reason={result.get('reason')!r}"
        except Exception as exc:  # noqa: BLE001 — a target error is a case FAILURE, not a crash
            actual = "<error>"
            passed = False
            detail = f"target raised: {exc}"
        cases.append(CaseResult(label=c["label"], expected=expected, actual=actual,
                                passed=passed, detail=detail))
    return CheckResult(name="grounding-eval", passed=all(c.passed for c in cases), cases=cases)


# --------------------------------------------------------------------------- #
# Fail-closed gates — the MCP read/write servers' capability separation         #
# --------------------------------------------------------------------------- #
# Mutation/enqueue symbols a READ tool must never be able to reach. F2-S2 broadened
# to include the LOW-LEVEL store writers (insert_proposal/mark_decided) — not just the
# high-level service fns — so a tool can't reach a writer one layer down either.
_READ_FORBIDDEN = {
    "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
    "enqueue", "create_proposal", "accept_proposal", "reject_proposal", "batch_accept",
    "proposals_service", "insert_proposal", "mark_decided",
}
# The WRITE tool may enqueue (create_proposal/insert_proposal) but must NOT mutate a
# note or accept/reject a proposal (the human ratifies).
_WRITE_FORBIDDEN = {
    "create_note", "update_note", "delete_note", "merge_notes", "refine_note",
    "enqueue", "accept_proposal", "reject_proposal", "batch_accept", "mark_decided",
}


def _tool_reachable_symbols(server_module: object) -> set[str]:
    """F2-S2: the names reachable from the server's REGISTERED TOOLS surface — each
    tool fn's own globals (the module scope it actually closes over), NOT just the
    server module's top-level `vars()`. A tool that imported a write fn into its module
    scope would be caught here even if the server's top-level namespace looked clean.
    Union of every registered tool's __globals__ keys + the module's own top-level."""
    names: set[str] = set(vars(server_module))
    tools = getattr(server_module, "TOOLS", {})
    for fn in tools.values():
        g = getattr(fn, "__globals__", {})
        names |= set(g.keys())
    return names


def run_fail_closed_check() -> CheckResult:
    """Re-assert the MCP gates programmatically (deterministic surface check, the same
    gate test_wiki_mcp_read/write prove): the READ server's tool surface exposes no
    write/mutate/enqueue symbol; the WRITE server's no accept/mutate symbol (it may
    only enqueue). F2-S2: checks the REGISTERED-TOOLS reachable surface (each tool's
    __globals__), not just the module's top-level vars()."""
    from modules.wiki.mcp import read_server, write_server

    cases: list[CaseResult] = []

    read_surface = _tool_reachable_symbols(read_server)
    read_leaked = sorted(_READ_FORBIDDEN & read_surface)
    cases.append(CaseResult(
        label="read_server_no_write_capability",
        expected="no_write_symbols", actual="clean" if not read_leaked else "leaked",
        passed=not read_leaked,
        detail=None if not read_leaked else f"leaked: {read_leaked}"))

    write_surface = _tool_reachable_symbols(write_server)
    write_leaked = sorted(_WRITE_FORBIDDEN & write_surface)
    # the write server SHOULD reach create_proposal (enqueue-only) — sanity, not a leak.
    cases.append(CaseResult(
        label="write_server_no_mutate_or_accept",
        expected="enqueue_only", actual="clean" if not write_leaked else "leaked",
        passed=not write_leaked and "create_proposal" in write_surface,
        detail=None if (not write_leaked and "create_proposal" in write_surface)
        else f"leaked: {write_leaked} create_proposal_present={'create_proposal' in write_surface}"))

    return CheckResult(name="fail-closed-gates", passed=all(c.passed for c in cases), cases=cases)


# --------------------------------------------------------------------------- #
# Suite assembler                                                               #
# --------------------------------------------------------------------------- #
def _assemble(checks: list[CheckResult]) -> ReliabilityReport:
    all_cases = [c for chk in checks for c in chk.cases]
    passed_n = sum(1 for c in all_cases if c.passed)
    return ReliabilityReport(
        checks=checks,
        passed=all(chk.passed for chk in checks),
        summary={"total": len(all_cases), "passed": passed_n,
                 "failed": len(all_cases) - passed_n},
    )


def _pick_probe_note() -> tuple[int, str] | None:
    """F2-H2: pick an EXISTING vault note (read-only) + a real passage from its body
    to run the grounding corpus against — so GET /reliability NEVER writes the vault
    (the old run_suite seeded+deleted a note PER CALL = a vault write every request).
    Returns (note_id, passage) or None if the vault has no usable note."""
    from modules.wiki import store as wiki_store
    for row in wiki_store.all_notes(order_by="id"):
        note = wiki_service.get_note(int(row["id"]))
        if note is None:
            continue
        # a passage genuinely in the note: prefer a body slice, else the title.
        body = (note.content or "").strip()
        if body:
            return note.id, body[:60]
        if note.title.strip():
            return note.id, note.title.strip()
    return None


def run_suite() -> ReliabilityReport:
    """Run the full reliability suite (grounding-eval against the REAL verify_citations
    + the fail-closed gates). READ-ONLY (F2-H2): verifies against an EXISTING note, no
    vault write. Empty vault → the grounding check is reported skipped (honest, still
    no write). This is what GET /reliability serves."""
    probe = _pick_probe_note()
    if probe is not None:
        note_id, passage = probe
        grounding = run_grounding_eval(note_id, passage)
    else:
        # nothing to verify against — honest skip, NOT a false pass, NOT a write.
        grounding = CheckResult(
            name="grounding-eval", passed=True,
            cases=[CaseResult(label="skipped_empty_vault", expected="n/a", actual="n/a",
                              passed=True, detail="no vault note to verify against")])
    fail_closed = run_fail_closed_check()
    return _assemble([grounding, fail_closed])
