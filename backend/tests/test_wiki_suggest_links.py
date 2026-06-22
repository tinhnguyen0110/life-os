"""tests/test_wiki_suggest_links.py — WIKI-SUGGEST-LINK (#34).

On a wiki note write-through, the response carries ``suggestedLinks`` — top 3-5 NEW link candidates
(FTS over the note's text) so the agent links the fresh note + keeps the graph connected. Deterministic
(FTS5 rank, NO AI), SUGGEST-ONLY (never auto-applies). EXCLUDES the note itself + notes already linked
from it. Honest-empty [] on no match.

Coverage (the dispatch's PASS bar):
- a note whose content matches an existing note → suggestedLinks includes it (id/title/score/relevance), top 3-5;
- THE DISTINGUISHING case: a note that LINKS [[X]] AND FTS-matches X → X is EXCLUDED (already-linked);
- content matching nothing → suggestedLinks: [] (honest-empty);
- #107: relevance = the #99 1-exp 0..1 (agent-readable, higher=more-relevant, descending best-first) —
  NOT the raw negative bm25; ``score`` carries the raw rank for parity with wiki_search;
- WIRED e2e (built-but-not-wired): the write-through RESPONSE (POST /wiki/notes) carries real
  suggestedLinks — not just the reader unit;
- the standalone tool/endpoint is REST≡MCP byte-identical (covered by the #24 parity gate; a focused
  check here too).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.mcp import read_server as mcp
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


@pytest.fixture
def api(wiki_db):
    from main import create_app
    return TestClient(create_app())


# --------------------------------------------------------------------------- #
# reader.suggest_links — the pure helper (unit)                                  #
# --------------------------------------------------------------------------- #
def test_suggest_includes_a_matching_note(wiki_db):
    """A note whose text shares terms with an existing note → that note is suggested, with
    {id, title, score, relevance} (#107: +score, relevance is the 0..1 1-exp)."""
    target = wsvc.create_note(NoteCreateInput(title="Compound Interest", content="money grows over time")).id
    # a new note about the same topic, NOT linked to target
    nid = wsvc.create_note(NoteCreateInput(title="Compound Interest revisited", content="how money grows")).id
    sug = reader.suggest_links(nid)
    ids = {s["id"] for s in sug}
    assert target in ids, "an FTS-matching, unlinked note must be suggested"
    hit = next(s for s in sug if s["id"] == target)
    assert set(hit) == {"id", "title", "score", "relevance"}
    assert hit["title"] == "Compound Interest"
    # #107: relevance is the agent-readable 0..1 1-exp (NOT the raw negative bm25 score)
    assert isinstance(hit["relevance"], float) and 0.0 <= hit["relevance"] < 1.0
    assert isinstance(hit["score"], float) and hit["score"] <= 0.0  # raw bm25 kept for transparency


def test_suggest_EXCLUDES_already_linked_note(wiki_db):
    """THE distinguishing case: a note that LINKS [[X]] AND FTS-matches X → X is EXCLUDED (it's
    already linked; suggesting it would be noise). A correct impl drops it; a naive 'just FTS' impl
    would wrongly include it — so this fixture distinguishes them."""
    x = wsvc.create_note(NoteCreateInput(title="Kelly Criterion", content="bet sizing math")).id
    # the new note both LINKS [[x]] AND repeats x's terms (so FTS WOULD match x)
    nid = wsvc.create_note(NoteCreateInput(
        title="Kelly Criterion notes", content=f"see [[{x}]] — more bet sizing math")).id
    sug_ids = {s["id"] for s in reader.suggest_links(nid)}
    assert x not in sug_ids, "an ALREADY-LINKED note must be excluded even though it FTS-matches"


def test_suggest_excludes_self(wiki_db):
    """The note never suggests linking to ITSELF (it FTS-matches its own terms most strongly)."""
    nid = wsvc.create_note(NoteCreateInput(title="Self Reference", content="unique-token-xyzzy")).id
    assert nid not in {s["id"] for s in reader.suggest_links(nid)}


def test_suggest_honest_empty_on_no_match(wiki_db):
    """Content matching NOTHING else in the vault → [] (honest-empty, not fabricated)."""
    # only one note in the vault, with a unique term → nothing else to match
    nid = wsvc.create_note(NoteCreateInput(title="Zzqxk Unique", content="zzqxk qwertyuniquetoken")).id
    assert reader.suggest_links(nid) == []


def test_suggest_missing_note_is_empty(wiki_db):
    """A missing note id → [] (never raises)."""
    assert reader.suggest_links(999999) == []


def test_suggest_relevance_is_1exp_0to1_descending(wiki_db):
    """#107: relevance is the #99 1-exp 0..1 (agent-readable), more-relevant first → the list is
    sorted by relevance DESCENDING (higher = more relevant). All relevance ∈ [0,1), none negative;
    order best-first preserved (1-exp is monotonic in the raw score, so descending relevance ==
    the same best-first order the raw bm25 produced)."""
    wsvc.create_note(NoteCreateInput(title="Markov Chain", content="state transition probability"))
    wsvc.create_note(NoteCreateInput(title="Markov Decision Process", content="markov state reward"))
    nid = wsvc.create_note(NoteCreateInput(title="Markov models", content="markov state transition probability reward")).id
    sug = reader.suggest_links(nid)
    assert sug, "expected matches"
    rels = [s["relevance"] for s in sug]
    # #107: every relevance is 0..1 (NOT negative) — the agent-readable contract
    assert all(0.0 <= r < 1.0 for r in rels), f"relevance must be in [0,1), got {rels}"
    # ordered most-relevant first → descending relevance (1-exp monotonic → same best-first order)
    assert rels == sorted(rels, reverse=True), "suggestions must be best-first (relevance descending)"
    # and raw score stays available + monotone-consistent (more-negative = better = first)
    scores = [s["score"] for s in sug]
    assert scores == sorted(scores), "raw bm25 score still ascending (most-negative first) — order intact"


def test_suggest_caps_at_limit(wiki_db):
    """Never returns more than ``limit`` (default 5; the 3-5 band)."""
    for i in range(8):
        wsvc.create_note(NoteCreateInput(title=f"Stoicism {i}", content="virtue control dichotomy"))
    nid = wsvc.create_note(NoteCreateInput(title="Stoicism summary", content="virtue control dichotomy")).id
    assert len(reader.suggest_links(nid)) <= 5
    assert len(reader.suggest_links(nid, limit=3)) <= 3


# --------------------------------------------------------------------------- #
# WIRED e2e — the write-through RESPONSE carries suggestedLinks (built-but-not-wired) #
# --------------------------------------------------------------------------- #
def test_create_response_carries_suggested_links(api):
    """POST /wiki/notes (write-through) → the response data carries real suggestedLinks for a
    note matching an existing one. Exercises the WIRED path, not just the reader unit."""
    api.post("/wiki/notes", json={"title": "Deliberate Practice", "content": "focused skill repetition"})
    r = api.post("/wiki/notes", json={"title": "Deliberate Practice deep-dive",
                                      "content": "focused skill repetition with feedback"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert "suggestedLinks" in data, "write-through response must carry suggestedLinks (the WIRED field)"
    titles = {s["title"] for s in data["suggestedLinks"]}
    assert "Deliberate Practice" in titles
    for s in data["suggestedLinks"]:
        assert set(s) == {"id", "title", "score", "relevance"}  # #107: +score, relevance 0..1
        assert 0.0 <= s["relevance"] < 1.0


def test_create_response_suggested_links_empty_when_no_match(api):
    """A first/unique note → write-through response suggestedLinks is [] (honest-empty), not omitted."""
    r = api.post("/wiki/notes", json={"title": "Qqzzx Singleton", "content": "qqzzx nomatchtoken"})
    assert r.status_code == 200
    assert r.json()["data"]["suggestedLinks"] == []


def test_update_response_carries_suggested_links(api):
    """PUT /wiki/notes/{id} (edit write-through) also carries suggestedLinks (re-FTS the edited text)."""
    other = api.post("/wiki/notes", json={"title": "Spaced Repetition", "content": "memory recall interval"}).json()["data"]["id"]
    nid = api.post("/wiki/notes", json={"title": "Memory note", "content": "unrelated"}).json()["data"]["id"]
    # edit it to match the other note
    r = api.put(f"/wiki/notes/{nid}", json={"content": "memory recall interval scheduling"})
    assert r.status_code == 200
    assert other in {s["id"] for s in r.json()["data"]["suggestedLinks"]}


def test_create_response_excludes_already_linked(api):
    """e2e distinguishing: a note created with [[X]] that ALSO matches X in FTS → X excluded from the
    write-through suggestedLinks (already linked)."""
    x = api.post("/wiki/notes", json={"title": "Antifragile", "content": "gains from disorder volatility"}).json()["data"]["id"]
    r = api.post("/wiki/notes", json={"title": "Antifragile applied",
                                      "content": f"[[{x}]] gains from disorder volatility in practice"})
    assert r.status_code == 200
    assert x not in {s["id"] for s in r.json()["data"]["suggestedLinks"]}


# --------------------------------------------------------------------------- #
# standalone endpoint/tool — REST≡MCP byte-identical (the #24 parity gate covers this too) #
# --------------------------------------------------------------------------- #
def test_standalone_rest_endpoint(api):
    """GET /wiki/notes/{id}/suggested-links → {suggestedLinks:[...]}; 404 on missing."""
    api.post("/wiki/notes", json={"title": "Via Negativa", "content": "subtraction improvement"})
    nid = api.post("/wiki/notes", json={"title": "Via Negativa notes", "content": "subtraction improvement design"}).json()["data"]["id"]
    r = api.get(f"/wiki/notes/{nid}/suggested-links")
    assert r.status_code == 200
    assert "suggestedLinks" in r.json()["data"]
    assert api.get("/wiki/notes/999999/suggested-links").status_code == 404


def test_mcp_tool_byte_identical_to_rest(api):
    """#24: MCP wiki_suggest_links(id) == REST /suggested-links data, byte-identical."""
    import json
    api.post("/wiki/notes", json={"title": "Lindy Effect", "content": "longevity expected lifespan"})
    nid = api.post("/wiki/notes", json={"title": "Lindy notes", "content": "longevity expected lifespan books"}).json()["data"]["id"]
    rest = api.get(f"/wiki/notes/{nid}/suggested-links").json()["data"]
    mcp_res = mcp.wiki_suggest_links(nid, limit=5)
    assert json.dumps(rest, sort_keys=True) == json.dumps(mcp_res, sort_keys=True)
