"""tests/test_wiki_trust_tier.py — WIKI #45: trustTier settable on create + preserved on partial update.

THE BUG (#45, ran-the-red): trustTier was NOT on NoteCreateInput → `NoteCreateInput(trustTier="candidate")`
silently DROPPED the kwarg, and _apply_create HARDCODED trustTier="verified" → every note born "verified",
a note could never be created "candidate". (The originally-reported "partial-update resets it" was a
misdiagnosis — the update path was always correct; the note was simply never candidate to begin with.)

THE FIX: NoteCreateInput gains `trustTier: TrustTier = "verified"` (default unchanged when omitted) +
`extra="forbid"` (an unknown kwarg now 422s instead of silently vanishing — the silent-drop is what hid
this); _apply_create honors inp.trustTier.

DISTINGUISHING (end-to-end, both halves of the real bug):
  - create trustTier="candidate" → the created note IS candidate (NOT the hardcoded "verified") — the create fix.
  - then a content-ONLY update → trustTier STAYS candidate — the update path was already correct (regression pin).
A divergent value (candidate, not the "verified" default) is required so a correct impl ≠ the old hardcoded one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


# --------------------------------------------------------------------------- #
# CREATE honors trustTier (the real #45 bug)                                     #
# --------------------------------------------------------------------------- #
def test_create_honors_candidate_trust_tier(wiki_db):
    """THE create fix: a note created trustTier="candidate" IS candidate — NOT the old hardcoded
    "verified". (Divergent value: candidate ≠ the default, so this fails against the old hardcode.)"""
    n = wsvc.create_note(NoteCreateInput(title="Unverified claim", trustTier="candidate"))
    assert n.trustTier == "candidate", "create must honor the input trustTier (was hardcoded 'verified')"


def test_create_defaults_verified_when_omitted(wiki_db):
    """Omitting trustTier → default "verified" (existing behavior preserved — no silent change)."""
    n = wsvc.create_note(NoteCreateInput(title="Plain note"))
    assert n.trustTier == "verified"


def test_create_field_is_present_on_the_model(wiki_db):
    """Regression for the root cause: NoteCreateInput actually HAS a trustTier field (it was missing,
    which is why the kwarg silently dropped). hasattr proves the field exists now."""
    inp = NoteCreateInput(title="X", trustTier="candidate")
    assert hasattr(inp, "trustTier") and inp.trustTier == "candidate"


# --------------------------------------------------------------------------- #
# THE end-to-end distinguishing: create candidate → content update → STAYS candidate #
# --------------------------------------------------------------------------- #
def test_candidate_survives_content_only_update(wiki_db):
    """The full #45 scenario end-to-end: born candidate (create fix) THEN a content-only update
    (no trustTier in the input) → STAYS candidate (the update path's None-means-skip, already
    correct). This is the exact bug as originally reported — now green via the create fix."""
    n = wsvc.create_note(NoteCreateInput(title="Claim", trustTier="candidate"))
    assert n.trustTier == "candidate"
    u = wsvc.update_note(n.id, NoteUpdateInput(content="a longer body, no trustTier in this update"))
    assert u.trustTier == "candidate", "a content-only update must NOT reset trustTier to default"


def test_update_can_change_trust_tier(wiki_db):
    """The update CAN change it when explicitly provided (candidate → verified)."""
    n = wsvc.create_note(NoteCreateInput(title="Claim", trustTier="candidate"))
    u = wsvc.update_note(n.id, NoteUpdateInput(trustTier="verified"))
    assert u.trustTier == "verified"


def test_update_none_preserves_each_field(wiki_db):
    """Regression pin for the update path (it was correct; keep it correct): a content-only update
    preserves status, noteType, tags AND trustTier — none reset to default. (The CLASS check —
    the dispatch feared status/noteType/tags too; this pins they all survive a partial update.)"""
    n = wsvc.create_note(NoteCreateInput(
        title="Rich", trustTier="candidate", status="evergreen", noteType="moc", tags=["x", "y"]))
    u = wsvc.update_note(n.id, NoteUpdateInput(content="new body only"))
    assert u.trustTier == "candidate" and u.status == "evergreen"
    assert u.noteType == "moc" and u.tags == ["x", "y"]


# --------------------------------------------------------------------------- #
# CLASS check — create honors EVERY NoteCreateInput field (no other silent drop)  #
# --------------------------------------------------------------------------- #
def test_create_honors_all_fields_no_silent_drop(wiki_db):
    """The #45 class: _apply_create must honor EVERY NoteCreateInput field, not hardcode/drop any.
    Set every settable field to a non-default value + assert the created note carries them all."""
    n = wsvc.create_note(NoteCreateInput(
        title="Everything", content="body", status="evergreen", noteType="moc",
        trustTier="candidate", tags=["a"], author="agent:test", folder="Area"))
    assert n.title == "Everything" and n.content == "body"
    assert n.status == "evergreen" and n.noteType == "moc" and n.trustTier == "candidate"
    assert n.tags == ["a"] and n.author == "agent:test" and n.folder == "Area"


# --------------------------------------------------------------------------- #
# extra="forbid" — an unknown field now 422s (was a silent drop, which hid #45)   #
# --------------------------------------------------------------------------- #
def test_unknown_field_is_rejected_not_dropped(wiki_db):
    """The honest-mirror fix: an unknown kwarg → ValidationError (422 at the API), NOT a silent
    drop. (A silently-dropped field is exactly what hid the missing trustTier.)"""
    with pytest.raises(ValidationError):
        NoteCreateInput(title="X", nonsenseField="whatever")  # type: ignore[call-arg]


# --------------------------------------------------------------------------- #
# REST round-trip — the create endpoint honors trustTier end-to-end             #
# --------------------------------------------------------------------------- #
def test_rest_create_honors_trust_tier(wiki_db):
    from fastapi.testclient import TestClient
    from main import create_app
    api = TestClient(create_app())
    r = api.post("/wiki/notes", json={"title": "Via REST", "trustTier": "candidate"})
    assert r.status_code == 200
    nid = r.json()["data"]["id"]
    assert r.json()["data"]["trustTier"] == "candidate"
    # a content-only PUT preserves it
    r2 = api.put(f"/wiki/notes/{nid}", json={"content": "edited"})
    assert r2.status_code == 200 and r2.json()["data"]["trustTier"] == "candidate"
