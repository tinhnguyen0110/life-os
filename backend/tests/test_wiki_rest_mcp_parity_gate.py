"""tests/test_wiki_rest_mcp_parity_gate.py — WIKI-TEST-GATE (#24).

CODIFIES the standing wiki REST≡MCP byte-identical invariant (#24) as a PARAMETRIZED GATE so the
drift class that shipped in #19 (the wiki_tree ``{tree:...}`` wrapper — a self-report compared the
INNER payload + missed the wrapper; only a live byte-compare caught it) can NEVER ship silently
again. The whole wiki batch references "REST≡MCP byte-identical"; this is its executable guard.

THE INVARIANT (precise): for every wiki capability that has BOTH a REST endpoint AND an MCP tool,
the REST ``data`` equals the MCP tool PAYLOAD byte-identical (json.dumps sort_keys=True) AFTER
normalizing the DOCUMENTED per-surface conventions — NOT a naive top-level dict-equal (that naive
compare is exactly the #19 mistake: it would pass a wrapper drift on a tool whose top-level dict
happens to match). The conventions, each encoded as an explicit per-pair normalize:
  - MCP ``{found}`` existence wrapper: REST 404s on missing, MCP returns ``{found:False}``. For a
    PRESENT note we strip the MCP ``found`` flag before comparing the payload. (get_note full also
    unwraps ``{note: view}`` → bare view, matching REST.) ``sectionFound`` STAYS (it's payload, not
    the existence wrapper). NB: ``wiki_context`` is the EXCEPTION — its REST /context returns
    reader.context() verbatim, which INCLUDES ``found``, so both sides carry found → NO strip.
  - MCP result wrappers (search ``{results}``, overview ``{overview}``) that the REST ``data`` does
    NOT have → unwrap to the bare payload REST returns.
  - ``warning``: the house convention — MCP folds it inline (overview ``{overview, warning}``),
    REST puts it on the envelope (``{success, data, warning?}``). Normalize: compare the data
    payloads; assert the warning agrees across the two surfaces separately.
  - volatile ``stats.asOf`` (overview): a per-call timestamp → dropped from BOTH before compare.
  - ``wiki_tree`` MUST stay BARE (no ``{tree}`` wrapper) — the #19 regression guard.

COVERAGE-COMPLETENESS: every MCP read tool in TOOLS is either PAIRED here or in the explicit
MCP-ONLY exempt-list (with a reason). A NEW wiki tool with neither → the gate goes RED (it cannot
be silently bypassed).

THE DISTINGUISHING PLANTED-DRIFT TEST (the most important deliverable): the compare-helper is
exercised against a DELIBERATELY-DRIFTED payload (a spurious ``{tree:...}`` wrapper like the #19
bug; a dropped field) and MUST reject it (return False / the assert fails RED). A gate that can't
fail on the #19 bug is theater (memory `verify-with-the-distinguishing-case`).

TEST-ONLY sprint: this changes NO wiki source. If the gate surfaces a REAL drift in the live
surface, that's a separate bug to REPORT — not fix here.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from modules.wiki import proposals_store as pstore
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.mcp import read_server as mcp
from modules.wiki.schema import NoteCreateInput


# --------------------------------------------------------------------------- #
# Fixtures — a seeded vault both surfaces read from                              #
# --------------------------------------------------------------------------- #
@pytest.fixture
def gate_db(isolated_paths):
    """Wiki + proposal tables on the fresh isolated connection, then a seeded vault: a small linked
    cluster (so graph/backlinks/overview/clusters have real data), a note WITH a heading (so the
    get_note section mode has a section to slice), and a pending wiki proposal (so list_proposals
    has a real row). Proposals-only toggle so the proposal stays PENDING to read back."""
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    from modules.settings import service as ssvc
    from modules.settings.schema import AppConfigPatch
    ssvc.set_config(AppConfigPatch(wikiAgentAutonomous=False))

    # a linked pair + a note with a heading (## ...) for section mode
    b = wsvc.create_note(NoteCreateInput(title="Gate target", content="## Overview\ntarget body")).id
    a = wsvc.create_note(NoteCreateInput(title="Gate source", content=f"see [[{b}]]")).id
    # a pending wiki proposal so list_proposals has a row (insert a pending row directly — the canonical
    # seed used by test_wiki_proposals; avoids the auto-apply path so it stays PENDING to read back)
    pstore.insert_proposal(kind="note_create", target_id=None,
                           payload={"title": "Proposed", "content": "x"},
                           rationale="gate fixture", actor="agent",
                           correlation_id=None, created="2026-06-21T00:00:00+00:00")
    return {"paths": isolated_paths, "a": a, "b": b, "heading": "Overview"}


@pytest.fixture
def api(gate_db):
    from main import create_app
    return TestClient(create_app()), gate_db


# --------------------------------------------------------------------------- #
# The compare helper (its own unit, so the planted-drift test can exercise it)   #
# --------------------------------------------------------------------------- #
def _canonical(obj: Any) -> str:
    """The byte-identical canonical form — sort_keys so dict order can't mask a drift."""
    return json.dumps(obj, sort_keys=True)


def byte_identical(mcp_payload: Any, rest_data: Any) -> bool:
    """REST ``data`` == MCP payload, byte-for-byte (after the caller has already normalized the
    documented conventions). This is the THING the #19 bug would trip: a wrapper or dropped field
    makes the canonical strings differ → False. Deliberately a FULL compare (not top-level keys)."""
    return _canonical(mcp_payload) == _canonical(rest_data)


# --------------------------------------------------------------------------- #
# Normalizers — encode each pair's DOCUMENTED convention (MCP side → REST-data shape) #
# --------------------------------------------------------------------------- #
def _drop_asof(ov: dict[str, Any]) -> dict[str, Any]:
    """overview's stats carries a per-call ``asOf`` timestamp — drop it from a COPY (never mutate)."""
    ov = copy.deepcopy(ov)
    if isinstance(ov, dict) and isinstance(ov.get("stats"), dict):
        ov["stats"].pop("asOf", None)
    return ov


def n_identity(m: dict[str, Any]) -> Any:
    return m


def n_strip_results(m: dict[str, Any]) -> Any:
    return m["results"]


def n_overview(m: dict[str, Any]) -> Any:
    return _drop_asof(m["overview"])


def n_strip_found_unwrap_note(m: dict[str, Any]) -> Any:
    return m["note"]  # full mode: {found, note: view} → bare view (REST shape)


def n_strip_found(m: dict[str, Any]) -> Any:
    return {k: v for k, v in m.items() if k != "found"}


def n_overview_rest(d: dict[str, Any]) -> Any:
    """REST /overview data also carries the volatile asOf → drop it the same way."""
    return _drop_asof(d)


# --------------------------------------------------------------------------- #
# THE PAIRING MAP — (id, mcp_call, rest_request, mcp_normalize, rest_normalize)  #
# Resolved LIVE against modules/wiki/router.py + read_server.TOOLS (2026-06-21). #
# --------------------------------------------------------------------------- #
def _pairs(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    a, b, heading = ctx["a"], ctx["b"], ctx["heading"]
    return [
        dict(id="search", mcp=lambda: mcp.wiki_search("Gate"),
             method="GET", path="/wiki/search", params={"q": "Gate"},
             norm_mcp=n_strip_results, norm_rest=n_identity),
        dict(id="overview", mcp=lambda: mcp.wiki_overview(),
             method="GET", path="/wiki/overview", params={},
             norm_mcp=n_overview, norm_rest=n_overview_rest),
        dict(id="inbox", mcp=lambda: mcp.wiki_inbox(),
             method="GET", path="/wiki/inbox", params={},
             norm_mcp=n_identity, norm_rest=n_identity),
        dict(id="tree", mcp=lambda: mcp.wiki_tree(),
             method="GET", path="/wiki/tree", params={},
             norm_mcp=n_identity, norm_rest=n_identity),
        dict(id="clusters", mcp=lambda: mcp.wiki_clusters(),
             method="GET", path="/wiki/clusters", params={},
             norm_mcp=n_identity, norm_rest=n_identity),
        dict(id="get_note_full", mcp=lambda: mcp.wiki_get_note(b, mode="full"),
             method="GET", path=f"/wiki/notes/{b}", params={"mode": "full"},
             norm_mcp=n_strip_found_unwrap_note, norm_rest=n_identity),
        dict(id="get_note_outline", mcp=lambda: mcp.wiki_get_note(b, mode="outline"),
             method="GET", path=f"/wiki/notes/{b}", params={"mode": "outline"},
             norm_mcp=n_strip_found, norm_rest=n_identity),
        dict(id="get_note_section", mcp=lambda: mcp.wiki_get_note(b, mode="section", heading=heading),
             method="GET", path=f"/wiki/notes/{b}", params={"mode": "section", "heading": heading},
             norm_mcp=n_strip_found, norm_rest=n_identity),
        # wiki_context: REST /context returns reader.context() verbatim → INCLUDES found → no strip.
        dict(id="context", mcp=lambda: mcp.wiki_context(b),
             method="GET", path=f"/wiki/notes/{b}/context", params={"depth": 2},
             norm_mcp=n_identity, norm_rest=n_identity),
        # wiki_suggest_links (#34): both return {suggestedLinks:[...]} verbatim → identical.
        dict(id="suggest_links", mcp=lambda: mcp.wiki_suggest_links(b, limit=5),
             method="GET", path=f"/wiki/notes/{b}/suggested-links", params={"limit": 5},
             norm_mcp=n_identity, norm_rest=n_identity),
        # wiki_stale (#41): both return reader.stale_notes() verbatim (same config threshold) → identical.
        dict(id="stale", mcp=lambda: mcp.wiki_stale(),
             method="GET", path="/wiki/stale", params={},
             norm_mcp=n_identity, norm_rest=n_identity),
        dict(id="list_proposals", mcp=lambda: mcp.wiki_list_proposals(status="pending"),
             method="GET", path="/wiki/proposals", params={"status": "pending"},
             norm_mcp=n_identity, norm_rest=n_identity),
        # wiki_my_feedback (#35): both return reader.my_feedback() verbatim ({feedback,count});
        # MCP adds the `found` existence-wrapper → strip it. On this fixture no override was
        # captured → both honest-empty {feedback:[], count:0} → byte-identical after the strip.
        dict(id="my_feedback", mcp=lambda: mcp.wiki_my_feedback(),
             method="GET", path="/wiki/feedback", params={},
             norm_mcp=n_strip_found, norm_rest=n_identity),
        # POST pair (the one non-GET): citations verify — pure fn, identical both sides.
        dict(id="verify_citations", mcp=lambda: mcp.wiki_verify_citations(claims=[{"noteId": b, "span": "target"}]),
             method="POST", path="/wiki/citations/verify", json_body={"claims": [{"noteId": b, "span": "target"}]},
             norm_mcp=n_identity, norm_rest=n_identity),
        # wiki_reindex (#53): both return reader.reindex_all() verbatim. On this CLEAN fixture (no
        # orphans) it's idempotent (dropped:0), so the MCP call then the REST call return the SAME
        # aggregate → byte-identical. (A seeded-orphan case is tested in test_wiki_reconcile, not here.)
        dict(id="reindex", mcp=lambda: mcp.wiki_reindex(),
             method="POST", path="/wiki/reindex", json_body={},
             norm_mcp=n_identity, norm_rest=n_identity),
    ]


# MCP-ONLY tools — intentionally NOT paired (each with a reason). The coverage assertion below
# requires every TOOLS key to be PAIRED or here, so an exemption is a DELIBERATE, reviewed choice.
EXEMPT_MCP_ONLY: dict[str, str] = {
    "wiki_recent_ops": "no REST GET pair exists (op-log feed is MCP-only; the REST activity feed is "
                       "a different module/shape).",
    "wiki_proposal_status": "intentional LEAN agent projection — MCP returns a curated camelCase "
                            "subset {found,proposalId,kind,status,targetId,appliedNoteId,decidedBy,"
                            "decided,rationale} from proposals_STORE, while REST /proposals/{id} "
                            "returns the RAW proposals_service row. Different surfaces by design "
                            "(lean view vs raw row), NOT a drift.",
}


# --------------------------------------------------------------------------- #
# THE GATE — every paired capability is REST≡MCP byte-identical (after normalize) #
# --------------------------------------------------------------------------- #
# Parametrize over the pair IDs (each distinctly id'd — no duplicate-name shadow); the body resolves
# the live pair from the seeded ctx. We assert collected == len(pairs) separately below.
_PAIR_IDS = [p["id"] for p in _pairs({"a": 0, "b": 0, "heading": "h"})]


@pytest.mark.parametrize("pair_id", _PAIR_IDS, ids=_PAIR_IDS)
def test_rest_mcp_byte_identical(api, pair_id):
    client, ctx = api
    pair = next(p for p in _pairs(ctx) if p["id"] == pair_id)

    mcp_payload = pair["norm_mcp"](pair["mcp"]())

    if pair["method"] == "GET":
        resp = client.get(pair["path"], params=pair.get("params", {}))
    else:
        resp = client.post(pair["path"], json=pair.get("json_body", {}))
    assert resp.status_code == 200, f"{pair_id}: REST {pair['path']} → {resp.status_code}"
    rest_data = pair["norm_rest"](resp.json()["data"])

    assert byte_identical(mcp_payload, rest_data), (
        f"REST≡MCP DRIFT on '{pair_id}':\n"
        f"  MCP (normalized): {_canonical(mcp_payload)}\n"
        f"  REST data (normalized): {_canonical(rest_data)}"
    )


def test_tree_stays_bare_no_wrapper(api):
    """#19 REGRESSION GUARD (explicit, beyond the parametrized pair): wiki_tree's MCP result must be
    the BARE folder-tree dict — NOT wrapped in {tree:...}. The #19 bug was exactly this wrapper; a
    naive top-level compare missed it. Here we assert the wrapper is ABSENT on both surfaces."""
    client, ctx = api
    m = mcp.wiki_tree()
    rest = client.get("/wiki/tree").json()["data"]
    assert "tree" not in m, "MCP wiki_tree re-grew a {tree:...} wrapper (the #19 regression)"
    assert "tree" not in rest, "REST /wiki/tree data grew a {tree:...} wrapper"
    assert set(m.keys()) == set(rest.keys()), "wiki_tree top-level keys diverged between MCP and REST"


# --------------------------------------------------------------------------- #
# COVERAGE-COMPLETENESS — every MCP tool is paired OR explicitly exempt          #
# --------------------------------------------------------------------------- #
def test_every_mcp_tool_is_paired_or_exempt():
    """The gate cannot be silently bypassed: each wiki-read MCP tool is EITHER in the
    pairing map OR in EXEMPT_MCP_ONLY (with a reason). A new wiki tool added without a pair/exempt
    → this fails RED, forcing a deliberate decision (pair it or document why it's MCP-only)."""
    paired = {p["id"] for p in _pairs({"a": 0, "b": 0, "heading": "h"})}
    # map pair-ids back to tool names (get_note's 3 modes are one tool)
    paired_tools = {
        "wiki_search", "wiki_overview", "wiki_inbox", "wiki_tree", "wiki_clusters",
        "wiki_get_note", "wiki_context", "wiki_suggest_links", "wiki_stale",
        "wiki_list_proposals", "wiki_verify_citations", "wiki_reindex",
        "wiki_my_feedback",  # WIKI-WRITE-FEEDBACK #35 — paired with GET /wiki/feedback
    }
    covered = paired_tools | set(EXEMPT_MCP_ONLY)
    tools = set(mcp.TOOLS)
    missing = tools - covered
    assert not missing, (
        f"wiki MCP tool(s) {sorted(missing)} are neither PAIRED nor EXEMPT — the REST≡MCP gate has "
        f"a hole. Add a pair to _pairs() or document an exemption in EXEMPT_MCP_ONLY."
    )
    # and no stale entries (a removed tool left in our map)
    stale = covered - tools
    assert not stale, f"pairing/exempt names {sorted(stale)} no longer exist in TOOLS (stale gate)"
    # sanity: the 3 get_note modes all map to the one tool; paired_tools must be a real subset
    assert paired_tools <= tools and set(EXEMPT_MCP_ONLY) <= tools


def test_pair_ids_all_collected_no_shadow():
    """duplicate-test-name-silent-shadow guard for the PARAMETRIZE: every pair id is UNIQUE (so no
    case is silently dropped) and the parametrize list length == the live pair count."""
    ids = _PAIR_IDS
    assert len(ids) == len(set(ids)), f"duplicate pair id (a case would be silently dropped): {ids}"
    assert len(ids) == len(_pairs({"a": 0, "b": 0, "heading": "h"}))


# --------------------------------------------------------------------------- #
# THE DISTINGUISHING PLANTED-DRIFT TEST — the gate MUST fail on a #19-class bug   #
# (memory verify-with-the-distinguishing-case: a gate that can't fail is theater) #
# --------------------------------------------------------------------------- #
def test_compare_helper_REJECTS_planted_wrapper_drift():
    """THE #19 bug, planted: wrap one side in a spurious {tree:...} wrapper → byte_identical MUST
    return False. (If this passed, the gate would have shipped the #19 drift.)"""
    honest = {"name": "root", "folders": [], "notes": [1, 2]}
    drifted = {"tree": honest}  # the exact #19 wrapper shape
    assert byte_identical(honest, honest) is True, "control: identical payloads must match"
    assert byte_identical(drifted, honest) is False, \
        "PLANTED #19 wrapper drift slipped through — the gate is theater"


def test_compare_helper_REJECTS_dropped_field():
    """A dropped field (the other drift class) → byte_identical MUST return False."""
    full = {"a": 1, "b": 2, "c": 3}
    missing_c = {"a": 1, "b": 2}
    assert byte_identical(full, missing_c) is False, "a dropped field must be caught"
    # and a CHANGED value
    changed = {"a": 1, "b": 99, "c": 3}
    assert byte_identical(full, changed) is False, "a changed value must be caught"


def test_gate_fails_red_on_a_drifted_pair(api):
    """End-to-end proof the GATE (not just the helper) fails on a drift: take a real honest pair,
    inject the #19 wrapper into the MCP side, and assert the byte-identical check now FAILS — i.e.
    a wrapper regression on any pair would turn this gate RED. (xfail-style: we assert the failure.)"""
    client, ctx = api
    # honest pair: tree (currently byte-identical)
    rest_data = client.get("/wiki/tree").json()["data"]
    honest_mcp = mcp.wiki_tree()
    assert byte_identical(honest_mcp, rest_data) is True, "precondition: tree is honest today"
    # plant the #19 drift on the MCP side
    drifted_mcp = {"tree": honest_mcp}
    assert byte_identical(drifted_mcp, rest_data) is False, \
        "the gate did NOT reject a planted #19 wrapper on the tree pair — it would ship the bug"
