"""tests/test_tracing_template_add.py — TRACING-UX2 #124: import a saved template → today's activity.

The user curates their OWN reusable todos (the #109 template store) + adds them to today with one
click. This is an EXPLICIT user action ("+ Từ mẫu"), NOT the rejected hard-code-chip auto-seed.

Distinguishing cases (the dispatch pass-bar):
  - POST /templates/{id}/add → creates today's activity from the template (right name/goal/unit);
  - 404 on an unknown template id;
  - already-added-today → SKIPPED (added=False, returns the EXISTING, NO duplicate) — the decided
    idempotent behavior;
  - add-all → adds all non-hidden, skips already-present, honest-empty when none;
  - 🔴 import → a BINARY TODO: goal=1, name-only — the template's stored goal/unit/emoji are
    DROPPED (#124 correction; the #122 text+tick model — checkboxes, not progress bars);
  - SCOPED: a template-add reads tracing_template + writes tracing_activities only (the store
    template fns never touch activities; the add path is the only template→activity write).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.tracing import service as svc
from modules.tracing import store as trc_store
from modules.tracing.schema import TemplateInput


@pytest.fixture
def db(isolated_paths):
    trc_store.init_tracing_tables()
    return isolated_paths


@pytest.fixture
def api(db):
    from main import create_app
    return TestClient(create_app())


# --- add one template → today's activity ------------------------------------ #
def test_add_template_imports_as_binary_todo_name_only(db):
    """🔴 #124 CORRECTION: import = a BINARY TODO. The template carries goal=20/unit=phút/emoji=🎸,
    but the imported activity is goal=1 + name-only (stored goal/unit/emoji DROPPED) — the #122
    text+tick model (checkboxes, not progress bars)."""
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0, unit="phút", emoji="🎸"))
    activity, added = svc.add_template_to_today("guitar")
    assert added is True
    assert activity is not None
    assert activity.id == "guitar" and activity.name == "Tập guitar"  # name preserved
    assert activity.goal == 1.0, "import → goal=1 (binary todo), NOT the stored goal 20"
    assert activity.unit == "" and activity.emoji == "", "stored unit/emoji DROPPED on import"
    # it's a real activity now (on the board)
    assert svc.get_activity("guitar") is not None
    # a template starts with NO reminder (the user sets that separately)
    assert activity.remindAt is None and activity.remindRepeat == "off"


def test_add_template_always_goal_one_even_if_stored_higher(db):
    """A measured-habit template (stored goal=8) still imports as goal=1 (binary todo, not a progress bar)."""
    svc.upsert_template("water", TemplateInput(name="Uống nước", goal=8.0, unit="ly"))
    activity, added = svc.add_template_to_today("water")
    assert added is True and activity is not None and activity.goal == 1.0


def test_imported_stored_goal20_template_is_tickable(db):
    """🔴 THE BUG team-lead verified (behavior-test, not field-read): the #122 todo-row ticks with
    val=1 and shows done = today.done (val ≥ goal). If the import had kept the template's stored
    goal=20, ONE tick (val=1 < 20) → done STAYS FALSE → an UN-TICKABLE todo. With goal=1, one tick
    (val=1 ≥ 1) → done=True. EXERCISE it: import a stored-goal=20 template → tick once → done."""
    from modules.tracing.schema import LogInput
    svc.upsert_template("habit20", TemplateInput(name="Big habit", goal=20.0, unit="reps"))
    activity, added = svc.add_template_to_today("habit20")
    assert added is True and activity.goal == 1.0
    # ONE tick (val=1) — the #122 todo tick
    view = svc.log_session("habit20", LogInput(val=1.0))
    assert view.today.done is True, "a single tick must turn the imported todo DONE (the bug: goal=20 → never done)"
    assert view.today.val == 1.0


def test_add_unknown_template_is_none(db):
    activity, added = svc.add_template_to_today("no-such-template")
    assert activity is None and added is False


# --- already-added-today → SKIP (no dup, returns existing) ------------------- #
def test_add_already_present_skips_no_dup(db):
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    first, added1 = svc.add_template_to_today("guitar")
    assert added1 is True
    second, added2 = svc.add_template_to_today("guitar")
    assert added2 is False, "already-added → added=False (idempotent)"
    assert second is not None and second.id == first.id  # returns the EXISTING, no dup
    # only ONE activity with that id exists
    from modules.tracing import store
    rows = [r for r in store.list_activities(include_archived=True) if r["id"] == "guitar"]
    assert len(rows) == 1, "no duplicate activity created"


# --- #130: ARCHIVED matched id → un-archive + re-surface (added:true) -------- #
def test_add_archived_template_unarchives_and_resurfaces(db):
    """🔴 #130 (the FE-found gap): add a template, archive it, then '+ Từ mẫu → X' again →
    UN-ARCHIVES + re-surfaces it (added=True, back on the board). The old behavior returned
    added=False + left it archived → the click silently did nothing."""
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    a, added1 = svc.add_template_to_today("guitar")
    assert added1 is True
    assert svc.archive_activity("guitar") is True  # archive it (off the board)
    # the activity is now archived → NOT in the default board
    assert "guitar" not in {x.id for x in svc.overview().activities}
    # re-add the template → un-archive + added:True (the #130 fix)
    re, added2 = svc.add_template_to_today("guitar")
    assert added2 is True, "re-adding an archived id must un-archive (added=True), not silently skip"
    assert re is not None and re.id == "guitar" and re.archived is False
    # back on the board, and STILL only one row (no dup — same row un-archived)
    assert "guitar" in {x.id for x in svc.overview().activities}
    from modules.tracing import store
    rows = [r for r in store.list_activities(include_archived=True) if r["id"] == "guitar"]
    assert len(rows) == 1, "un-archive reuses the SAME row, no duplicate"


def test_add_live_id_still_skips_unchanged(db):
    """#130 keeps the LIVE-id behavior unchanged: a non-archived already-present id → added=False."""
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    svc.add_template_to_today("guitar")
    _re, added = svc.add_template_to_today("guitar")  # still LIVE → skip
    assert added is False


def test_archived_unarchive_preserves_logs(db):
    """The un-archive reuses the same row → the activity's logged history is preserved (not a fresh
    row). Log a session, archive, re-add → the prior log is still there."""
    from modules.tracing.schema import LogInput
    svc.upsert_template("water", TemplateInput(name="Uống nước", goal=8.0))
    svc.add_template_to_today("water")
    svc.log_session("water", LogInput(val=1.0))
    svc.archive_activity("water")
    re, added = svc.add_template_to_today("water")
    assert added is True and re is not None
    # via the overview the activity is back; its today reflects the preserved log (same row)
    ov_act = next((x for x in svc.overview().activities if x.id == "water"), None)
    assert ov_act is not None and ov_act.today.val == 1.0, "the log survived archive→un-archive"


def test_add_all_unarchives_archived_member(db):
    """#130: add-all re-surfaces an archived member (counted as created, not skipped)."""
    seeds = svc.list_templates()
    first_id = seeds[0].id
    svc.add_template_to_today(first_id)
    svc.archive_activity(first_id)  # archive one member
    created, skipped = svc.add_all_templates()
    assert first_id in {a.id for a in created}, "add-all must un-archive + re-create the archived member"
    assert first_id not in skipped


# --- add-all → all non-hidden, skip present, honest-empty -------------------- #
def test_add_all_seeds_create_today_activities(db):
    """With no user overrides, add-all adds all the SEED templates (the user's default list)."""
    seeds = svc.list_templates()
    assert len(seeds) >= 1  # seeds exist
    created, skipped = svc.add_all_templates()
    assert skipped == []
    assert {a.id for a in created} == {t.id for t in seeds}  # all seeds → activities


def test_add_all_skips_already_present(db):
    # add one seed first, then add-all → that one is skipped, the rest created
    seeds = svc.list_templates()
    first_id = seeds[0].id
    svc.add_template_to_today(first_id)
    created, skipped = svc.add_all_templates()
    assert first_id in skipped
    assert first_id not in {a.id for a in created}
    assert len(created) == len(seeds) - 1


def test_add_all_honest_empty_when_no_templates(db):
    """Tombstone every seed → list_templates empty → add-all returns ([],[])."""
    for t in svc.list_templates():
        svc.delete_template(t.id)  # seed → tombstone, user → remove
    assert svc.list_templates() == []
    created, skipped = svc.add_all_templates()
    assert created == [] and skipped == []


def test_add_all_respects_hidden_tombstone(db):
    """A tombstoned seed is NOT added by add-all (the #109 hidden model is respected)."""
    seeds = svc.list_templates()
    hidden_id = seeds[0].id
    svc.delete_template(hidden_id)  # tombstone it
    created, _ = svc.add_all_templates()
    assert hidden_id not in {a.id for a in created}


# --- SCOPED: template store untouched by activities; add writes activities only #
def test_add_does_not_mutate_template_store(db):
    svc.upsert_template("guitar", TemplateInput(name="Tập guitar", goal=20.0))
    before = {t.id for t in svc.list_templates()}
    svc.add_template_to_today("guitar")
    after = {t.id for t in svc.list_templates()}
    assert before == after, "adding a template to today must NOT change the template list"


# --- REST surface ------------------------------------------------------------ #
def test_rest_add_template(api):
    api.put("/tracing/templates/guitar", json={"name": "Tập guitar", "goal": 20.0, "unit": "phút"})
    r = api.post("/tracing/templates/guitar/add")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    # #124 correction: imported as a binary todo → goal=1 (NOT the stored 20), name preserved
    assert d["added"] is True and d["activity"]["id"] == "guitar" and d["activity"]["goal"] == 1.0


def test_rest_add_unknown_template_404(api):
    r = api.post("/tracing/templates/ghost/add")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_add_already_present_added_false(api):
    api.put("/tracing/templates/guitar", json={"name": "Tập guitar", "goal": 20.0})
    api.post("/tracing/templates/guitar/add")
    r = api.post("/tracing/templates/guitar/add")
    assert r.status_code == 200 and r.json()["data"]["added"] is False


def test_rest_add_all(api):
    r = api.post("/tracing/templates/add-all")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert isinstance(d["created"], list) and isinstance(d["skipped"], list)
    assert len(d["created"]) >= 1  # the seeds got added
