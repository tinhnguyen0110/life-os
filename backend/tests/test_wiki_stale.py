"""tests/test_wiki_stale.py — WIKI-STALE-DETECTOR (#41, SPEC A6).

The read-only staleness + contradiction-candidate detector. The DISTINGUISHING cases use an
injectable ``now`` (the detector takes ``now=`` for testable days-since) so a freshly-created note
can be made "stale" by passing a far-future now — no flaky real-clock waiting, no backdating hacks.

The 4 staleness axes (each must independently gate — verify-with-the-distinguishing-case):
  age (updated > N days), recency (recent → NOT), status (only evergreen), inbound (≥1 link).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from modules.wiki import reader as wiki_reader
from modules.wiki import service as wsvc
from modules.wiki import store as wiki_store
from modules.wiki.schema import NoteCreateInput, NoteUpdateInput


@pytest.fixture
def wiki_db(isolated_paths):
    wiki_store.init_wiki_tables()
    return isolated_paths


def _far_future(days: int = 1000) -> datetime:
    """A now() far enough ahead that any just-created note is > threshold old."""
    return datetime.now(timezone.utc) + timedelta(days=days)


def _evergreen_with_inbound() -> int:
    """Create an evergreen target + a source that links it (→ target has 1 inbound). Returns target id."""
    target = wsvc.create_note(NoteCreateInput(title="Load-bearing note", status="evergreen")).id
    wsvc.create_note(NoteCreateInput(title="Source", content=f"see [[{target}]]"))
    return target


# --------------------------------------------------------------------------- #
# STALE — the 4 distinguishing axes                                             #
# --------------------------------------------------------------------------- #
def test_stale_flags_evergreen_old_with_inbound(wiki_db):
    """The positive case: evergreen + > threshold old + ≥1 inbound → flagged."""
    tid = _evergreen_with_inbound()
    res = wiki_reader.stale_notes(threshold_days=90, now=_far_future())
    ids = [s["id"] for s in res["stale"]]
    assert tid in ids
    row = next(s for s in res["stale"] if s["id"] == tid)
    assert row["status"] == "evergreen" and row["inboundCount"] >= 1 and row["daysSince"] > 90
    assert res["staleCount"] == len(res["stale"])


def test_stale_NOT_flagged_when_recent(wiki_db):
    """RECENCY axis: same evergreen-with-inbound note, but now=just-now → daysSince ~0 → NOT stale."""
    _evergreen_with_inbound()
    res = wiki_reader.stale_notes(threshold_days=90, now=datetime.now(timezone.utc))
    assert res["stale"] == [] and res["staleCount"] == 0


def test_stale_NOT_flagged_for_fleeting(wiki_db):
    """STATUS axis: a fleeting note (default) old + with inbound → NOT flagged (only evergreen)."""
    target = wsvc.create_note(NoteCreateInput(title="Fleeting target")).id  # status defaults fleeting
    wsvc.create_note(NoteCreateInput(title="Src", content=f"see [[{target}]]"))
    res = wiki_reader.stale_notes(threshold_days=90, now=_far_future())
    assert target not in [s["id"] for s in res["stale"]]


def test_stale_NOT_flagged_for_developing(wiki_db):
    """STATUS axis: a developing (in-progress) note old + with inbound → NOT flagged."""
    target = wsvc.create_note(NoteCreateInput(title="WIP", status="developing")).id
    wsvc.create_note(NoteCreateInput(title="Src2", content=f"see [[{target}]]"))
    res = wiki_reader.stale_notes(threshold_days=90, now=_far_future())
    assert target not in [s["id"] for s in res["stale"]]


def test_stale_NOT_flagged_for_orphan_evergreen(wiki_db):
    """INBOUND axis: an evergreen note old but with ZERO inbound → NOT flagged (it's an orphan,
    overview.orphans' concern, not stale-important)."""
    target = wsvc.create_note(NoteCreateInput(title="Orphan evergreen", status="evergreen")).id
    res = wiki_reader.stale_notes(threshold_days=90, now=_far_future())
    assert target not in [s["id"] for s in res["stale"]]


def test_stale_threshold_is_respected(wiki_db):
    """AGE axis: the same note is stale at threshold 90 (now=+1000d) but NOT at threshold 2000."""
    tid = _evergreen_with_inbound()
    now = _far_future(1000)
    assert tid in [s["id"] for s in wiki_reader.stale_notes(threshold_days=90, now=now)["stale"]]
    assert tid not in [s["id"] for s in wiki_reader.stale_notes(threshold_days=2000, now=now)["stale"]]


def test_stale_sorted_stalest_first(wiki_db):
    """daysSince DESC — the stalest note is first."""
    old = _evergreen_with_inbound()
    res = wiki_reader.stale_notes(threshold_days=1, now=_far_future(500))
    days = [s["daysSince"] for s in res["stale"]]
    assert days == sorted(days, reverse=True)
    assert old in [s["id"] for s in res["stale"]]


def test_stale_honest_empty(wiki_db):
    """Empty vault → empty lists + 0 counts (honest, not omitted)."""
    res = wiki_reader.stale_notes(threshold_days=90, now=_far_future())
    assert res["stale"] == [] and res["staleCount"] == 0
    assert res["contradictionCandidates"] == [] and res["candidateCount"] == 0
    assert res["thresholdDays"] == 90


def test_stale_malformed_updated_not_flagged(wiki_db):
    """A note whose updated is unparseable → daysSince None → NOT flagged (honest, never crash).
    Even WITH a real inbound link (so the timestamp is the ONLY gate that excludes it)."""
    # an evergreen note with a garbage updated timestamp, crafted directly in the cache
    wiki_store.upsert_note_cache(
        note_id=999, title="Garbage ts note", aliases_json="[]", status="evergreen",
        note_type="concept", trust_tier="verified", author="human", tags_json="[]",
        content_hash="", created="2020-01-01T00:00:00+00:00", updated="not-a-timestamp",
        capture_source="quick_add", folder="",
    )
    # a real source note that links 999 → 999 now has a resolved inbound (only the bad ts gates it)
    wsvc.create_note(NoteCreateInput(title="Linker to garbage", content="see [[999]]"))
    res = wiki_reader.stale_notes(threshold_days=90, now=_far_future())
    assert 999 not in [s["id"] for s in res["stale"]]  # unparseable ts → not flagged, no crash


# --------------------------------------------------------------------------- #
# CONTRADICTION-CANDIDATE v1 — mutually-linked + divergent trust tier           #
# --------------------------------------------------------------------------- #
def test_contradiction_candidate_verified_vs_candidate_mutual(wiki_db):
    """A verified note + a candidate note that LINK EACH OTHER → flagged as a candidate.
    NB: a NoteUpdateInput with only ``content`` set resets trustTier to the default → pass
    trustTier on EVERY update so the tiers stick (the detector reads the cached trust_tier)."""
    a = wsvc.create_note(NoteCreateInput(title="Trusted", trustTier="verified")).id
    b = wsvc.create_note(NoteCreateInput(title="Unverified", trustTier="candidate")).id
    # make them mutually link, RE-asserting each tier so the content-edit doesn't reset it
    wsvc.update_note(a, NoteUpdateInput(content=f"links [[{b}]]", trustTier="verified"))
    wsvc.update_note(b, NoteUpdateInput(content=f"links [[{a}]]", trustTier="candidate"))
    res = wiki_reader.stale_notes(now=_far_future())
    pairs = [tuple(sorted(c["pair"])) for c in res["contradictionCandidates"]]
    assert tuple(sorted((a, b))) in pairs


def test_contradiction_NOT_when_same_tier(wiki_db):
    """Two verified notes mutually linked → NOT a candidate (same tier, no divergence)."""
    a = wsvc.create_note(NoteCreateInput(title="V1", trustTier="verified")).id
    b = wsvc.create_note(NoteCreateInput(title="V2", trustTier="verified")).id
    wsvc.update_note(a, NoteUpdateInput(content=f"[[{b}]]"))
    wsvc.update_note(b, NoteUpdateInput(content=f"[[{a}]]"))
    res = wiki_reader.stale_notes(now=_far_future())
    pairs = [tuple(sorted(c["pair"])) for c in res["contradictionCandidates"]]
    assert tuple(sorted((a, b))) not in pairs


def test_contradiction_NOT_when_one_way_link(wiki_db):
    """A verified→candidate ONE-WAY link (not mutual) → NOT a candidate (v1 needs mutual)."""
    a = wsvc.create_note(NoteCreateInput(title="OneWayV", trustTier="verified")).id
    b = wsvc.create_note(NoteCreateInput(title="OneWayC", trustTier="candidate")).id
    wsvc.update_note(a, NoteUpdateInput(content=f"[[{b}]]"))  # a→b only
    res = wiki_reader.stale_notes(now=_far_future())
    pairs = [tuple(sorted(c["pair"])) for c in res["contradictionCandidates"]]
    assert tuple(sorted((a, b))) not in pairs
