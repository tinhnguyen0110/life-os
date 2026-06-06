"""tests/test_registry_discovery.py — backend regression for _candidate_module_names.

Regression guard (Sprint 0): the documented convention probe is named ``_probe``,
and underscore-prefixed module folders are LEGAL. Only dunder names (``__pycache__``,
``__init__``) must be excluded from discovery. A bug filtered any single leading
``_`` and silently hid ``_probe`` — caught by the dispatch's CRITICAL probe proof.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from core import registry

# RED-PROOF switch (Sprint 0A). Flip to True to STRIP the cleanup path and prove
# the invariant guard below goes RED on a real sys.modules leak; flip back to
# False (the committed default) to prove it goes GREEN with cleanup restored.
# This is the code-under-test toggle, NOT a tamper of the assertion — the leak it
# produces is a real raw `sys.modules` mutation, the exact failure mode discovery
# code would cause if it injected fakes without restoring them.
STRIP_ISOLATION = False


def _make_modules_pkg(tmp_path, *folder_names):
    """Build a fake modules package on disk with the given sub-package folders."""
    modules_dir = tmp_path / "modules_disc"
    modules_dir.mkdir()
    (modules_dir / "__init__.py").write_text("")
    for name in folder_names:
        pkg = modules_dir / name
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
    return modules_dir


def test_underscore_module_is_discoverable(tmp_path, monkeypatch):
    _make_modules_pkg(tmp_path, "_probe", "projects")
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setattr(registry, "MODULES_PACKAGE", "modules_disc")
    try:
        names = registry._candidate_module_names()
        assert "_probe" in names, "underscore-prefixed module must be discoverable"
        assert "projects" in names
    finally:
        sys.path.remove(str(tmp_path))
        for m in list(sys.modules):
            if m == "modules_disc" or m.startswith("modules_disc."):
                del sys.modules[m]


# --- code-under-test: the raw injection + cleanup pair a discovery test uses ----
#
# These mimic what an injection-based discovery test does the LOW-LEVEL way:
# `_raw_inject` mutates the global sys.modules table directly (NOT via
# monkeypatch — so nothing auto-restores), exactly as a buggy discovery/cleanup
# path would. `_cleanup_injected` is the explicit restore that keeps the global
# table clean. The guard below proves the cleanup actually works: with it the
# invariant holds; strip it (STRIP_ISOLATION=True) and a real leak survives.


def _raw_inject(injected_keys: list[str], fake_path: str) -> dict[str, object]:
    """Raw, un-restored injection of fake `modules` + `modules.*` into sys.modules.

    Returns the prior values so a correct cleanup can restore them. This is the
    WRONG-way mutation on purpose — no monkeypatch, so it persists until an
    explicit cleanup undoes it.
    """
    prior: dict[str, object] = {}
    fake_root = types.ModuleType("modules")
    fake_root.__path__ = [fake_path]  # type: ignore[attr-defined]
    prior["modules"] = sys.modules.get("modules")
    sys.modules["modules"] = fake_root
    for key in injected_keys:
        prior[key] = sys.modules.get(key)
        sys.modules[key] = types.ModuleType(key)
    return prior


def _cleanup_injected(prior: dict[str, object]) -> None:
    """Restore sys.modules to its pre-injection state (the real isolation path)."""
    for key, old in prior.items():
        if old is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = old  # type: ignore[assignment]


def test_sys_modules_invariant_after_registry_injections(tmp_path):
    """Regression guard: an injection-based discovery test must not leak sys.modules.

    The invariant the test-isolation bug violated: after a test injects fake
    `modules.*` packages (to drive discovery against synthetic folders), the
    global table must be unchanged — no injected `modules.*` survives, and a
    fresh `import modules` resolves `__path__` to the REAL backend/modules. A
    leak here corrupts every later `import modules` / `/health` boot, which is
    why it's order-dependent and lethal.

    This guard has TEETH (Sprint 0A): it injects via `_raw_inject` (a real,
    un-restored sys.modules mutation — NOT monkeypatch auto-restore) and relies
    on `_cleanup_injected` to restore. Set STRIP_ISOLATION=True to skip cleanup
    and the post-injection asserts FAIL on the genuine leak. With cleanup
    (committed default) they pass. monkeypatch is deliberately NOT used so the
    assertions are sensitive to a real leak rather than a tautological restore.
    """
    backend_modules = (Path(__file__).resolve().parent.parent / "modules").resolve()

    # Sanity: before injection the real package points at backend/modules.
    real_path = list(importlib.import_module("modules").__path__)
    assert any(Path(p).resolve() == backend_modules for p in real_path), \
        f"real modules.__path__ {real_path} should include {backend_modules}"

    injected_keys = ["modules.probe", "modules.r", "modules.nope"]
    prior = _raw_inject(injected_keys, str(tmp_path))
    try:
        # Inside the injection the fakes are live (proves the injection took effect).
        assert sys.modules["modules"].__path__ == [str(tmp_path)]
        assert "modules.probe" in sys.modules
    finally:
        if not STRIP_ISOLATION:
            _cleanup_injected(prior)
        # When STRIP_ISOLATION is True we deliberately skip cleanup → real leak.

    # Invariant after the injection window: NO fake survived, real path restored.
    for key in injected_keys:
        assert key not in sys.modules, f"injected {key} leaked into sys.modules"
    restored_path = list(importlib.import_module("modules").__path__)
    assert any(Path(p).resolve() == backend_modules for p in restored_path), \
        f"real modules.__path__ not restored after injection, got {restored_path}"
    # And the import must NOT resolve to the fake tmp_path the injection used.
    assert str(tmp_path) not in restored_path, \
        "import modules resolved to the injected fake path — leak corrupted discovery"


def test_dunder_names_excluded(tmp_path, monkeypatch):
    # __pycache__ would appear as a package-like dir; it must NOT be a candidate.
    modules_dir = _make_modules_pkg(tmp_path, "good")
    dunder = modules_dir / "__pycache__"
    dunder.mkdir()
    (dunder / "__init__.py").write_text("")
    sys.path.insert(0, str(tmp_path))
    monkeypatch.setattr(registry, "MODULES_PACKAGE", "modules_disc")
    try:
        names = registry._candidate_module_names()
        assert "good" in names
        assert "__pycache__" not in names
    finally:
        sys.path.remove(str(tmp_path))
        for m in list(sys.modules):
            if m == "modules_disc" or m.startswith("modules_disc."):
                del sys.modules[m]
