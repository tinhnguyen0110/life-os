"""tests/test_wiki_clusters.py — W5a SYNTHESIZE substrate (cluster detection + MOC).

Coverage:
  - detect_clusters: a ≥3-note dense group surfaces; isolated/under-threshold notes
    don't; density + importance computed; ranked; suggestedTitle is a real member.
  - moc noteType: a moc proposal applies as a noteType="moc" note; /wiki/mocs lists
    only mocs; concept/literature notes excluded.
  - endpoints: GET /wiki/clusters ranked + honest empty; GET /wiki/mocs.
  - ego_graph.clusters now populated (was []).

The cluster detector reads the RESOLVED-edge graph, so tests seed real [[links]].
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import proposals_service as psvc
from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki import proposals_store as pstore
from modules.wiki.proposals_schema import ProposalCreateInput
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


def _triangle() -> list[int]:
    """3 mutually-linked notes (a dense cluster: all 3 internal edges present)."""
    a = wsvc.create_note(NoteCreateInput(title="Alpha", content="x")).id
    b = wsvc.create_note(NoteCreateInput(title="Beta", content=f"[[{a}]]")).id
    c = wsvc.create_note(NoteCreateInput(title="Gamma", content=f"[[{a}]] [[{b}]]")).id
    return [a, b, c]


# --------------------------------------------------------------------------- #
# detect_clusters                                                              #
# --------------------------------------------------------------------------- #
def test_dense_triangle_is_a_cluster(wiki_db):
    ids = _triangle()
    clusters = reader.detect_clusters()
    assert len(clusters) == 1
    c = clusters[0]
    assert c["size"] == 3
    assert {m["id"] for m in c["members"]} == set(ids)
    assert c["density"] == 1.0  # 3 edges / max 3
    assert c["importance"] == round(3 * 1.0, 3)
    assert c["suggestedTitle"] in {"Alpha", "Beta", "Gamma"}
    # #39 (HARDENING): topMembers — top-N member titles for label synthesis, deterministic (no AI),
    # a SUBSET of members[].title, capped at N (=5).
    assert "topMembers" in c
    member_titles = {m["title"] for m in c["members"]}
    assert set(c["topMembers"]) <= member_titles, "topMembers must be a subset of member titles"
    assert len(c["topMembers"]) <= 5 and len(c["topMembers"]) == min(3, 5)  # this triangle has 3
    # deterministic: same call → same topMembers (no AI, stable order)
    assert reader.detect_clusters()[0]["topMembers"] == c["topMembers"]


def test_isolated_notes_are_not_a_cluster(wiki_db):
    wsvc.create_note(NoteCreateInput(title="lonely1"))
    wsvc.create_note(NoteCreateInput(title="lonely2"))
    assert reader.detect_clusters() == []


def test_two_note_link_under_min_size(wiki_db):
    a = wsvc.create_note(NoteCreateInput(title="A")).id
    wsvc.create_note(NoteCreateInput(title="B", content=f"[[{a}]]"))
    # 2 < min_size(3) → not a cluster
    assert reader.detect_clusters() == []


def test_sparse_group_under_density_threshold(wiki_db):
    # a path a-b-c-d-e (4 edges among 5 nodes): density 4/10 = 0.4 ≥ 0.30 → IS a cluster.
    # Make it sparser: a star with a long tail so density dips below 0.30.
    # 6-node path: 5 edges / max 15 = 0.33 (still ≥0.30). Use a 7-node path: 6/21=0.286 <0.30.
    ids = [wsvc.create_note(NoteCreateInput(title=f"N{i}")).id for i in range(7)]
    for i in range(1, 7):
        wsvc.update_note(ids[i], NoteUpdateInput(content=f"[[{ids[i-1]}]]"))
    clusters = reader.detect_clusters()
    # 7-node path: 6 undirected edges / 21 max = 0.286 < 0.30 → excluded
    assert clusters == []


def test_clusters_ranked_by_importance(wiki_db):
    # cluster 1: dense triangle (importance 3.0). cluster 2: 4-node denser-ish.
    _triangle()
    # a separate 4-node near-complete cluster
    w = wsvc.create_note(NoteCreateInput(title="W")).id
    x = wsvc.create_note(NoteCreateInput(title="X", content=f"[[{w}]]")).id
    y = wsvc.create_note(NoteCreateInput(title="Y", content=f"[[{w}]] [[{x}]]")).id
    wsvc.create_note(NoteCreateInput(title="Z", content=f"[[{w}]] [[{x}]] [[{y}]]"))
    clusters = reader.detect_clusters()
    assert len(clusters) == 2
    # importance desc — the 4-node complete graph (4*1.0=4.0) outranks the triangle (3.0)
    assert clusters[0]["size"] == 4 and clusters[1]["size"] == 3
    assert clusters[0]["importance"] >= clusters[1]["importance"]


# --------------------------------------------------------------------------- #
# moc noteType + /wiki/mocs                                                     #
# --------------------------------------------------------------------------- #
def test_moc_proposal_applies_as_moc_notetype(wiki_db):
    a = wsvc.create_note(NoteCreateInput(title="member")).id
    p = psvc.create_proposal(ProposalCreateInput(
        kind="moc", payload={"title": "MOC: theme", "content": f"- [[{a}]]"},
    ))
    accepted = psvc.accept_proposal(p["id"])
    note = wsvc.get_note(accepted["appliedNoteId"])
    assert note.noteType == "moc"


def test_mocs_lists_only_moc_notes(wiki_db):
    wsvc.create_note(NoteCreateInput(title="a concept", noteType="concept"))
    moc = wsvc.create_note(NoteCreateInput(title="a moc", noteType="moc")).id
    items = reader.mocs()["items"]
    assert len(items) == 1 and items[0]["id"] == moc


def test_mocs_empty_is_honest(wiki_db):
    wsvc.create_note(NoteCreateInput(title="just a concept"))
    assert reader.mocs() == {"items": []}


# --------------------------------------------------------------------------- #
# ego_graph.clusters populated                                                  #
# --------------------------------------------------------------------------- #
def test_ego_graph_clusters_populated(wiki_db):
    ids = _triangle()
    g = reader.ego_graph(ids[0], 2)
    assert g is not None
    assert len(g["clusters"]) == 1
    assert {m["id"] for m in g["clusters"][0]["members"]} <= set(ids)


# --------------------------------------------------------------------------- #
# API                                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(wiki_db):
    from main import app
    return TestClient(app)


def test_api_clusters_ranked(client):
    a = client.post("/wiki/notes", json={"title": "A"}).json()["data"]["id"]
    b = client.post("/wiki/notes", json={"title": "B", "content": f"[[{a}]]"}).json()["data"]["id"]
    client.post("/wiki/notes", json={"title": "C", "content": f"[[{a}]] [[{b}]]"})
    data = client.get("/wiki/clusters").json()["data"]
    assert len(data["clusters"]) == 1 and data["clusters"][0]["size"] == 3


def test_api_clusters_empty_honest(client):
    assert client.get("/wiki/clusters").json()["data"] == {"clusters": []}


def test_api_mocs(client):
    client.post("/wiki/notes", json={"title": "concept note"})
    # create a moc via proposal accept
    pid = client.post("/wiki/proposals", json={
        "kind": "moc", "payload": {"title": "MOC", "content": "x"},
    }).json()["data"]["id"]
    client.post(f"/wiki/proposals/{pid}/accept")
    items = client.get("/wiki/mocs").json()["data"]["items"]
    assert len(items) == 1 and items[0]["title"] == "MOC"
