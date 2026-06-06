"""core/scheduler.py — APScheduler engine (ARCH §3/§10).

Wraps a single ``BackgroundScheduler`` and registers the ``Routine`` objects the
registry collected from modules. Rule-based jobs only (poll/idle/pattern/nudge) —
no AI. Single-user, local process; the background scheduler runs in-thread.

Lifecycle: ``main.py`` creates one Engine, calls ``register_many(routines)`` then
``start()`` on app startup, and ``shutdown()`` on app stop.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from core.base import Routine

logger = logging.getLogger("life-os.scheduler")

# Map our Routine.trigger string -> APScheduler trigger name (they happen to
# match today, but this indirection documents the contract).
_TRIGGER_MAP = {"interval": "interval", "cron": "cron", "date": "date"}


class SchedulerEngine:
    """Thin wrapper around APScheduler's BackgroundScheduler.

    Args:
        enabled: when False, register_many/start are no-ops (test/CI mode).
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._scheduler = BackgroundScheduler()
        self._registered: dict[str, Routine] = {}

    def register(self, routine: Routine) -> bool:
        """Register one routine. Returns True if added, False if skipped.

        Duplicate ids and disabled routines are skipped (logged). A routine whose
        trigger args are malformed is skipped rather than crashing registration.
        """
        if routine.id in self._registered:
            logger.warning("routine %r already registered — skipping duplicate", routine.id)
            return False
        if not routine.enabled:
            logger.info("routine %r disabled — not scheduling", routine.id)
            self._registered[routine.id] = routine
            return False
        trigger = _TRIGGER_MAP.get(routine.trigger)
        if trigger is None:  # pragma: no cover - Routine.__post_init__ guards this
            logger.error("routine %r unknown trigger %r — skipping", routine.id, routine.trigger)
            return False
        try:
            self._scheduler.add_job(
                routine.func,
                trigger=trigger,
                id=routine.id,
                name=routine.name,
                replace_existing=True,
                **routine.trigger_args,
            )
        except Exception as exc:  # bad trigger_args, etc. — never crash boot
            logger.error("failed to schedule routine %r: %s", routine.id, exc)
            return False
        self._registered[routine.id] = routine
        logger.info(
            "scheduled routine %r (%s %s)", routine.id, routine.trigger, routine.trigger_args
        )
        return True

    def register_many(self, routines: list[Routine]) -> int:
        """Register a batch; returns how many were actually scheduled."""
        return sum(1 for r in routines if self.register(r))

    @property
    def routines(self) -> list[Routine]:
        """All registered routines (enabled or not), for the automation API."""
        return list(self._registered.values())

    def start(self) -> None:
        if not self.enabled:
            logger.info("scheduler disabled — not starting")
            return
        if self._scheduler.running:
            return
        self._scheduler.start()
        logger.info("scheduler started with %d job(s)", len(self._scheduler.get_jobs()))

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("scheduler shut down")
