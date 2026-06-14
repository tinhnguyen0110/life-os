"""tests/test_reliability.py — Agent Reliability Harness (Sprint W8 A3).

THE HARNESS-SELF-TEST TEETH (non-negotiable gate, verify-with-the-distinguishing-case):
a wrong harness is worse than none, so we PROVE the harness discriminates:
  1. broken-target (always-"verified" stub) → harness REPORTS FAIL (catches the lie).
  2. real verify_citations → harness REPORTS PASS (every case actual==expected).
A harness that can't tell #1 from #2 is the failure mode this gate prevents.

Plus: the corpus cases land their expected statuses, the fail-closed gate check, and
the live GET /reliability + auto-discovery.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.reliability import service as rel
from modules.wiki import proposals_store as pstore
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


def _seed() -> tuple[int, str]:
    passage = "atomic notes hold exactly one idea"
    nid = wsvc.create_note(NoteCreateInput(title="probe", content=passage)).id
    return nid, passage


# --------------------------------------------------------------------------- #
# THE TEETH — the harness must DISCRIMINATE a broken target from a real one     #
# --------------------------------------------------------------------------- #
def _always_verified_stub(claims):
    """A deliberately-BROKEN checker: claims everything is verified, ignoring reality.
    The harness MUST report FAIL when run against this (it wrongly 'verifies' the
    fabricated/no-citation/nonexistent cases)."""
    return {"results": [{"status": "verified", "reason": None, "resolvedNoteId": None}
                        for _ in claims], "summary": {}}


def test_harness_reports_FAIL_on_broken_target(wiki_db):
    nid, passage = _seed()
    check = rel.run_grounding_eval(nid, passage, checker_fn=_always_verified_stub)
    # the stub passes the real_span case (coincidentally "verified") but FAILS the
    # fabricated/no-citation/nonexistent/weak cases → overall FAIL.
    assert check.passed is False
    failed = {c.label for c in check.cases if not c.passed}
    assert {"fabricated_span", "no_citation", "nonexistent_note", "weak"} <= failed


def test_harness_reports_PASS_on_real_target(wiki_db):
    nid, passage = _seed()
    check = rel.run_grounding_eval(nid, passage)  # default = real verify_citations
    assert check.passed is True
    assert all(c.passed for c in check.cases)
    # the anti-fabrication case actually rejected for the RIGHT reason
    fab = next(c for c in check.cases if c.label == "fabricated_span")
    assert fab.actual == "rejected" and fab.passed


def test_harness_records_case_failure_when_target_raises(wiki_db):
    nid, passage = _seed()

    def _raiser(claims):
        raise RuntimeError("boom")

    check = rel.run_grounding_eval(nid, passage, checker_fn=_raiser)
    # never crashes; every case FAILS with the error recorded.
    assert check.passed is False
    assert all(c.actual == "<error>" and "boom" in (c.detail or "") for c in check.cases)


# --------------------------------------------------------------------------- #
# corpus cases land their expected statuses (the grounding eval is correct)      #
# --------------------------------------------------------------------------- #
def test_corpus_covers_all_statuses(wiki_db):
    nid, passage = _seed()
    check = rel.run_grounding_eval(nid, passage)
    by_label = {c.label: c for c in check.cases}
    assert by_label["real_span"].actual == "verified"
    assert by_label["fabricated_span"].actual == "rejected"
    assert by_label["no_citation"].actual == "ungrounded"
    assert by_label["nonexistent_note"].actual == "rejected"
    assert by_label["weak"].actual == "weakly_grounded"


# --------------------------------------------------------------------------- #
# fail-closed gate check                                                         #
# --------------------------------------------------------------------------- #
def test_fail_closed_gates_pass(wiki_db):
    check = rel.run_fail_closed_check()
    assert check.passed is True
    assert {c.label for c in check.cases} == {
        "read_server_no_write_capability", "write_server_no_mutate_or_accept"}


# --------------------------------------------------------------------------- #
# suite assembler                                                               #
# --------------------------------------------------------------------------- #
def test_run_suite_passes_on_real_system(wiki_db):
    report = rel.run_suite()
    assert report.passed is True
    assert {chk.name for chk in report.checks} == {"grounding-eval", "fail-closed-gates"}
    assert report.summary["failed"] == 0 and report.summary["total"] > 0


# --------------------------------------------------------------------------- #
# API + auto-discovery                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(wiki_db):
    from main import app
    return TestClient(app)


def test_api_reliability_runs_and_passes(client):
    r = client.get("/reliability")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["passed"] is True
    assert data["summary"]["failed"] == 0
    names = {c["name"] for c in data["checks"]}
    assert names == {"grounding-eval", "fail-closed-gates"}


def test_api_auto_discovered_in_health(client):
    assert "reliability" in client.get("/health").json()["data"]["modules"]
