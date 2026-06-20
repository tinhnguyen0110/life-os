"""tests/test_journal_nudge.py — JOURNAL-NUDGE (#14, SPEC §172): a buy-ladder rung newly
entered → a pending nudge to LOG a decision. Triggered inside market-poll (fail-soft add-on),
surfaced in life_brief.decisions, NEVER fabricates a journal/decision entry.

The HARD GATE (distinguishing — both directions):
- rung newly entered (rungsIn↑) → pending nudge recorded + in life_brief.pendingNudges + a
  'journal-nudge' run_log row (activity attribution).
- same rung (rungsIn unchanged) → NO duplicate.
- exit + re-enter (rungsIn drops then rises past) → RE-fires (episode, not once-ever).
- mock / no-ladder → NO nudge (real-data-only — ladder_states omits no-ladder channels).
- NEVER writes a journal/decision entry (only a pending nudge row).
- NEUTRAL: no buy/sell/should verb in the nudge text.
- 0 decisions → life_brief.decisions flags the empty state (the note).
- market-poll primary work UNAFFECTED by a nudge add-on failure (fail-soft, status-before-addon).
"""

from __future__ import annotations

import json

import pytest

from store import db


@pytest.fixture
def nudge_db(isolated_paths):
    """A fresh isolated DB with the schema (journal_nudges + nudge_rung_state)."""
    db.init_db()
    return isolated_paths


def _ladder(rungs_in: int, *, current: float = 100.0, next_pct: float = -20.0,
            next_trigger: float = 80.0) -> dict:
    """A LadderState-shaped dict for one channel (what fin.ladder_states returns)."""
    return {"channel": "crypto", "referencePrice": 100.0, "currentPrice": current,
            "rungsIn": rungs_in, "nextRung": {"pct": next_pct, "triggerPrice": next_trigger},
            "distancePct": 5.0}


def _patch_ladder(monkeypatch, states: dict):
    """Patch finance.ladder_states (the source check_rung_nudges reads) to a controlled value."""
    import modules.finance.service as fin
    monkeypatch.setattr(fin, "ladder_states", lambda: states)


# --------------------------------------------------------------------------- #
# GATE — fire on a NEW rung; no-dup on unchanged; re-fire on re-entry (episode)  #
# --------------------------------------------------------------------------- #
def test_NUDGE_fires_on_new_rung(nudge_db, monkeypatch):
    from modules.market import service as mkt
    _patch_ladder(monkeypatch, {"crypto": _ladder(1)})
    r = mkt.check_rung_nudges()
    assert r["fired"] == 1, "a newly-entered rung must fire one nudge"
    pend = db.pending_journal_nudges()
    assert len(pend) == 1 and pend[0]["channel"] == "crypto" and pend[0]["status"] == "pending"
    # the high-water mark is bumped to the live rungsIn
    assert db.get_nudge_rung_state("crypto") == 1


def test_NUDGE_no_duplicate_on_unchanged_rung(nudge_db, monkeypatch):
    from modules.market import service as mkt
    _patch_ladder(monkeypatch, {"crypto": _ladder(1)})
    assert mkt.check_rung_nudges()["fired"] == 1   # first entry fires
    # SAME rungsIn again → no new nudge (already nudged this episode)
    assert mkt.check_rung_nudges()["fired"] == 0, "unchanged rungsIn must NOT re-fire"
    assert len(db.pending_journal_nudges()) == 1, "no duplicate nudge row"


def test_NUDGE_refires_on_exit_then_reentry_episode(nudge_db, monkeypatch):
    """THE DISTINGUISHING vs once-ever: rungsIn rises → fire; drops (exit) → no fire + lower the
    mark; rises past it again → a NEW episode RE-fires. A naive once-per-rung table would NOT."""
    import modules.finance.service as fin
    from modules.market import service as mkt
    state = {"r": 0}
    monkeypatch.setattr(fin, "ladder_states", lambda: {"crypto": _ladder(state["r"])})

    state["r"] = 1
    assert mkt.check_rung_nudges()["fired"] == 1            # enter → fire
    state["r"] = 0
    assert mkt.check_rung_nudges()["fired"] == 0            # exit → no fire (mark lowered)
    assert db.get_nudge_rung_state("crypto") == 0
    state["r"] = 1
    assert mkt.check_rung_nudges()["fired"] == 1, "a genuine re-entry must RE-fire (new episode)"
    assert len(db.pending_journal_nudges()) == 2, "two episodes → two nudges"


def test_NUDGE_deeper_rung_fires_again(nudge_db, monkeypatch):
    """Entering a DEEPER rung (rungsIn 1 → 2) is a new rung → fires again."""
    import modules.finance.service as fin
    from modules.market import service as mkt
    state = {"r": 1}
    monkeypatch.setattr(fin, "ladder_states", lambda: {"crypto": _ladder(state["r"])})
    assert mkt.check_rung_nudges()["fired"] == 1   # rung 1
    state["r"] = 2
    assert mkt.check_rung_nudges()["fired"] == 1, "a deeper rung (1→2) is new → fires"
    assert db.get_nudge_rung_state("crypto") == 2


# --------------------------------------------------------------------------- #
# GATE — real-data-only: no ladder (mock / unconfigured) → NO nudge              #
# --------------------------------------------------------------------------- #
def test_NUDGE_no_ladder_no_fire(nudge_db, monkeypatch):
    """A channel with NO ladder state (no config / no price / mock) is absent from
    ladder_states() → no nudge fires (real-data-only, like guardian)."""
    from modules.market import service as mkt
    _patch_ladder(monkeypatch, {})   # ladder_states returns nothing
    r = mkt.check_rung_nudges()
    assert r["fired"] == 0 and r["channels"] == []
    assert db.pending_journal_nudges() == []


def test_NUDGE_ladder_states_failure_is_soft(nudge_db, monkeypatch):
    """If ladder_states() raises, check_rung_nudges returns a no-fire result, never propagates."""
    import modules.finance.service as fin
    from modules.market import service as mkt
    monkeypatch.setattr(fin, "ladder_states", lambda: (_ for _ in ()).throw(RuntimeError("finance down")))
    r = mkt.check_rung_nudges()   # must not raise
    assert r["fired"] == 0


# --------------------------------------------------------------------------- #
# GATE — NEVER fabricates a journal/decision entry (only a pending nudge)        #
# --------------------------------------------------------------------------- #
def test_NUDGE_never_writes_journal_or_decision_entry(nudge_db, monkeypatch):
    """Firing a nudge records ONLY a journal_nudges row — it must NOT create a decision_journal
    or trade-journal entry (the user logs those). Assert the decision_journal stays empty."""
    from modules.market import service as mkt
    from modules.decision_journal import service as dj
    _patch_ladder(monkeypatch, {"crypto": _ladder(1)})
    mkt.check_rung_nudges()
    assert len(db.pending_journal_nudges()) == 1          # the nudge IS recorded
    stats, _ = dj.list_entries()                          # but NO decision entry was fabricated
    assert len(stats.entries) == 0, "a nudge must NEVER create a decision entry — the user logs it"


# --------------------------------------------------------------------------- #
# GATE — NEUTRAL: the nudge text is a QUESTION, no advice verb                   #
# --------------------------------------------------------------------------- #
_ADVICE_VERBS = ("should", "buy", "sell", "rebalance", "deploy", "recommend", "must ", "ought")


def test_NUDGE_text_is_neutral_no_advice_verb(nudge_db, monkeypatch):
    from modules.market import service as mkt
    _patch_ladder(monkeypatch, {"crypto": _ladder(1)})
    r = mkt.check_rung_nudges()
    msg = r["nudges"][0]["msg"].lower()
    for verb in _ADVICE_VERBS:
        assert verb not in msg, f"nudge text leaked an advice verb {verb!r}: {msg!r}"
    assert "log your decision" in msg, "the nudge must prompt LOGGING (a question), not advise"


# --------------------------------------------------------------------------- #
# GATE — fail-SOFT add-on: a nudge failure does NOT fail the market poll         #
# --------------------------------------------------------------------------- #
def test_NUDGE_addon_failure_does_not_fail_poll(nudge_db, monkeypatch):
    """The poll's PRIMARY status is set BEFORE the nudge add-on; a nudge that raises is caught →
    the poll status is unaffected (warn-only-if-poll-warned), detail notes 'journal-nudge ERR'."""
    from modules.market import router as mkt_router
    from modules.market import service as mkt
    # primary poll succeeds (no warnings)
    monkeypatch.setattr(mkt, "poll_once", lambda: {"persisted": 3, "fired": 0, "warnings": []})
    # the nudge add-on raises
    monkeypatch.setattr(mkt, "check_rung_nudges", lambda: (_ for _ in ()).throw(RuntimeError("nudge boom")))
    status, detail = mkt_router._market_poll_work()
    assert status == "ok", "a nudge add-on failure must NOT downgrade a successful poll"
    assert "journal-nudge ERR" in detail, "the soft failure is noted, not raised"


def test_NUDGE_poll_records_nudge_run_and_detail(nudge_db, monkeypatch):
    """When nudges fire, _market_poll_work records a 'journal-nudge' run_log row (activity
    attribution) + appends a detail note — without changing the poll's primary status."""
    from modules.market import router as mkt_router
    from modules.market import service as mkt
    monkeypatch.setattr(mkt, "poll_once", lambda: {"persisted": 3, "fired": 0, "warnings": []})
    monkeypatch.setattr(mkt, "check_rung_nudges",
                        lambda: {"fired": 1, "channels": ["crypto"],
                                 "nudges": [{"channel": "crypto", "msg": "log your decision?"}]})
    status, detail = mkt_router._market_poll_work()
    assert status == "ok"
    assert "journal-nudge: 1 rung(s) entered" in detail
    # the run_log has a journal-nudge row attributed to its routine_id
    runs = db.recent_runs(mkt.JOURNAL_NUDGE_ID, limit=5)
    assert len(runs) == 1 and runs[0]["routine_id"] == "journal-nudge"
    payload = json.loads(runs[0]["detail"])
    assert payload["kind"] == "nudge" and payload["fired"] == 1


# --------------------------------------------------------------------------- #
# GATE — life_brief surfaces pendingNudges + the 0-logged note (the loop-closer) #
# --------------------------------------------------------------------------- #
def test_NUDGE_life_brief_decisions_surfaces_nudge_and_empty_note(nudge_db, monkeypatch):
    """life_brief.decisions: 0 decisions logged → a `note`; and `pendingNudges` lists the open
    rung nudge. So an MCP agent sees rung-hit + pending nudge + 0-logged and prompts the user."""
    import mcp_servers.read_server as rs
    # record a pending nudge (as the engine would)
    db.record_journal_nudge("crypto", -20.0, 80.0, 79.0, "2026-06-21T00:00:00+00:00")

    section = rs._brief_decisions()
    # the empty-state note (0 decisions logged)
    assert section.get("totalLogged") == 0
    assert section.get("note") and "0 decisions logged" in section["note"]
    # the pending nudge is surfaced (honest, never fabricated)
    nudges = section.get("pendingNudges")
    assert isinstance(nudges, list) and len(nudges) == 1
    assert nudges[0]["channel"] == "crypto" and nudges[0]["status"] == "pending"


def test_NUDGE_life_brief_pending_empty_when_none(nudge_db):
    """Honest-empty: no nudges → pendingNudges == [] (never fabricated)."""
    import mcp_servers.read_server as rs
    section = rs._brief_decisions()
    assert section.get("pendingNudges") == []


# --------------------------------------------------------------------------- #
# Part 3 — routine attribution: macro-poll + news-capture are now in the catalog #
# --------------------------------------------------------------------------- #
def test_NUDGE_part3_routine_attribution_catalog():
    """The run_log routine_ids that existed but weren't in the catalog (macro-poll, news-capture)
    are now registered → the activity feed attributes them with a friendly name, not the raw id.
    journal-nudge is already catalogued (so its nudge runs attribute too)."""
    from modules.automation.service import _CATALOG_BY_ID
    for rid in ("macro-poll", "news-capture", "journal-nudge"):
        assert rid in _CATALOG_BY_ID, f"{rid} must be in the routine catalog for attribution"
        assert _CATALOG_BY_ID[rid]["name"], f"{rid} must have a friendly name"
