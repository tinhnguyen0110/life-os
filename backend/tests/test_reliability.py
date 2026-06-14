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


def test_S2_forbidden_set_includes_low_level_store_writers():
    # F2-S2: the forbidden sets must include the low-level proposal-store mutators,
    # not just the high-level service fns (a tool reaching insert_proposal/mark_decided
    # is just as much a write capability).
    assert {"insert_proposal", "mark_decided"} <= rel._READ_FORBIDDEN
    assert "mark_decided" in rel._WRITE_FORBIDDEN


def test_S2_distinguishing_a_leaked_symbol_is_caught(wiki_db):
    # F2-S2 TEETH (verify-with-the-distinguishing-case): if a forbidden symbol WERE
    # reachable from a server's tool surface, the gate MUST catch it. We build a fake
    # "server" whose tool closes over `insert_proposal` and assert _tool_reachable_symbols
    # surfaces it (so run_fail_closed_check would report leaked). A gate that can't
    # catch a planted leak is worthless.
    def _leaky_tool():  # a tool that (pretends to) reach a write fn
        return None
    _leaky_tool.__globals__["insert_proposal"] = lambda *a, **k: None  # plant the leak

    class _FakeServer:
        TOOLS = {"leaky": _leaky_tool}

    surface = rel._tool_reachable_symbols(_FakeServer)
    assert "insert_proposal" in surface  # the planted forbidden symbol IS surfaced
    assert "insert_proposal" in (rel._READ_FORBIDDEN & surface)  # → would be flagged leaked
    # cleanup the planted global so it can't leak into other tests
    _leaky_tool.__globals__.pop("insert_proposal", None)


# --------------------------------------------------------------------------- #
# suite assembler                                                               #
# --------------------------------------------------------------------------- #
def test_run_suite_passes_on_real_system(wiki_db):
    # seed a real note so grounding runs the full corpus (not the empty-vault skip).
    _seed()
    report = rel.run_suite()
    assert report.passed is True
    assert {chk.name for chk in report.checks} == {"grounding-eval", "fail-closed-gates"}
    assert report.summary["failed"] == 0 and report.summary["total"] > 0


def test_H2_run_suite_is_read_only(wiki_db, monkeypatch):
    # F2-H2: GET /reliability (run_suite) must NOT write the vault. Stronger than a
    # count check (which a create+delete nets to zero): SPY on md_store.write_file +
    # delete_file and assert NEITHER is called during the suite. (team-lead's gate:
    # "GET /reliability twice → 0 new git commits".)
    _seed()
    from store import md_store
    writes: list = []
    monkeypatch.setattr(md_store, "write_file",
                        lambda *a, **k: writes.append(("write", a)))
    monkeypatch.setattr(md_store, "delete_file",
                        lambda *a, **k: writes.append(("delete", a)))
    rel.run_suite()
    rel.run_suite()  # twice
    assert writes == [], f"run_suite wrote the vault: {writes}"


def test_H2_empty_vault_skips_grounding_no_write(wiki_db):
    # empty vault → grounding honestly skipped (not a false pass, not a write).
    before = wiki_store.count_notes()
    report = rel.run_suite()
    assert wiki_store.count_notes() == before == 0
    grounding = next(c for c in report.checks if c.name == "grounding-eval")
    assert grounding.passed is True
    assert grounding.cases[0].label == "skipped_empty_vault"


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
