"""main.py — FastAPI app entry (ARCH §3, C4).

Wires the cross-cutting contracts:
  - C2: ``registry.mount_all(app)`` auto-discovers feature modules (zero today).
  - C4: ``/health`` returns the locked response shape ``{success, data, warning?}``.
  - C5: SQLite initialised + scheduler started on boot, both torn down on stop.

Adding a feature later = adding a folder under ``modules/``. This file is NOT
edited to register modules (ARCH §4).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.registry import DiscoveryResult, mount_all
from core.responses import ok
from core.scheduler import SchedulerEngine
from store import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("life-os.main")

# Engine + discovery result live on app.state so endpoints/tests can read them.
scheduler = SchedulerEngine(enabled=settings.scheduler_enabled)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    db.init_db()
    discovery: DiscoveryResult = app.state.discovery
    scheduler.register_many(discovery.routines)
    scheduler.start()
    logger.info(
        "%s up — %d module(s), %d routine(s)",
        settings.app_name, len(discovery.mounted), len(discovery.routines),
    )
    yield
    # --- shutdown ---
    scheduler.shutdown()
    db.close_db()


def create_app() -> FastAPI:
    """Application factory — used by uvicorn and by tests for isolation."""
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    # CORS — let the browser FE (:3010) call the API. Single-user localhost
    # no-auth (CLAUDE.md §2): this enables browser fetch, it is NOT a security
    # boundary. Origins are configurable (LIFEOS_CORS_ORIGINS). Added before
    # mount_all so every mounted module's routes inherit the middleware.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["core"])
    def health() -> dict:
        """Liveness + discovery summary. Locked response shape (C4 via ok())."""
        discovery: DiscoveryResult = app.state.discovery
        return ok(
            data={
                "app": settings.app_name,
                "status": "ok",
                "modules": discovery.mounted,
                "routines": [r.id for r in discovery.routines],
            },
            warning=(f"{len(discovery.skipped)} module(s) skipped"
                     if discovery.skipped else None),
        )

    # C2: discover + mount BEFORE returning. Empty modules/ → mounts nothing.
    app.state.discovery = mount_all(app)
    return app


app = create_app()
