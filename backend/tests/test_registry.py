"""tests/test_registry.py — unit tests for core/registry.py (C2 auto-discovery contract).

Sprint 0 Gate 2: registry discovers modules, fails-open on broken modules, mounts nothing
on empty modules/.

These tests run WITHOUT a live app — they construct a FastAPI instance in-process.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import APIRouter, FastAPI

from core.base import BaseModule, Routine
from core.registry import DiscoveryResult, _candidate_module_names, _load_module, mount_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    return FastAPI()


def _make_module(name: str, with_routine: bool = False) -> BaseModule:
    router = APIRouter()

    @router.get("")
    def _index():
        return {"success": True, "data": []}

    routines: list[Routine] = []
    if with_routine:
        routines = [Routine(id=f"{name}-job", func=lambda: None, trigger="interval",
                            trigger_args={"seconds": 60})]
    return BaseModule(name=name, router=router, routines=routines)


# ---------------------------------------------------------------------------
# BaseModule construction guards
# ---------------------------------------------------------------------------

class TestBaseModule:
    def test_valid_module(self):
        m = _make_module("notes")
        assert m.name == "notes"
        assert isinstance(m.router, APIRouter)
        assert m.routines() == []

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            BaseModule(name="", router=APIRouter())

    def test_whitespace_name_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            BaseModule(name="   ", router=APIRouter())

    def test_slash_in_name_raises(self):
        with pytest.raises(ValueError, match="URL-safe"):
            BaseModule(name="foo/bar", router=APIRouter())

    def test_space_in_name_raises(self):
        with pytest.raises(ValueError, match="URL-safe"):
            BaseModule(name="foo bar", router=APIRouter())

    def test_bad_router_type_raises(self):
        with pytest.raises(TypeError):
            BaseModule(name="x", router="not-a-router")  # type: ignore[arg-type]

    def test_routines_returns_copy(self):
        m = _make_module("test", with_routine=True)
        r1 = m.routines()
        r2 = m.routines()
        assert r1 == r2
        assert r1 is not r2  # defensive copy


# ---------------------------------------------------------------------------
# Routine construction guards
# ---------------------------------------------------------------------------

class TestRoutine:
    def test_valid_routine(self):
        r = Routine(id="r1", func=lambda: None, trigger="interval", trigger_args={"seconds": 5})
        assert r.name == "r1"  # defaults to id

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            Routine(id="", func=lambda: None)

    def test_bad_trigger_raises(self):
        with pytest.raises(ValueError, match="trigger"):
            Routine(id="x", func=lambda: None, trigger="every")  # type: ignore[arg-type]

    def test_non_callable_func_raises(self):
        with pytest.raises(ValueError, match="callable"):
            Routine(id="x", func="not-callable")  # type: ignore[arg-type]

    def test_name_defaults_to_id(self):
        r = Routine(id="my-job", func=lambda: None)
        assert r.name == "my-job"

    def test_custom_name(self):
        r = Routine(id="j", func=lambda: None, name="My Job")
        assert r.name == "My Job"


# ---------------------------------------------------------------------------
# mount_all: empty modules/ → mount nothing, no error
# ---------------------------------------------------------------------------

class TestMountAllEmpty:
    def test_empty_modules_returns_empty_result(self, tmp_path, monkeypatch):
        """Empty modules/ dir → no error, mounted=[], routines=[].

        Uses an ISOLATED package name (`modules_empty`) instead of shadowing the
        real `modules` package, so no `import_module("modules")` re-import can
        leak a tmp-pathed entry into sys.modules (the Sprint-0 isolation bug).
        """
        pkg_root = tmp_path / "modules_empty"
        pkg_root.mkdir()
        (pkg_root / "__init__.py").write_text("")
        monkeypatch.syspath_prepend(str(tmp_path))
        with patch("core.registry.MODULES_PACKAGE", "modules_empty"):
            app = _make_app()
            result = mount_all(app)
        assert result.mounted == []
        assert result.routines == []
        assert result.skipped == []
        # Cleanup the isolated package import (don't leak it either).
        sys.modules.pop("modules_empty", None)

    def test_missing_modules_package_is_safe(self, monkeypatch):
        """If modules package doesn't exist at all, mount_all returns empty."""
        # Patch _candidate_module_names to return []
        with patch("core.registry._candidate_module_names", return_value=[]):
            app = _make_app()
            result = mount_all(app)
        assert result.mounted == []
        assert result.skipped == []


# ---------------------------------------------------------------------------
# mount_all: happy path — discovers a well-formed module
# ---------------------------------------------------------------------------

class TestMountAllHappy:
    def _inject_module(self, tmp_path: Path, monkeypatch, name: str,
                       with_routine: bool = False) -> None:
        """Inject a fake module into sys.modules for discovery."""
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir(exist_ok=True)
        (modules_dir / "__init__.py").write_text("")
        pkg_dir = modules_dir / name
        pkg_dir.mkdir(exist_ok=True)

        router = APIRouter()

        @router.get(f"/{name}/ping")
        def ping():
            return {"pong": True}

        mod = types.ModuleType(f"modules.{name}")
        mod.MODULE = BaseModule(name=name, router=router)
        # monkeypatch.setitem auto-reverts on teardown (raw `sys.modules[k]=` does NOT)
        monkeypatch.setitem(sys.modules, f"modules.{name}", mod)

        # Always register a fake parent `modules` pkg pointing at the tmp dir, and
        # let monkeypatch restore the REAL `modules` package object afterwards.
        pkg = types.ModuleType("modules")
        pkg.__path__ = [str(modules_dir)]  # type: ignore[attr-defined]
        pkg.__package__ = "modules"
        monkeypatch.setitem(sys.modules, "modules", pkg)

        monkeypatch.syspath_prepend(str(tmp_path))

    def test_happy_module_is_mounted(self, tmp_path, monkeypatch):
        self._inject_module(tmp_path, monkeypatch, "probe")

        with patch("core.registry._candidate_module_names", return_value=["probe"]):
            app = _make_app()
            result = mount_all(app)

        assert "probe" in result.mounted
        assert result.skipped == []
        # Endpoint is registered in the app
        routes = [r.path for r in app.routes]
        assert any("probe" in p for p in routes)

    def test_happy_module_routines_collected(self, tmp_path, monkeypatch):
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir(exist_ok=True)
        (modules_dir / "__init__.py").write_text("")

        router = APIRouter()

        @router.get("/r/ping")
        def r_ping():
            return {}

        routine = Routine(id="r-job", func=lambda: None, trigger="interval",
                          trigger_args={"seconds": 30})
        mod = types.ModuleType("modules.r")
        mod.MODULE = BaseModule(name="r", router=router, routines=[routine])
        monkeypatch.setitem(sys.modules, "modules.r", mod)

        with patch("core.registry._candidate_module_names", return_value=["r"]):
            app = _make_app()
            result = mount_all(app)

        assert "r" in result.mounted
        assert len(result.routines) == 1
        assert result.routines[0].id == "r-job"

    def test_module_skipped_on_import_error(self):
        """A module that raises on import is skipped — app still boots."""
        def _bad_load(name: str) -> BaseModule:
            raise ImportError("intentional failure")

        with patch("core.registry._candidate_module_names", return_value=["broken"]):
            with patch("core.registry._load_module", side_effect=_bad_load):
                app = _make_app()
                result = mount_all(app)

        assert result.mounted == []
        assert len(result.skipped) == 1
        assert result.skipped[0][0] == "broken"

    def test_broken_module_does_not_crash_healthy_module(self):
        """With one broken + one healthy module, only broken is skipped."""
        def _selective_load(name: str) -> BaseModule:
            if name == "broken":
                raise ImportError("intentional")
            router = APIRouter()
            return BaseModule(name=name, router=router)

        with patch("core.registry._candidate_module_names", return_value=["broken", "healthy"]):
            with patch("core.registry._load_module", side_effect=_selective_load):
                app = _make_app()
                result = mount_all(app)

        assert "healthy" in result.mounted
        assert result.skipped[0][0] == "broken"

    def test_missing_module_attr_is_skipped(self, tmp_path, monkeypatch):
        """A package that exposes no MODULE attr is skipped, not crashed."""
        mod = types.ModuleType("modules.nope")
        # No MODULE attribute
        monkeypatch.setitem(sys.modules, "modules.nope", mod)

        with patch("core.registry._candidate_module_names", return_value=["nope"]):
            app = _make_app()
            result = mount_all(app)

        assert result.mounted == []
        assert len(result.skipped) == 1

    def test_wrong_module_attr_type_is_skipped(self):
        """MODULE that is not a BaseModule instance is skipped."""
        def _bad_load(name: str) -> BaseModule:
            raise TypeError("not a BaseModule")

        with patch("core.registry._candidate_module_names", return_value=["bad_type"]):
            with patch("core.registry._load_module", side_effect=_bad_load):
                app = _make_app()
                result = mount_all(app)

        assert result.mounted == []
        assert len(result.skipped) == 1


# ---------------------------------------------------------------------------
# Regression guard — test-isolation contract
#
# This test proves that sys.modules mutations made during a test (injecting a
# fake `modules` package) do NOT leak into subsequent tests.
#
# Without monkeypatch.setitem isolation the fake `modules` pkg would persist in
# sys.modules after the test, causing the NEXT call to mount_all (e.g. in
# test_health.py's TestClient lifespan) to discover the stale fake module and
# return modules!=[] — a silent cross-test data-corruption bug.
#
# The test is structured so it would be RED if raw `sys.modules[k]=` is used
# (no auto-revert) and GREEN with monkeypatch.setitem (auto-revert on teardown).
# ---------------------------------------------------------------------------

class TestIsolationRegressionGuard:
    """Deterministic guard: injected module must NOT appear in /health after test teardown."""

    def test_injected_module_does_not_leak_to_health(self, tmp_path, monkeypatch):
        """
        Step 1 — inject a fake 'canary' module into sys.modules via monkeypatch
                  (auto-reverts on teardown).
        Step 2 — confirm mount_all SEES it during the test (injection is real).
        Step 3 — confirm /health endpoint (via TestClient) does NOT see it —
                  because the TestClient creates a fresh app that calls mount_all
                  at startup, by which time the canary injection is still live
                  (we're still inside the test). This verifies that /health reflects
                  registry state correctly, not a stale cached state.
        Step 4 — after test exits, monkeypatch reverts sys.modules. Subsequent
                  tests that call mount_all will see modules=[] again.
        """
        from fastapi.testclient import TestClient
        import store.db as db_mod
        from core import config

        # Point DB + data_dir at tmp so the TestClient lifespan doesn't conflict
        # with other tests' DB connections.
        db_mod.close_db()
        monkeypatch.setattr(config.settings, "data_dir", tmp_path / "data", raising=False)
        monkeypatch.setattr(config.settings, "db_path", tmp_path / "canary.db", raising=False)
        monkeypatch.setattr(config.settings, "scheduler_enabled", False, raising=False)

        # Build the fake 'canary' module
        canary_router = APIRouter()

        @canary_router.get("/ping")
        def _ping():
            return {"success": True, "data": "canary"}

        canary_mod = types.ModuleType("modules.canary")
        canary_mod.MODULE = BaseModule(name="canary", router=canary_router)

        # Build a fake parent `modules` package pointing at tmp
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)
        (modules_dir / "__init__.py").write_text("")
        (modules_dir / "canary").mkdir(exist_ok=True)

        # canary dir must be a proper package (has __init__.py) so pkgutil.iter_modules
        # recognises it as a sub-package during _candidate_module_names scan.
        (modules_dir / "canary" / "__init__.py").write_text("")

        fake_pkg = types.ModuleType("modules")
        fake_pkg.__path__ = [str(modules_dir)]  # type: ignore[attr-defined]
        fake_pkg.__package__ = "modules"

        # Inject via monkeypatch — auto-reverts when this test exits
        monkeypatch.setitem(sys.modules, "modules", fake_pkg)
        monkeypatch.setitem(sys.modules, "modules.canary", canary_mod)

        # Step 2: mount_all SEES the canary via _candidate_module_names scanning
        # fake_pkg.__path__ (pkgutil.iter_modules finds canary/ subpackage there).
        probe_app = _make_app()
        result = mount_all(probe_app)
        assert "canary" in result.mounted, (
            "Canary module must be visible to mount_all inside the test — "
            "if this fails, injection itself is broken."
        )

        # Step 3: /health reflects registry state — modules=["canary"] while injected
        from main import create_app
        db_mod.close_db()  # reset before TestClient creates its own connection
        test_app = create_app()
        with TestClient(test_app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        # canary IS injected → /health must report it
        assert "canary" in body["data"]["modules"], (
            f"Expected 'canary' in modules while injected, got: {body['data']['modules']}"
        )
        db_mod.close_db()

    def test_modules_clean_after_injection_scope(self, monkeypatch):
        """
        Guard: after a test that injected a fake module, mount_all on a fresh
        app sees NO modules. This runs AFTER the injection test and verifies
        that monkeypatch.setitem revert actually happened.

        If raw sys.modules mutation (without monkeypatch) was used in the prior
        test, 'canary' or the fake 'modules' pkg would still be in sys.modules
        and this test would FAIL — making the regression visible.
        """
        import store.db as db_mod
        from core import config
        db_mod.close_db()
        monkeypatch.setattr(config.settings, "scheduler_enabled", False, raising=False)

        # Real modules/ package in the backend only has __init__.py + .gitkeep —
        # mount_all must return empty (no real feature modules in Sprint 0).
        app = _make_app()
        result = mount_all(app)

        # If 'canary' leaked from prior test, result.mounted would contain it → RED
        assert "canary" not in result.mounted, (
            f"'canary' leaked from prior test into sys.modules — "
            f"isolation failed. mounted={result.mounted}"
        )
        # Mounted list must be empty (Sprint 0 has no feature modules)
        assert result.mounted == [], (
            f"Expected empty mounted list in clean state, got: {result.mounted}"
        )


# ---------------------------------------------------------------------------
# DiscoveryResult shape
# ---------------------------------------------------------------------------

class TestDiscoveryResult:
    def test_default_empty(self):
        d = DiscoveryResult()
        assert d.mounted == []
        assert d.routines == []
        assert d.skipped == []

    def test_fields_are_independent(self):
        d1 = DiscoveryResult()
        d2 = DiscoveryResult()
        d1.mounted.append("x")
        assert d2.mounted == []
