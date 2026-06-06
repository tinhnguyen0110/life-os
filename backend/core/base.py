"""core/base.py — BaseModule contract (C1).

The single most important contract in the codebase: every feature module plugs
into core through this interface, and **adding a module = adding a folder under
``modules/`` — never editing core/ or main.py** (ARCH §4).

Discovery convention (enforced by core/registry.py):
---------------------------------------------------
A module is a package ``backend/modules/<name>/`` that exposes a module-level
attribute named ``MODULE`` bound to a ``BaseModule`` instance. The registry looks
for ``MODULE`` first in ``modules/<name>/__init__.py``, then in
``modules/<name>/router.py``.

Minimal module:

    # modules/notes/router.py
    from fastapi import APIRouter
    from core.base import BaseModule

    router = APIRouter()

    @router.get("")
    def list_notes():
        return {"success": True, "data": []}

    MODULE = BaseModule(name="notes", router=router)

The registry mounts ``module.router`` at ``/{module.name}`` and collects
``module.routines()`` into the scheduler. ``name`` MUST be URL-safe and unique.

To change the convention (attr name / lookup location), edit this docstring AND
``core/registry.py`` together — they are the two sides of the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from fastapi import APIRouter


@dataclass
class Routine:
    """A rule-based scheduled job a module hands to the scheduler (ARCH §10).

    No AI — pure rules (poll price, check idle days, pattern-match, nudge).

    Attributes:
        id:        Stable unique id, e.g. ``"market-poll"``. Used by the
                   automation module's ``PATCH /routines/{id}`` and run_log.
        func:      Zero-arg callable the scheduler invokes. Should be cheap to
                   import and must not block the event loop for long.
        trigger:   APScheduler trigger type: ``"interval"`` | ``"cron"`` | ``"date"``.
        trigger_args: kwargs passed to the trigger (e.g. ``{"minutes": 5}`` or
                   ``{"hour": 8}``). Empty → caller/scheduler supplies a default.
        name:      Human-readable label (defaults to ``id``).
        enabled:   If False the scheduler registers it paused (toggle via API).
    """

    id: str
    func: Callable[[], object]
    trigger: str = "interval"
    trigger_args: dict = field(default_factory=dict)
    name: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Routine.id must be a non-empty string")
        if self.trigger not in ("interval", "cron", "date"):
            raise ValueError(
                f"Routine.trigger must be 'interval'|'cron'|'date', got {self.trigger!r}"
            )
        if not callable(self.func):
            raise ValueError(f"Routine.func for {self.id!r} must be callable")
        if not self.name:
            self.name = self.id


class BaseModule:
    """Hợp đồng chung — the interface every feature module implements (ARCH §4).

    A module is constructed with a ``name`` (its URL prefix) and a ``router``
    (its REST endpoints). Optionally it overrides/supplies ``routines()`` to hand
    rule-based jobs to the scheduler.

    Subclassing is allowed for modules that want richer ``routines()`` logic, but
    the plain instance form ``BaseModule(name=..., router=...)`` is sufficient for
    read-only modules. The registry only depends on the three public members:
    ``name`` (str), ``router`` (APIRouter), ``routines()`` (-> list[Routine]).
    """

    def __init__(
        self,
        name: str,
        router: APIRouter,
        routines: list[Routine] | None = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("BaseModule.name must be a non-empty string")
        if "/" in name or " " in name:
            raise ValueError(
                f"BaseModule.name must be URL-safe (no '/' or spaces), got {name!r}"
            )
        if not isinstance(router, APIRouter):
            raise TypeError(
                f"BaseModule.router must be a FastAPI APIRouter, got {type(router).__name__}"
            )
        self.name = name.strip()
        self.router = router
        self._routines = routines or []

    def routines(self) -> list[Routine]:
        """Routines this module contributes to the scheduler. Default: none."""
        return list(self._routines)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<BaseModule name={self.name!r} routines={len(self._routines)}>"
