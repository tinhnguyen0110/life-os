"""tests/test_health.py — integration test for GET /health (G1 API Gate, C4 shape).

Sprint 0. Verifies the locked C4 response shape:
    {"success": true, "data": {"status": "ok", "modules": [...], ...}}

Uses FastAPI TestClient (ASGI, no live uvicorn). The lifespan init_db() path is
tested — a fresh DB is used via a tmp dir configured before import.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """Create the FastAPI test app with isolated DB + data_dir."""
    tmp = tmp_path_factory.mktemp("healthtest")
    # Patch settings before importing main so init_db() uses the tmp path
    from core import config
    config.settings.data_dir = tmp / "data"
    config.settings.db_path = tmp / "health_test.db"
    config.settings.scheduler_enabled = False  # don't start background threads in tests

    # Reset any stale db connection from prior tests
    import store.db as db_mod
    db_mod.close_db()

    from main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c
    db_mod.close_db()


class TestHealthEndpoint:
    def test_health_200(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_success_true(self, client: TestClient):
        body = client.get("/health").json()
        assert body.get("success") is True, f"success != True: {body}"

    def test_data_status_ok(self, client: TestClient):
        body = client.get("/health").json()
        assert "data" in body, f"No 'data' key: {body}"
        assert body["data"].get("status") == "ok", f"data.status != 'ok': {body}"

    def test_data_modules_is_list(self, client: TestClient):
        body = client.get("/health").json()
        assert isinstance(body["data"].get("modules"), list), \
            f"data.modules must be list: {body}"

    def test_shape_has_required_keys(self, client: TestClient):
        body = client.get("/health").json()
        assert "success" in body and "data" in body, f"Missing top-level keys: {body}"
        assert "status" in body["data"] and "modules" in body["data"], \
            f"Missing data keys: {body['data']}"

    def test_health_reflects_discovered_modules(self, client: TestClient):
        """/health.data.modules reflects the registry's actual discovery.

        Sprint 1 adds the first feature module (`projects`), so the list is no
        longer empty — the invariant is that /health mirrors what mount_all found,
        and every entry is a clean, non-dunder module name.
        """
        body = client.get("/health").json()
        modules = body["data"]["modules"]
        assert isinstance(modules, list)
        # The projects module auto-mounts (Sprint 1) — health must report it.
        assert "projects" in modules, f"projects not discovered: {modules}"
        # No dunder/garbage names leaked into discovery.
        assert all(not m.startswith("__") for m in modules), modules

    def test_no_skipped_warning_on_clean_boot(self, client: TestClient):
        """Clean boot: no module fails to mount → no skip warning on /health."""
        body = client.get("/health").json()
        # A warning is only present when mount_all recorded skips. All real
        # modules must mount cleanly, so there must be no skip warning.
        assert not body.get("warning"), \
            f"module(s) skipped at boot (registry error?): {body.get('warning')}"

    def test_docs_endpoint_returns_html(self, client: TestClient):
        """GET /docs must return 200 HTML (OpenAPI UI)."""
        resp = client.get("/docs")
        assert resp.status_code == 200, f"/docs returned {resp.status_code}"
        assert "text/html" in resp.headers.get("content-type", ""), \
            f"/docs content-type not HTML: {resp.headers}"


class TestHealthRegistryIntegration:
    """Verify C4 + C2 hold together: health reflects registry state."""

    def test_health_reflects_registry_state(self, client: TestClient):
        """C4+C2: health returns 200 and its modules list mirrors the registry.

        The registry discovered `projects` (Sprint 1); health reports exactly the
        mounted set — the contract is "health reflects registry", not "registry
        is empty" (which was only ever true in the Sprint-0 scaffold).
        """
        body = client.get("/health").json()
        assert body["success"] is True
        assert isinstance(body["data"]["modules"], list)
        assert "projects" in body["data"]["modules"]
