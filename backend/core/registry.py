"""core/registry.py — module auto-discovery & mounting (C2, decide-log D1).

THE core "easy-to-extend" contract (ARCH §4): scan ``modules/`` for packages
exposing a ``MODULE: BaseModule`` instance, mount each router at ``/{name}``, and
collect every module's ``routines()`` for the scheduler.

**Adding a module = adding a folder under modules/. Never edit this file or
main.py to register a new module.**

Discovery mechanism (D1):
  - ``pkgutil.iter_modules`` over the ``modules`` package (NOT a manual list).
  - For each sub-package, look for attribute ``MODULE`` in ``modules/<name>/``
    (its ``__init__``) first, else in ``modules/<name>/router.py``.

Defensive contract (Sprint 0 plan §Defensive):
  - Empty ``modules/`` dir → mount nothing, no error.
  - A module missing ``MODULE`` / with a bad ``name`` / that raises on import →
    logged and SKIPPED. One broken module never crashes the whole app.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field

from fastapi import FastAPI

from core.base import BaseModule, Routine

logger = logging.getLogger("life-os.registry")

# Where feature modules live, as an importable package path.
MODULES_PACKAGE = "modules"
# Attribute a module package must expose.
MODULE_ATTR = "MODULE"


@dataclass
class DiscoveryResult:
    """Outcome of a mount_all() pass — returned so callers/tests can inspect it."""

    mounted: list[str] = field(default_factory=list)        # module names mounted
    routines: list[Routine] = field(default_factory=list)   # all collected routines
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)


def _candidate_module_names() -> list[str]:
    """List sub-package names under the modules package. Empty/absent → []."""
    try:
        pkg = importlib.import_module(MODULES_PACKAGE)
    except ModuleNotFoundError:
        logger.warning("modules package %r not importable — mounting nothing", MODULES_PACKAGE)
        return []
    search_paths = getattr(pkg, "__path__", None)
    if not search_paths:
        return []
    names: list[str] = []
    for info in pkgutil.iter_modules(search_paths):
        # Only packages (folders) are modules; skip stray top-level .py files
        # and dunder names like ``__pycache__``. NOTE: only ``__`` is excluded,
        # NOT a single leading ``_`` — the documented convention probe is named
        # ``_probe`` and underscore-prefixed module names are legal.
        if info.ispkg and not info.name.startswith("__"):
            names.append(info.name)
    return sorted(names)


def _load_module(name: str) -> BaseModule:
    """Import ``modules/<name>`` and return its MODULE instance.

    Looks in the package ``__init__`` first, then ``<name>.router``. Raises a
    descriptive error if not found / wrong type — caller decides to skip.
    """
    pkg_path = f"{MODULES_PACKAGE}.{name}"
    pkg = importlib.import_module(pkg_path)
    candidate = getattr(pkg, MODULE_ATTR, None)
    if candidate is None:
        # Fall back to the router submodule.
        try:
            router_mod = importlib.import_module(f"{pkg_path}.router")
        except ModuleNotFoundError as exc:
            raise AttributeError(
                f"module {name!r} exposes no {MODULE_ATTR} in __init__ and has no router.py"
            ) from exc
        candidate = getattr(router_mod, MODULE_ATTR, None)
    if candidate is None:
        raise AttributeError(
            f"module {name!r} exposes no {MODULE_ATTR} (looked in __init__ and router.py)"
        )
    if not isinstance(candidate, BaseModule):
        raise TypeError(
            f"module {name!r} {MODULE_ATTR} must be a BaseModule, got {type(candidate).__name__}"
        )
    return candidate


def mount_all(app: FastAPI) -> DiscoveryResult:
    """Discover, mount, and collect routines for every module. Fail-open per module.

    Returns a DiscoveryResult so main.py can store routines and tests can assert
    exactly what mounted/skipped. A single failing module is recorded in
    ``skipped`` and does not abort the whole scan.
    """
    result = DiscoveryResult()
    for name in _candidate_module_names():
        try:
            module = _load_module(name)
        except Exception as exc:  # broad on purpose: one bad module must not crash boot
            logger.error("skipping module %r: %s", name, exc)
            result.skipped.append((name, str(exc)))
            continue

        # The mount prefix is derived from the module's declared name, not the
        # folder, so a mismatch is the module's own contract to keep.
        prefix = f"/{module.name}"
        try:
            app.include_router(module.router, prefix=prefix)
        except Exception as exc:  # defensive: malformed router
            logger.error("skipping module %r: include_router failed: %s", name, exc)
            result.skipped.append((name, f"include_router failed: {exc}"))
            continue

        try:
            module_routines = module.routines()
        except Exception as exc:  # a broken routines() must not unmount the router
            logger.error("module %r routines() raised, ignoring routines: %s", name, exc)
            module_routines = []

        result.mounted.append(module.name)
        result.routines.extend(module_routines)
        logger.info(
            "mounted module %r at %s (%d routine(s))",
            module.name, prefix, len(module_routines),
        )

    if not result.mounted:
        logger.info("registry: no feature modules discovered (empty modules/ is OK)")
    return result
