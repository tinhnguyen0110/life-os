"""tests/test_tracing_templates.py — TRACING-UX T1 (#109): task templates.

Templates prefill the "new activity" form. The list = SEED (immutable code) ⊕ USER OVERRIDE
(the tracing_template table). Each item tagged source. These tests are the load-bearing teeth:
  - SEED = the 3 check-ins (the built-in prefills, #173);
  - upsert → the list shows the user override (source='user', override WINS on a seed id);
  - delete a SEED → a tombstone HIDES it; delete a USER template → its row is REMOVED;
  - reset → back to pure SEED, and SCOPED (the user's real activities/logs are UNTOUCHED — the #72 lesson);
  - bulk-delete → removes/hides the given ids, idempotent, scoped;
  - bad upsert → 422; migration idempotent (re-init on an existing table → no error);
  - MCP tracing_templates ≡ REST GET /tracing/templates (#24 parity).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.tracing import reader, service as svc, store
from modules.tracing.schema import ActivityInput, TemplateInput


@pytest.fixture
def db(isolated_paths):
    store.init_tracing_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


# --------------------------------------------------------------------------- #
# SEED — the immutable built-ins                                                 #
# --------------------------------------------------------------------------- #
def test_seed_list_is_the_three_checkins_all_source_seed(db):
    """TRACING-DEFAULT (#173): a fresh vault (no overrides) → EXACTLY the 3 check-in templates, ALL
    source='seed', each with the prefill fields."""
    tpls = svc.list_templates()
    assert len(tpls) == 3, f"expected 3 seed templates (the check-ins), got {len(tpls)}"
    assert all(t.source == "seed" for t in tpls)
    assert {t.id for t in tpls} == {"checkin-sang", "checkin-trua", "report-toi"}
    # each carries the lean prefill fields (no derived metrics)
    for t in tpls:
        assert t.id and t.name and isinstance(t.goal, float) and t.goal == 1.0 and t.unit == "lần"
    # the morning check-in has its sensible prefill (VN name + emoji)
    sang = next((t for t in tpls if t.id == "checkin-sang"), None)
    assert sang is not None and sang.name == "Check-in sáng" and sang.emoji == "🌅"


# --------------------------------------------------------------------------- #
# OVERRIDE — upsert wins on a seed id; a new id appears                          #
# --------------------------------------------------------------------------- #
def test_upsert_overrides_a_seed_source_user_wins(db):
    """Upsert with a SEED id → the list shows the USER override (source='user', the override's
    fields, NOT the seed's) — override wins; the seed count stays the same (replaced, not added)."""
    before = len(svc.list_templates())
    svc.upsert_template("checkin-sang", TemplateInput(name="Sáng 5'", goal=5.0, unit="phút", emoji="🌄"))
    tpls = svc.list_templates()
    assert len(tpls) == before, "overriding a seed must REPLACE it, not add a duplicate"
    sang = next(t for t in tpls if t.id == "checkin-sang")
    assert sang.source == "user" and sang.goal == 5.0 and sang.name == "Sáng 5'"


def test_upsert_new_id_appears_as_user(db):
    """Upsert a NEW id (no matching seed) → it appears in the list as source='user'."""
    before = len(svc.list_templates())
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0, unit="phút", emoji="🎸"))
    tpls = svc.list_templates()
    assert len(tpls) == before + 1
    g = next(t for t in tpls if t.id == "guitar")
    assert g.source == "user" and g.name == "Tập guitar"


# --------------------------------------------------------------------------- #
# DELETE — seed → tombstone hides; user → row removed                            #
# --------------------------------------------------------------------------- #
def test_delete_seed_tombstones_and_hides_it(db):
    """Delete a SEED → a tombstone HIDES it from the list (the seed lives in code, can't be removed;
    we record a hide-marker). The list shrinks by 1; the id is gone."""
    before = svc.list_templates()
    assert any(t.id == "report-toi" for t in before)
    assert svc.delete_template("report-toi") is True
    after = svc.list_templates()
    assert len(after) == len(before) - 1
    assert not any(t.id == "report-toi" for t in after), "a tombstoned seed must be hidden"


def test_delete_user_template_removes_its_row(db):
    """Delete a USER template → its override row is REMOVED (not tombstoned — it has no seed to hide)."""
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    assert any(t.id == "guitar" for t in svc.list_templates())
    assert svc.delete_template("guitar") is True
    assert not any(t.id == "guitar" for t in svc.list_templates())
    # the override row is physically gone
    assert "guitar" not in {r["id"] for r in store.list_template_overrides()}


def test_delete_absent_non_seed_is_idempotent_false(db):
    """Deleting an id that is neither a seed nor a user template → False (nothing to do, no error)."""
    assert svc.delete_template("does-not-exist-xyz") is False


def test_upsert_after_tombstone_unhides(db):
    """Upserting a previously-tombstoned seed id → un-hides it (hidden reset to 0), now source='user'."""
    svc.delete_template("report-toi")  # tombstone
    assert not any(t.id == "report-toi" for t in svc.list_templates())
    svc.upsert_template("report-toi", TemplateInput(name="Tối 20'", goal=20.0))
    t = next((t for t in svc.list_templates() if t.id == "report-toi"), None)
    assert t is not None and t.source == "user" and t.goal == 20.0


# --------------------------------------------------------------------------- #
# RESET — back to pure seed, SCOPED (activities untouched — the #72 lesson)      #
# --------------------------------------------------------------------------- #
def test_reset_returns_to_pure_seed(db):
    """Reset deletes ALL overrides → the list is pure seed again (count == seed count, all 'seed')."""
    seed_count = len(svc.list_templates())
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    svc.delete_template("report-toi")  # tombstone a seed
    # the override rows exist (guitar add + report-toi tombstone) — the list is no longer pure seed
    assert len(store.list_template_overrides()) == 2
    assert any(t.source == "user" for t in svc.list_templates())  # guitar shows as user
    assert not any(t.id == "report-toi" for t in svc.list_templates())  # report-toi hidden
    n = svc.reset_templates()
    assert n == 2, "reset deletes the 2 override rows (1 user + 1 tombstone)"
    after = svc.list_templates()
    assert len(after) == seed_count and all(t.source == "seed" for t in after)


def test_reset_is_SCOPED_does_not_touch_real_activities(db):
    """🔴 THE #72 LESSON: reset deletes ONLY tracing_template — the user's real activities + their
    logs are UNTOUCHED. Seed a real activity + a log, override+reset templates, assert the activity
    and its log survive intact."""
    svc.create_activity(ActivityInput(id="run", name="Run", goal=5.0, unit="km"))
    from modules.tracing.schema import LogInput
    svc.log_session("run", LogInput(val=3.0))
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    svc.reset_templates()  # the dangerous op
    # the REAL activity + its log are intact (reset is scoped to tracing_template)
    act = svc.get_activity("run")
    assert act is not None and act.name == "Run"
    assert len(store.logs_for_activity("run")) == 1, "reset must NOT wipe real activity logs"


# --------------------------------------------------------------------------- #
# BULK-DELETE — remove/hide many, idempotent, scoped                             #
# --------------------------------------------------------------------------- #
def test_bulk_delete_removes_and_hides_given_ids(db):
    """Bulk-delete a mix of a USER template + a SEED → both gone from the list; returns the count
    that changed. Absent ids are skipped (idempotent, no error)."""
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    n = svc.bulk_delete_templates(["guitar", "report-toi", "nope-absent"])
    assert n == 2, "guitar (user) + report-toi (seed tombstone) changed; nope-absent skipped"
    ids = {t.id for t in svc.list_templates()}
    assert "guitar" not in ids and "report-toi" not in ids


def test_bulk_delete_empty_is_noop_zero(db):
    """Empty ids → 0 (no-op), the list unchanged."""
    before = len(svc.list_templates())
    assert svc.bulk_delete_templates([]) == 0
    assert len(svc.list_templates()) == before


def test_bulk_delete_does_not_touch_activities(db):
    """Bulk-delete is SCOPED to tracing_template — real activities survive (the #72 lesson, bulk path)."""
    svc.create_activity(ActivityInput(id="run", name="Run", goal=5.0))
    svc.bulk_delete_templates(["checkin-trua", "report-toi", "checkin-sang"])
    assert svc.get_activity("run") is not None


# --------------------------------------------------------------------------- #
# migration idempotent — re-init on an existing table doesn't error              #
# --------------------------------------------------------------------------- #
def test_migration_idempotent_reinit_no_error(db):
    """init_tracing_tables (which CREATE TABLE IF NOT EXISTS tracing_template) is idempotent — calling
    it again on an already-created table must not raise + the data survives."""
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    store.init_tracing_tables()  # re-run the migration on an existing, populated table
    store.init_tracing_tables()
    assert any(t.id == "guitar" for t in svc.list_templates()), "data survives a migration re-run"


# --------------------------------------------------------------------------- #
# REST endpoints + validation                                                    #
# --------------------------------------------------------------------------- #
def test_rest_get_list(api):
    r = api.get("/tracing/templates")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "templates" in data and len(data["templates"]) == 3
    assert all(set(t) >= {"id", "name", "goal", "unit", "emoji", "color", "source"} for t in data["templates"])


def test_rest_put_upsert_then_get_shows_override(api):
    r = api.put("/tracing/templates/checkin-trua",
                json={"name": "Trưa 12'", "goal": 12.0, "unit": "phút"})
    assert r.status_code == 200 and r.json()["data"]["source"] == "user"
    lst = api.get("/tracing/templates").json()["data"]["templates"]
    trua = next(t for t in lst if t["id"] == "checkin-trua")
    assert trua["goal"] == 12.0 and trua["source"] == "user"


def test_rest_delete_then_reset_round_trip(api):
    seed_n = len(api.get("/tracing/templates").json()["data"]["templates"])
    api.delete("/tracing/templates/report-toi")  # tombstone a seed
    assert len(api.get("/tracing/templates").json()["data"]["templates"]) == seed_n - 1
    rr = api.post("/tracing/templates/reset")
    assert rr.status_code == 200 and rr.json()["data"]["reset"] is True
    assert len(api.get("/tracing/templates").json()["data"]["templates"]) == seed_n


def test_rest_bulk_delete(api):
    api.put("/tracing/templates/guitar", json={"name": "Tập guitar", "goal": 20.0})
    r = api.post("/tracing/templates/bulk-delete", json={"ids": ["guitar", "report-toi", "absent"]})
    assert r.status_code == 200 and r.json()["data"]["deleted"] == 2


def test_rest_upsert_blank_name_is_422(api):
    r = api.put("/tracing/templates/foo", json={"name": "   ", "goal": 1.0})
    assert r.status_code == 422


def test_rest_upsert_negative_goal_is_422(api):
    r = api.put("/tracing/templates/foo", json={"name": "Foo", "goal": -5.0})
    assert r.status_code == 422


def test_rest_upsert_overlong_id_is_invalid(api):
    r = api.put("/tracing/templates/" + "x" * 65, json={"name": "Foo", "goal": 1.0})
    assert r.status_code in (400, 404, 422)  # over-length id → agent-error / route reject
    if r.status_code != 404:
        body = r.json()
        assert "error" in body or body.get("success") is False


# --------------------------------------------------------------------------- #
# MCP ≡ REST parity (#24)                                                        #
# --------------------------------------------------------------------------- #
def test_mcp_tracing_templates_matches_rest(api):
    """The MCP tracing_templates tool returns the same merged list as REST GET /tracing/templates
    (both via reader.list_templates → byte-identical, #24)."""
    from mcp_servers import read_server as rs
    # seed an override so the merged list is non-trivial
    api.put("/tracing/templates/guitar", json={"name": "Tập guitar", "goal": 20.0})
    rest = api.get("/tracing/templates").json()["data"]["templates"]
    mcp = rs.tracing_templates()["templates"]
    assert mcp == rest, "MCP tracing_templates must be byte-identical to REST"
    # and reader is the single source
    assert [t.model_dump() for t in reader.list_templates()] == rest
