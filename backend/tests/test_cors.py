"""tests/test_cors.py — CORS middleware regression (Sprint 2).

A browser invariant curl CANNOT see: without CORSMiddleware the FE (:3010) is
blocked by the browser from calling the API (preflight 405 / no
Access-Control-Allow-Origin). curl ignores CORS, so Sprint 0/1 curl-verification
missed this — only the live browser at S2 exposed it. This locks the invariant.

RED without the middleware (comment it out in main.create_app → these fail),
GREEN with it.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

FE_ORIGIN = "http://localhost:3010"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fresh app (isolated DB/data dir) with the real middleware stack."""
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    db.close_db()
    import main as main_mod

    importlib.reload(main_mod)
    app = main_mod.create_app()
    with TestClient(app) as c:
        yield c
    db.close_db()


def _acao(headers) -> str | None:
    """Case-insensitive Access-Control-Allow-Origin lookup."""
    for k, v in headers.items():
        if k.lower() == "access-control-allow-origin":
            return v
    return None


def test_preflight_options_on_health_returns_cors(client):
    """OPTIONS preflight from the FE origin → 200 + ACAO header (not 405)."""
    resp = client.options(
        "/health",
        headers={
            "Origin": FE_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200, f"preflight must be 200, got {resp.status_code}"
    assert _acao(resp.headers) in (FE_ORIGIN, "*"), \
        f"missing/incorrect Access-Control-Allow-Origin: {dict(resp.headers)}"


def test_preflight_options_on_projects_returns_cors(client):
    """The S2 data endpoint must be browser-reachable (preflight passes)."""
    resp = client.options(
        "/projects",
        headers={
            "Origin": FE_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200, f"preflight must be 200, got {resp.status_code}"
    assert _acao(resp.headers) in (FE_ORIGIN, "*")


def test_simple_get_has_acao_header(client):
    """A real GET from the FE origin carries the ACAO header → browser allows it."""
    resp = client.get("/health", headers={"Origin": FE_ORIGIN})
    assert resp.status_code == 200
    assert _acao(resp.headers) in (FE_ORIGIN, "*"), \
        f"GET response missing ACAO header — browser would block it: {dict(resp.headers)}"


def test_configured_origin_is_allowed(client):
    """The :3000 default origin (Next default) is also allowed."""
    resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert _acao(resp.headers) in ("http://localhost:3000", "*")
