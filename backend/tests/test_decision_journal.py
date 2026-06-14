"""tests/test_decision_journal.py — Decision Journal + Calibration (Sprint W7 A2).

THE 3 TEETH (architect/team-lead locked):
  1. Brier exact value 0.325 on the locked fixture (conf90-right + conf80-wrong).
  2. Two-axis (verify-with-the-distinguishing-case): a high-confidence-WRONG band
     scores actual=0.0, NOT ~95 — a confidence-only collapse would report ~95 and
     FAIL this. The two axes (confidence vs outcome) must NOT collapse.
  3. Bias min-n gate: a 3-all-wrong domain is NOT flagged (n<4); a 4-entry >60%-wrong
     domain IS flagged.

Tests in their own module (test-where-the-reader-greps). compute_stats is pure.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.decision_journal import service as dj
from modules.decision_journal.schema import DecisionEntry, DecisionInput, DecisionUpdate


def _entry(confidence, outcome, *, domain="general", predicted=None,
           status="resolved", decision="d") -> DecisionEntry:
    return DecisionEntry(
        id=f"x-{confidence}-{outcome}-{domain}", decision=decision, thesis=None,
        falsificationCondition=None, confidence=confidence, predicted=predicted,
        date="2026-06-14", domain=domain, status=status, outcome=outcome,
        lesson=None, createdAt="2026-06-14T00:00:00Z", updatedAt="2026-06-14T00:00:00Z",
    )


# --------------------------------------------------------------------------- #
# TEETH 1 — Brier exact value                                                   #
# --------------------------------------------------------------------------- #
def test_brier_exact_locked_fixture():
    # conf 90 right (p=0.9, o=1) + conf 80 wrong (p=0.8, o=0), predicted=None.
    # ((0.9-1)^2 + (0.8-0)^2)/2 = (0.01 + 0.64)/2 = 0.325
    entries = [_entry(90, "right"), _entry(80, "wrong")]
    stats = dj.compute_stats(entries)
    assert stats["brier"] == 0.325


def test_brier_uses_predicted_when_set():
    # predicted overrides confidence-derived prob (don't double-count).
    entries = [_entry(90, "right", predicted=0.5)]  # p=0.5, o=1 → (0.5-1)^2 = 0.25
    assert dj.compute_stats(entries)["brier"] == 0.25


def test_brier_none_when_no_resolved():
    assert dj.compute_stats([_entry(90, None, status="open")])["brier"] is None  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# TEETH 2 — two-axis: high-confidence-WRONG → actual 0.0, not ~95              #
# --------------------------------------------------------------------------- #
def test_two_axis_high_confidence_wrong_scores_actual_zero():
    # band 90-100 with TWO resolved entries, BOTH outcome=wrong.
    entries = [_entry(95, "wrong", domain="a"), _entry(92, "wrong", domain="b")]
    stats = dj.compute_stats(entries)
    band = next(b for b in stats["calibration"] if b.band == "90-100")
    # actual = %(outcome=="right") = 0.0 — NOT 95 (the predicted/confidence axis).
    # A bug scoring on confidence alone would report ~95 here → this assert catches it.
    assert band.actual == 0.0
    assert band.predicted == 95.0  # the predicted axis IS 95 (midpoint) — they DIFFER
    assert band.n == 2


def test_two_axis_high_confidence_right_scores_actual_high():
    entries = [_entry(95, "right"), _entry(92, "right")]
    band = next(b for b in dj.compute_stats(entries)["calibration"] if b.band == "90-100")
    assert band.actual == 100.0  # both right → 100; diverges from the wrong case above


def test_calibration_drops_confidence_below_50():
    # confidence 40 < 50 → not a confidence claim to score → no band.
    assert dj.compute_stats([_entry(40, "right")])["calibration"] == []


# --------------------------------------------------------------------------- #
# TEETH 3 — bias min-n gate                                                     #
# --------------------------------------------------------------------------- #
def test_bias_three_all_wrong_not_flagged():
    # 3 all-wrong in one domain → n<4 → NOT flagged (no sparse-data false positive).
    entries = [_entry(70, "wrong", domain="crypto") for _ in range(3)]
    assert dj.compute_stats(entries)["biasFlags"] == []


def test_bias_four_majority_wrong_flagged():
    # 4 resolved in 'crypto', 3 wrong (75% > 60%) → flagged.
    entries = ([_entry(70, "wrong", domain="crypto") for _ in range(3)]
               + [_entry(70, "right", domain="crypto")])
    flags = dj.compute_stats(entries)["biasFlags"]
    assert len(flags) == 1
    assert flags[0].domain == "crypto" and flags[0].n == 4 and flags[0].wrongRate == 0.75


def test_bias_exactly_60pct_not_flagged():
    # wrongRate must EXCEED 0.60 (strict >). 3/5 = 0.60 → NOT flagged.
    entries = ([_entry(70, "wrong", domain="d") for _ in range(3)]
               + [_entry(70, "right", domain="d") for _ in range(2)])
    assert dj.compute_stats(entries)["biasFlags"] == []


# --------------------------------------------------------------------------- #
# resolved-set scoping                                                          #
# --------------------------------------------------------------------------- #
def test_open_entries_excluded_from_all_stats():
    entries = [
        _entry(90, "right"),                      # resolved
        _entry(95, None, status="open"),          # open — excluded
    ]
    stats = dj.compute_stats(entries)
    assert stats["count"] == 2 and stats["resolvedCount"] == 1
    # Brier over the 1 resolved only: (0.9-1)^2 = 0.01
    assert stats["brier"] == 0.01


def test_empty_is_honest_zero():
    assert dj.compute_stats([]) == {
        "count": 0, "resolvedCount": 0, "brier": None,
        "calibration": [], "biasFlags": [],
    }


# --------------------------------------------------------------------------- #
# CRUD (md_store round-trip)                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture
def dj_db(isolated_paths):
    return isolated_paths


def test_create_get_roundtrip(dj_db):
    e = dj.create_entry(DecisionInput(decision="ship W7", confidence=70, domain="project"))
    got = dj.get_entry(e.id)
    assert got is not None and got.decision == "ship W7" and got.confidence == 70
    assert got.status == "open" and got.outcome is None


def test_resolve_partial_keeps_core_fields(dj_db):
    # W7-A2-fix: the NATURAL resolve supplies ONLY status+outcome(+lesson); core
    # fields (decision/confidence/domain) are KEPT from the existing entry.
    e = dj.create_entry(DecisionInput(decision="buy X", confidence=80, domain="investment",
                                      thesis="undervalued"))
    upd = dj.update_entry(e.id, DecisionUpdate(
        status="resolved", outcome="wrong", lesson="thesis broke"))
    assert upd is not None and upd.status == "resolved" and upd.outcome == "wrong"
    # core fields preserved despite not being resent
    assert upd.decision == "buy X" and upd.confidence == 80 and upd.domain == "investment"
    assert upd.thesis == "undervalued" and upd.lesson == "thesis broke"
    assert upd.createdAt == e.createdAt  # preserved


def test_update_missing_returns_none(dj_db):
    assert dj.update_entry("nope", DecisionUpdate(status="resolved", outcome="right")) is None


def test_delete(dj_db):
    e = dj.create_entry(DecisionInput(decision="d", confidence=50, domain="x"))
    assert dj.delete_entry(e.id) is True
    assert dj.delete_entry(e.id) is False  # gone


# --------------------------------------------------------------------------- #
# schema validation                                                            #
# --------------------------------------------------------------------------- #
def test_confidence_out_of_range_422():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DecisionInput(decision="d", confidence=101, domain="x")
    with pytest.raises(ValidationError):
        DecisionInput(decision="d", confidence=-1, domain="x")


def test_confidence_boundaries_valid():
    assert DecisionInput(decision="d", confidence=0, domain="x").confidence == 0
    assert DecisionInput(decision="d", confidence=100, domain="x").confidence == 100


# --------------------------------------------------------------------------- #
# API + auto-discovery                                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(dj_db):
    from main import app
    return TestClient(app)


def test_api_crud_and_stats(client):
    # create two resolved + the Brier fixture via the API
    a = client.post("/decision-journal", json={"decision": "A", "confidence": 90, "domain": "g"}).json()["data"]["id"]
    b = client.post("/decision-journal", json={"decision": "B", "confidence": 80, "domain": "g"}).json()["data"]["id"]
    client.put(f"/decision-journal/{a}", json={"decision": "A", "confidence": 90, "domain": "g", "status": "resolved", "outcome": "right"})
    client.put(f"/decision-journal/{b}", json={"decision": "B", "confidence": 80, "domain": "g", "status": "resolved", "outcome": "wrong"})
    data = client.get("/decision-journal").json()["data"]
    assert data["count"] == 2 and data["resolvedCount"] == 2
    assert data["brier"] == 0.325  # the locked fixture, end-to-end


def test_api_empty_honest(client):
    data = client.get("/decision-journal").json()["data"]
    assert data["count"] == 0 and data["brier"] is None
    assert data["calibration"] == [] and data["biasFlags"] == []


def test_api_get_missing_404(client):
    assert client.get("/decision-journal/nope").status_code == 404


def test_api_natural_resolve_put_is_200_not_422(client):
    # W7-A2-fix REGRESSION GUARD: the natural resolve — PUT with ONLY {status,outcome}
    # — must be 200, NOT 422 (the bug: PUT required decision/confidence/domain).
    eid = client.post("/decision-journal", json={
        "decision": "ship it", "confidence": 75, "domain": "project"}).json()["data"]["id"]
    r = client.put(f"/decision-journal/{eid}", json={"status": "resolved", "outcome": "right"})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "resolved" and d["outcome"] == "right"
    # core fields kept (not wiped to defaults)
    assert d["decision"] == "ship it" and d["confidence"] == 75 and d["domain"] == "project"


def test_api_resolve_via_put_then_brier_end_to_end(client):
    # THE end-to-end teeth (built-but-not-wired-gap): POST 2 → PUT-resolve each with
    # ONLY {status,outcome} via HTTP → GET stats → brier==0.325. The path that the
    # unit tests (compute_stats on hand-built objects) never exercised.
    a = client.post("/decision-journal", json={"decision": "A", "confidence": 90, "domain": "g"}).json()["data"]["id"]
    b = client.post("/decision-journal", json={"decision": "B", "confidence": 80, "domain": "g"}).json()["data"]["id"]
    assert client.put(f"/decision-journal/{a}", json={"status": "resolved", "outcome": "right"}).status_code == 200
    assert client.put(f"/decision-journal/{b}", json={"status": "resolved", "outcome": "wrong"}).status_code == 200
    data = client.get("/decision-journal").json()["data"]
    assert data["resolvedCount"] == 2
    assert data["brier"] == 0.325  # the locked fixture, fully through the resolve workflow


def test_api_auto_discovered_in_health(client):
    modules = client.get("/health").json()["data"]["modules"]
    assert "decision-journal" in modules
