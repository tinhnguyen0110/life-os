"""tests/test_wiki_global_graph.py — GLOBAL-GRAPH T1: whole-vault graph as the default
/wiki/graph view + ``note`` optional on the endpoint (absent→global, present→ego).

THE distinguishing case (dispatch + team-lead locked): global node-count == count_notes()
AND ego(?note=X) returns ONLY the depth-2 neighborhood (fewer nodes) — proves global ≠
ego and the param actually switches modes. Ego behavior must stay UNCHANGED (regression).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.wiki import reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki import proposals_store as pstore
from modules.wiki.schema import NoteCreateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    return isolated_paths


def _seed_chain(n: int) -> list[int]:
    """n notes in a chain: note k links to note k-1 (so a depth-2 ego from an endpoint
    sees only ~3 of them, but global sees all n)."""
    ids = [wsvc.create_note(NoteCreateInput(title="N0", content="root")).id]
    for k in range(1, n):
        ids.append(wsvc.create_note(NoteCreateInput(title=f"N{k}", content=f"[[{ids[k-1]}]]")).id)
    return ids


# --------------------------------------------------------------------------- #
# global_graph reader                                                          #
# --------------------------------------------------------------------------- #
def test_global_graph_returns_whole_vault(wiki_db):
    ids = _seed_chain(6)
    g = reader.global_graph()
    assert g["center"] is None
    assert {n["id"] for n in g["nodes"]} == set(ids)        # ALL notes
    assert len(g["nodes"]) == wiki_store.count_notes()      # node-count == count_notes
    # node shape matches ego (id/title/status/degree)
    assert {"id", "title", "status", "degree"} <= set(g["nodes"][0].keys())
    # edges = all resolved edges, ego shape {source,target,type,isResolved}
    assert g["edges"], "a linked chain has resolved edges"
    assert {"source", "target", "type", "isResolved"} <= set(g["edges"][0].keys())
    assert "clusters" in g


def test_global_graph_empty_vault_is_honest_empty(wiki_db):
    g = reader.global_graph()
    assert g == {"center": None, "nodes": [], "edges": [], "clusters": []}


def test_global_clusters_are_full_not_ego_restricted(wiki_db):
    # a dense triangle → detect_clusters finds it; global carries the FULL cluster list
    a = wsvc.create_note(NoteCreateInput(title="A", content="x")).id
    b = wsvc.create_note(NoteCreateInput(title="B", content=f"[[{a}]]")).id
    wsvc.create_note(NoteCreateInput(title="C", content=f"[[{a}]] [[{b}]]"))
    g = reader.global_graph()
    assert g["clusters"] == reader.detect_clusters()  # full list, not ego-restricted


# --------------------------------------------------------------------------- #
# THE distinguishing case + ego regression (endpoint)                          #
# --------------------------------------------------------------------------- #
def test_endpoint_no_note_is_global_with_note_is_ego(wiki_db):
    import main
    ids = _seed_chain(6)  # chain N0<-N1<-...<-N5
    client = TestClient(main.create_app())

    # NO note → global: node-count == count_notes(), center null
    g = client.get("/wiki/graph").json()["data"]
    assert g["center"] is None
    assert len(g["nodes"]) == wiki_store.count_notes() == 6

    # ?note=endpoint → ego: depth-2 neighborhood ONLY (fewer than the whole chain)
    ego = client.get(f"/wiki/graph?note={ids[0]}").json()["data"]
    assert ego["center"] == ids[0]
    assert len(ego["nodes"]) < len(g["nodes"]), "ego must be a SUBSET (depth-2), not the whole vault"
    # the far end of the chain is NOT in the depth-2 ego of N0
    assert ids[5] not in {n["id"] for n in ego["nodes"]}


def test_endpoint_ego_unchanged_404_on_missing(wiki_db):
    import main
    client = TestClient(main.create_app())
    r = client.get("/wiki/graph?note=999999")
    assert r.status_code == 404  # ego regression: missing center still 404


def test_ego_graph_behavior_unchanged_regression(wiki_db):
    """ego_graph itself is untouched: center present, neighborhood-bounded, clusters key."""
    ids = _seed_chain(4)
    ego = reader.ego_graph(ids[1], depth=2)
    assert ego is not None
    assert ego["center"] == ids[1]
    assert "clusters" in ego
    assert reader.ego_graph(999999) is None  # missing → None (unchanged)
