"""tests/test_wiki_citations.py — citation post-verify (Sprint W6 A1b).

THE anti-fabrication guarantee (spec L120-121): a cited span that does NOT occur in
the note → rejected, so a fabricated citation can't be passed off as grounded.

Coverage incl. the DISTINGUISHING case (verify-with-the-distinguishing-case): a
collapsed impl that only checks "note exists" passes the verified case but FAILS the
fake-span case — that divergence is the teeth.

Tests co-located with the fn's own module (test-where-the-reader-greps). The fn is
PURE; the API tests use TestClient; an MCP-tool parity check confirms the read tool
returns the same result.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import citations
from modules.wiki import proposals_store as pstore
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# THE distinguishing case — a collapsed (note-exists-only) impl FAILS this      #
# --------------------------------------------------------------------------- #
def test_distinguishing_case(wiki_db):
    nid = wsvc.create_note(NoteCreateInput(
        title="Atomicity", content="A note should hold exactly one idea.")).id
    real_span = "exactly one idea"
    out = citations.verify_citations([
        {"claim": "atomic", "noteId": nid, "span": real_span},        # verified
        {"claim": "fake", "noteId": nid, "span": "this text is NOT in the note"},  # rejected
        {"claim": "ghost", "noteId": 999999, "span": real_span},      # rejected note_not_found
        {"claim": "bare", "noteId": None, "span": None},              # ungrounded
        {"claim": "named", "noteId": nid, "span": ""},                # weakly_grounded
    ])
    r = out["results"]
    assert r[0]["status"] == "verified"
    # the TEETH: same real note, fabricated span → MUST reject (not verify).
    assert r[1]["status"] == "rejected" and r[1]["reason"] == "span_not_in_note"
    assert r[2]["status"] == "rejected" and r[2]["reason"] == "note_not_found"
    assert r[3]["status"] == "ungrounded"
    assert r[4]["status"] == "weakly_grounded"
    assert out["summary"] == {"verified": 1, "rejected": 2, "ungrounded": 1,
                              "weaklyGrounded": 1, "total": 5}


# --------------------------------------------------------------------------- #
# per-status unit cases                                                         #
# --------------------------------------------------------------------------- #
def test_verified_span_in_body(wiki_db):
    nid = wsvc.create_note(NoteCreateInput(title="T", content="the quick brown fox")).id
    out = citations.verify_citations([{"claim": "c", "noteId": nid, "span": "quick brown"}])
    assert out["results"][0]["status"] == "verified"
    assert out["results"][0]["resolvedNoteId"] is None  # no redirect


def test_verified_span_in_title(wiki_db):
    # title is in scope — a citation to a titular claim verifies.
    nid = wsvc.create_note(NoteCreateInput(title="Spaced Repetition", content="body")).id
    out = citations.verify_citations([{"claim": "c", "noteId": nid, "span": "Spaced Repetition"}])
    assert out["results"][0]["status"] == "verified"


def test_multiline_span_normalized(wiki_db):
    nid = wsvc.create_note(NoteCreateInput(
        title="T", content="first line\nsecond line\nthird line")).id
    # the span has different whitespace (newline vs space) — normalization matches it.
    out = citations.verify_citations([{"claim": "c", "noteId": nid,
                                       "span": "first line   second line"}])
    assert out["results"][0]["status"] == "verified"


def test_case_sensitive_mismatch_rejected(wiki_db):
    nid = wsvc.create_note(NoteCreateInput(title="T", content="Atomicity Principle")).id
    # case-SENSITIVE: lowercase span does not match the capitalized text.
    out = citations.verify_citations([{"claim": "c", "noteId": nid, "span": "atomicity principle"}])
    assert out["results"][0]["status"] == "rejected"


def test_ungrounded_no_noteid(wiki_db):
    out = citations.verify_citations([{"claim": "c", "noteId": None, "span": "x"}])
    assert out["results"][0]["status"] == "ungrounded" and out["results"][0]["reason"] == "no_citation"


def test_weakly_grounded_whitespace_span(wiki_db):
    nid = wsvc.create_note(NoteCreateInput(title="T", content="body")).id
    out = citations.verify_citations([{"claim": "c", "noteId": nid, "span": "   "}])
    assert out["results"][0]["status"] == "weakly_grounded"


# --------------------------------------------------------------------------- #
# defensive cases                                                               #
# --------------------------------------------------------------------------- #
def test_empty_claims(wiki_db):
    assert citations.verify_citations([]) == {
        "results": [],
        "summary": {"verified": 0, "rejected": 0, "ungrounded": 0,
                    "weaklyGrounded": 0, "total": 0},
    }


def test_zero_and_negative_noteid_rejected(wiki_db):
    out = citations.verify_citations([
        {"claim": "c", "noteId": 0, "span": "x"},
        {"claim": "c", "noteId": -5, "span": "x"},
    ])
    assert all(r["status"] == "rejected" and r["reason"] == "note_not_found"
               for r in out["results"])


def test_span_longer_than_note_rejected(wiki_db):
    nid = wsvc.create_note(NoteCreateInput(title="T", content="short")).id
    out = citations.verify_citations([{"claim": "c", "noteId": nid,
                                       "span": "short" * 100}])
    assert out["results"][0]["status"] == "rejected" and out["results"][0]["reason"] == "span_not_in_note"


def test_merged_away_noteid_follows_redirect(wiki_db):
    # cite a note, then MERGE it away; the stale citation still verifies against the
    # target + reports resolvedNoteId (a merged citation must NOT be rejected).
    src = wsvc.create_note(NoteCreateInput(title="dupe", content="merge survives test")).id
    tgt = wsvc.create_note(NoteCreateInput(title="canon", content="merge survives test")).id
    wsvc.merge_notes(src, tgt)  # src → tombstone → tgt
    out = citations.verify_citations([{"claim": "c", "noteId": src, "span": "merge survives test"}])
    r = out["results"][0]
    assert r["status"] == "verified"
    assert r["resolvedNoteId"] == tgt  # the citation pointed at the merged-away id


# --------------------------------------------------------------------------- #
# API + MCP parity                                                              #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(wiki_db):
    from main import app
    return TestClient(app)


def test_api_verify_endpoint(client):
    nid = client.post("/wiki/notes", json={"title": "T", "content": "alpha beta gamma"}).json()["data"]["id"]
    r = client.post("/wiki/citations/verify", json={"claims": [
        {"claim": "ok", "noteId": nid, "span": "beta gamma"},
        {"claim": "bad", "noteId": nid, "span": "not here"},
    ]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["results"][0]["status"] == "verified"
    assert data["results"][1]["status"] == "rejected"
    assert data["summary"]["total"] == 2


def test_api_empty_claims(client):
    r = client.post("/wiki/citations/verify", json={"claims": []})
    assert r.status_code == 200 and r.json()["data"]["summary"]["total"] == 0


def test_mcp_tool_parity(wiki_db):
    from modules.wiki.mcp import read_server
    nid = wsvc.create_note(NoteCreateInput(title="T", content="parity body")).id
    claims = [{"claim": "c", "noteId": nid, "span": "parity body"}]
    assert read_server.wiki_verify_citations(claims) == citations.verify_citations(claims)
