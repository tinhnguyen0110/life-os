"""main.py — FastAPI app entry (ARCH §3, C4).

Wires the cross-cutting contracts:
  - C2: ``registry.mount_all(app)`` auto-discovers feature modules (zero today).
  - C4: ``/health`` returns the locked response shape ``{success, data, warning?}``.
  - C5: SQLite initialised + scheduler started on boot, both torn down on stop.

Adding a feature later = adding a folder under ``modules/``. This file is NOT
edited to register modules (ARCH §4).
"""

from __future__ import annotations

import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from core.config import settings
from core.registry import DiscoveryResult, mount_all
from core.responses import ok
from core.scheduler import SchedulerEngine
from store import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("life-os.main")

# Engine + discovery result live on app.state so endpoints/tests can read them.
scheduler = SchedulerEngine(enabled=settings.scheduler_enabled)

# MCP-HTTP: the 4 MCP servers mounted over streamable-http at distinct paths. A mounted
# Starlette sub-app's INTERNAL streamable_http_path is /mcp, so the client URL is
# <mount>/mcp (e.g. POST /mcp/read/mcp). Order is stable for the lifespan exit-stack.
_MCP_MOUNTS = [
    ("/mcp/read", "mcp_servers.read_server"),
    ("/mcp/write", "mcp_servers.write_server"),
    ("/mcp/wiki-read", "modules.wiki.mcp.read_server"),
    ("/mcp/wiki-write", "modules.wiki.mcp.write_server"),
]


def _build_mcp_servers() -> list:
    """Build the 4 FastMCP servers with DNS-rebinding protection OFF (single-user, no-auth,
    LAN — north-star) so REMOTE/multi-client streamable-http works (default ON → 421 on a
    non-localhost Host). Each via the server's own build_server(transport_security=...) so
    the capability gate + import graph stay pristine (no new import in the server modules).
    Returns the 4 FastMCP instances (session_manager exists only AFTER streamable_http_app)."""
    import importlib

    from mcp.server.transport_security import TransportSecuritySettings

    sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    servers = []
    for _path, mod_name in _MCP_MOUNTS:
        mod = importlib.import_module(mod_name)
        servers.append(mod.build_server(transport_security=sec))
    return servers


def create_app() -> FastAPI:
    """Application factory — used by uvicorn and by tests for isolation."""
    # MCP-HTTP: build the 4 FastMCP + their ASGI apps ONCE (session_manager.run() is
    # one-shot; never per-request). streamable_http_app() must be called BEFORE reading
    # .session_manager (lazy).
    mcp_servers = _build_mcp_servers()
    mcp_apps = [srv.streamable_http_app() for srv in mcp_servers]  # session_manager now exists

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
        # MCP-HTTP: a mounted Starlette sub-app's lifespan is NOT auto-run by FastAPI —
        # only the top-level lifespan runs. So enter each session_manager.run() HERE, or
        # every MCP call 500s. AsyncExitStack unwinds them on shutdown (LIFO) before the
        # scheduler/db teardown below.
        async with contextlib.AsyncExitStack() as stack:
            for srv in mcp_servers:
                await stack.enter_async_context(srv.session_manager.run())
            yield
        # --- shutdown --- (scheduler + db torn down AFTER the MCP managers unwind)
        scheduler.shutdown()
        db.close_db()

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

    @app.get("/", tags=["core"], include_in_schema=False)
    def root() -> RedirectResponse:
        """Friendly root entry — send browser visits to the built-in API docs."""
        return RedirectResponse(url="/docs", status_code=307)

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

    # MCP-HTTP: mount the 4 streamable-http ASGI apps at distinct paths. Built above
    # (session managers entered in the lifespan). Client hits <mount>/mcp. stdio main()
    # entrypoints are untouched — this is an ADDITIONAL transport, not a replacement.
    for (path, _mod_name), sub in zip(_MCP_MOUNTS, mcp_apps):
        app.mount(path, sub)
    return app


app = create_app()
