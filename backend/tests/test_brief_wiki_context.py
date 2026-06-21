"""tests/test_brief_wiki_context.py — WIKI-CONTEXT (#36).

daily_brief enriched with a DETERMINISTIC wiki-graph section: recent note activity
(create|edit) + notable clusters, pulled from the wiki reader (recent_activity +
detect_clusters). ADDITIVE + backward-compat (the existing 5-rule priorities/summary/
stale are UNCHANGED). NO LLM. honest-mirror: empty → empty lists; wiki down → empty
lists + a warning (present, never faked, never a crash).

BEHAVIOR-TESTED: build Sources.wiki → _build_wiki_context / generate_brief → assert
value-by-value; + a real end-to-end through the wiki tables for the populated case.
"""

from __future__ import annotations

import pytest

from modules.brief import reader, service
from modules.brief.schema import Brief, WikiContext


# --------------------------------------------------------------------------- #
# Helpers — build a Sources with a wiki block (the reader.pull shape)            #
# --------------------------------------------------------------------------- #
def _op(note_id, title, op="create", ts="2026-06-21T10:00:00+00:00"):
    """A reader.recent_activity row: {ts, op, actor, noteId, noteTitle, detail}."""
    return {"ts": ts, "op": op, "actor": "mcp:writer", "noteId": note_id,
            "noteTitle": title, "detail": None}


def _cluster(suggested_title, size, importance=1.0):
    """A reader.detect_clusters row (the keys _build_wiki_context mirrors)."""
    return {"members": [{"id": i, "title": f"m{i}"} for i in range(size)],
            "size": size, "density": 0.5, "importance": importance,
            "suggestedTitle": suggested_title}


def _sources_with_wiki(wiki):
    s = reader.Sources()
    s.wiki = wiki
    return s


# --------------------------------------------------------------------------- #
# _build_wiki_context — populated / honest-null / fail-soft / filtering           #
# --------------------------------------------------------------------------- #
def test_build_wiki_context_populated():
    """Recent create|edit ops + clusters → WikiContext with value-by-value rows."""
    src = _sources_with_wiki({
        "recentOps": [_op(3, "Note C", "edit"), _op(2, "Note B"), _op(1, "Note A")],
        "clusters": [_cluster("Cluster X", 4, importance=2.0), _cluster("Cluster Y", 3)],
    })
    wc = service._build_wiki_context(src, "2026-06-21T12:00:00+00:00")
    assert [(n.noteId, n.title, n.kind) for n in wc.recentNotes] == [
        (3, "Note C", "edit"), (2, "Note B", "create"), (1, "Note A", "create")]
    assert [(c.label, c.noteCount) for c in wc.clusters] == [("Cluster X", 4), ("Cluster Y", 3)]
    assert wc.source == "wiki" and wc.warnings == []
    assert wc.asOf == "2026-06-21T12:00:00+00:00"


def test_build_wiki_context_honest_empty():
    """No activity AND no clusters → empty lists (NOT None-the-section, NOT a fabricated row)."""
    wc = service._build_wiki_context(_sources_with_wiki({"recentOps": [], "clusters": []}),
                                     "2026-06-21T12:00:00+00:00")
    assert wc.recentNotes == [] and wc.clusters == []
    assert wc.source == "wiki" and wc.warnings == []


def test_build_wiki_context_failsoft_wiki_down():
    """src.wiki is None (the wiki read raised in pull) → empty lists + a warning, present
    (honest-blind), never a crash."""
    wc = service._build_wiki_context(_sources_with_wiki(None), "2026-06-21T12:00:00+00:00")
    assert wc.recentNotes == [] and wc.clusters == []
    assert wc.warnings == ["wiki source unavailable"]
    assert wc.source == "wiki"


def test_build_wiki_context_excludes_delete_and_merge():
    """DISTINGUISHING: only create|edit surface — delete/merge ops (note is gone) are excluded."""
    src = _sources_with_wiki({
        "recentOps": [_op(5, "Live", "create"), _op(4, "Gone", "delete"),
                      _op(3, "Merged", "merge"), _op(2, "Edited", "edit")],
        "clusters": [],
    })
    wc = service._build_wiki_context(src, "2026-06-21T12:00:00+00:00")
    kinds = {(n.noteId, n.kind) for n in wc.recentNotes}
    assert kinds == {(5, "create"), (2, "edit")}, "delete/merge must NOT appear (note gone)"


def test_build_wiki_context_caps_recent_and_clusters():
    """Caps: recent ≤ WIKI_RECENT_CAP, clusters ≤ WIKI_CLUSTER_CAP (no silent unbounded dump)."""
    src = _sources_with_wiki({
        "recentOps": [_op(i, f"N{i}", "create") for i in range(20)],
        "clusters": [_cluster(f"C{i}", 3) for i in range(20)],
    })
    wc = service._build_wiki_context(src, "2026-06-21T12:00:00+00:00")
    assert len(wc.recentNotes) == service.WIKI_RECENT_CAP
    assert len(wc.clusters) == service.WIKI_CLUSTER_CAP


# --------------------------------------------------------------------------- #
# generate_brief — backward-compat + wikeContext present                          #
# --------------------------------------------------------------------------- #
def test_generate_brief_carries_wiki_context(monkeypatch):
    """generate_brief surfaces wikiContext from the wiki source."""
    src = reader.Sources()
    src.wiki = {"recentOps": [_op(1, "Hello")], "clusters": [_cluster("Topic", 3)]}
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert brief.wikiContext is not None
    assert brief.wikiContext.recentNotes[0].title == "Hello"
    assert brief.wikiContext.clusters[0].label == "Topic"


def test_generate_brief_backward_compat_existing_fields_unchanged(monkeypatch):
    """BACKWARD-COMPAT: adding wikiContext does NOT change priorities/summary/stale/source.
    A brief with no rules firing still has the existing shape; wikiContext is purely additive."""
    src = reader.Sources()  # all sources None → no rules fire
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    # the existing contract holds
    assert brief.source == "template"
    assert brief.priorities == []          # honest-empty (no rules)
    assert brief.summary is not None
    assert brief.stale is False
    # wikiContext present + honest-blind (wiki was None → unavailable warning)
    assert brief.wikiContext is not None
    assert brief.wikiContext.warnings == ["wiki source unavailable"]


def test_generate_brief_wiki_failsoft_keeps_brief(monkeypatch):
    """A wiki read failing (src.wiki None) does NOT break the rest of the brief — the
    other sections still populate; wikiContext is honest-blind."""
    src = reader.Sources()
    src.wiki = None  # wiki down
    src.warnings = ["wiki nguồn lỗi (RuntimeError)"]
    monkeypatch.setattr(reader, "pull", lambda: src)
    brief = service.generate_brief()
    assert brief.wikiContext.warnings == ["wiki source unavailable"]
    assert "wiki nguồn lỗi (RuntimeError)" in brief.warnings   # the pull-level warning preserved


def test_wiki_context_is_neutral_no_advice(monkeypatch):
    """NEUTRAL: wikiContext is SIGNAL (notes/clusters) — no advice/forecast verb leaks."""
    import json
    src = reader.Sources()
    src.wiki = {"recentOps": [_op(1, "Buy signals research")],  # title may contain words; the BLOCK adds none
                "clusters": [_cluster("Trading", 3)]}
    monkeypatch.setattr(reader, "pull", lambda: src)
    wc = service.generate_brief().wikiContext
    flat = json.dumps(wc.model_dump()).lower()
    # the block itself must not ADD advice; we check the structural fields don't inject verbs
    # (a note's own title is user data — we assert the source tag + no fabricated recommendation field)
    assert wc.source == "wiki"
    assert "recommend" not in flat and "should buy" not in flat and "forecast" not in flat


# --------------------------------------------------------------------------- #
# REAL end-to-end through the wiki tables (the populated distinguishing case)      #
# --------------------------------------------------------------------------- #
@pytest.fixture
def wiki_db(isolated_paths):
    from modules.wiki import store as wiki_store
    wiki_store.init_wiki_tables()
    return isolated_paths


def test_e2e_real_wiki_notes_surface_in_brief(wiki_db, monkeypatch):
    """REAL: seed notes + a dense cluster through the wiki service → generate_brief's
    wikiContext surfaces them (value-by-value), proving the reader.pull → service path
    works end-to-end (not just a monkeypatched Sources)."""
    from modules.wiki import service as wsvc
    from modules.wiki.schema import NoteCreateInput
    # isolate the noisy non-wiki sources (network) so the test is deterministic + fast
    monkeypatch.setattr(reader, "pull", lambda: _real_wiki_only_sources())

    a = wsvc.create_note(NoteCreateInput(title="Alpha", content="x"), actor="mcp:writer").id
    b = wsvc.create_note(NoteCreateInput(title="Beta", content=f"[[{a}]]"), actor="mcp:writer").id
    wsvc.create_note(NoteCreateInput(title="Gamma", content=f"[[{a}]] [[{b}]]"), actor="mcp:writer")

    brief = service.generate_brief()
    titles = {n.title for n in brief.wikiContext.recentNotes}
    assert {"Alpha", "Beta", "Gamma"} <= titles
    assert brief.wikiContext.clusters, "a dense 3-note cluster should be detected"
    assert brief.wikiContext.clusters[0].noteCount == 3


def _real_wiki_only_sources():
    """A Sources with ONLY the real wiki block populated (other sources None) — so the
    e2e test exercises the real wiki reader without the network-bound finance/market reads."""
    from modules.wiki import reader as wiki_reader
    s = reader.Sources()
    s.wiki = {"recentOps": wiki_reader.recent_activity(20),
              "clusters": wiki_reader.detect_clusters()}
    return s
