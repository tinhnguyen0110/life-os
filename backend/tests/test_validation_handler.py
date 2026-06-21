"""tests/test_validation_handler.py — AGENT-ERROR-P7 (#69): the app-level RequestValidationError
handler is the TRUE FINAL of the #46 agent-error story.

FastAPI's RequestValidationError (path/query/body type + missing-field) fires BEFORE any route
handler, so the per-handler #46 migration could never reach it — a bad path int / malformed body
still returned the raw FastAPI ``{detail:[{type,loc,msg,...}]}`` list, the one raw-error class an
agent could still meet. ONE app-level handler (main.create_app) converts it to the flat agent_error
envelope ``{error:{code:INVALID_INPUT,message,hint,retryable:false}}``.

These tests lock:
  - 422 STATUS is PRESERVED (only the BODY shape changes).
  - the body is the flat ``{error:...}`` — NO top-level ``detail`` (the agent never parses a raw list).
  - the DISTINGUISHING invariant: the handler fires ONLY on a validation FAILURE — a VALID request
    still returns 2xx (the handler doesn't swallow good requests).
  - all three flavors: bad PATH int, missing-required BODY field, bad-TYPE/enum BODY field.

RED without the handler (comment it out in main.create_app → these fail with a {detail} list body).
Mirrors test_cors.py's fixture (real app via create_app + isolated paths) — an app-level invariant.
"""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fresh real app (isolated DB/data dir, scheduler off) with the full middleware +
    exception-handler stack. Mirrors test_cors.py — an app-level test needs the WHOLE app."""
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    db.close_db()
    import main as main_mod

    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def _assert_flat_invalid_input(resp) -> dict:
    """Every validation failure must be the flat agent_error INVALID_INPUT shape — 422 status,
    NO top-level ``detail`` list, a readable message + actionable hint, retryable=False
    (deterministic — fix the input, don't retry)."""
    assert resp.status_code == 422, f"validation must stay 422, got {resp.status_code}: {resp.text}"
    j = resp.json()
    assert "detail" not in j, f"agent must NEVER meet a raw {{detail}} list — got {j}"
    err = j["error"]
    assert err["code"] == "INVALID_INPUT"
    assert err["retryable"] is False  # deterministic
    assert err["message"] and err["hint"]  # both non-empty + agent-actionable
    return err


def test_bad_path_int_is_flat_invalid_input(client):
    """A non-int path param (the team-lead live finding: GET /reminders/NOTANINT) → flat
    {error:INVALID_INPUT}, NOT the raw {detail:[{int_parsing}]}."""
    err = _assert_flat_invalid_input(client.get("/reminders/NOTANINT"))
    # the message surfaces WHERE it failed (loc) so the agent can fix the right field.
    assert "path" in err["message"].lower() or "reminder" in err["message"].lower() \
        or "int" in err["message"].lower()


def test_bad_path_int_on_another_route_too(client):
    """ONE handler covers ALL routes — not just reminders. An int-typed path elsewhere
    (agent-proposals/{id}) gets the same flat shape."""
    _assert_flat_invalid_input(client.get("/agent-proposals/NOTANINT"))


def test_missing_required_body_field_is_flat_invalid_input(client):
    """A missing required body field (POST /journal without required keys) is a body
    RequestValidationError → flat {error:INVALID_INPUT}, not a {detail} list."""
    _assert_flat_invalid_input(client.post("/journal", json={"action": "BUY"}))


def test_bad_type_body_field_is_flat_invalid_input(client):
    """A wrong-type / bad-enum body field (journal confidence as a string) → flat shape."""
    _assert_flat_invalid_input(
        client.post("/journal", json={"action": "BUY", "asset": "X", "reason": "r",
                                      "confidence": "not-a-number"})
    )


def test_valid_request_is_NOT_intercepted(client):
    """THE DISTINGUISHING: the handler fires ONLY on a validation FAILURE. A VALID request
    must still return 2xx — a handler that swallowed good requests would be caught here
    (a 422-on-everything bug would pass the failure tests but fail THIS one)."""
    # /health takes no input → can never raise RequestValidationError → must be 200.
    r = client.get("/health")
    assert r.status_code == 200, f"valid request must NOT be intercepted, got {r.status_code}"
    assert r.json()["success"] is True
    # a valid int path on an existing-or-not id is NOT a validation error → 404/200, never 422.
    r2 = client.get("/reminders/999999")
    assert r2.status_code != 422, "a valid-typed id is not a validation error"
