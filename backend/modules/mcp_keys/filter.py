"""modules/mcp_keys/filter.py — the #87 key-aware tool filter (the 3 cases).

A client configs ONE /mcp endpoint + ONE optional key (header ``X-MCP-Key``); the server narrows
which tools that key sees. The 3 cases (user-decided, EXACT):
  1. NO key (absent / empty / whitespace) → ALL tools (default-open; the key is an OPTIONAL filter,
     NOT auth — single-user). Byte-identical to the no-filter behavior.
  2. VALID key → ONLY that key's scoped tools = resolve(get_key_scope(key)) ∩ the LIVE catalog.
  3. Key sent but INVALID/not-found (get_key_scope → None) → ``KeyNotFound`` raised → the transport
     layer returns the agent-readable error (code/message/hint/retryable).

🔴 store-lenient / filter-honest (the two-layer rule): the #86 STORE keeps an unknown scoped
domain/tool as-given (forward-compat); THIS FILTER is HONEST — it resolves against the LIVE catalog
and returns ONLY tools that ACTUALLY EXIST (a scoped tool no longer in the catalog is SKIPPED, no
phantom, no error — just fewer). empty-scope key → ZERO tools (valid sees-nothing; get_key_scope
returns {[],[]} NOT None).

This module is PURE (no HTTP): ``allowed_tool_names(key)`` returns the set of tool names a key may
see, or raises KeyNotFound. The ASGI wiring (main.py) reads the header into a ContextVar; each MCP
server's list_tools consults ``allowed_tool_names`` to filter. Pure → unit-testable without a server.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

from . import service

logger = logging.getLogger("life-os.mcp_keys.filter")

# Request-scoped key, set by the ASGI middleware (mcp_key_asgi_middleware) at the START of each
# /mcp request, BEFORE the FastMCP handler runs. list_tools (install_tool_filter) reads it. Default
# None = no-key = all tools. (asyncio context propagates synchronously from the middleware into the
# handler within the same request task; we verify on LIVE HTTP per verify-mcp-on-http-not-import-cache.)
_request_key: contextvars.ContextVar[str | None] = contextvars.ContextVar("mcp_request_key", default=None)

HEADER_NAME = "x-mcp-key"  # the key arrives as the X-MCP-Key request header (lower-cased by ASGI)


class KeyNotFound(Exception):
    """Raised when a non-empty key is sent but get_key_scope returns None (case 3). The transport
    turns this into the agent-readable error — never fail-open, never silently empty."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(f"mcp key not recognized: {_truncate(key)}")


def _truncate(key: str) -> str:
    """A short, non-secret-leaking key prefix for the error message (never echo the full token)."""
    return f"{key[:6]}…" if len(key) > 6 else key


def _normalize_key(key: str | None) -> str | None:
    """Case-1 defensive: absent / empty-string / whitespace-only → None (= NO key → all tools)."""
    if key is None:
        return None
    k = key.strip()
    return k or None


def _catalog_names_by_server() -> tuple[set[str], dict[str, set[str]]]:
    """The LIVE universe from read_server.list_tools_catalog(): (all tool names, names-by-mount).
    Fail-OPEN on a catalog hiccup → ({}, {}) (the caller then yields zero scoped tools, never crash;
    the no-key path doesn't call this at all)."""
    try:
        from mcp_servers.read_server import list_tools_catalog
        tools = list_tools_catalog().get("tools", []) or []
    except Exception as exc:  # noqa: BLE001 — catalog unavailable → degrade, don't crash the filter
        logger.warning("mcp_keys filter: catalog unavailable: %s", exc)
        return set(), {}
    all_names: set[str] = set()
    by_server: dict[str, set[str]] = {}
    for t in tools:
        name, server = t.get("name"), t.get("server")
        if name is None:
            continue
        all_names.add(name)
        by_server.setdefault(server, set()).add(name)
    return all_names, by_server


def resolve_scope(scope: dict) -> set[str]:
    """The filter-honest resolution: (every tool whose mount ∈ scope.domains) ∪ (scope.tools that
    ACTUALLY EXIST in the live catalog). A phantom scoped tool/domain is silently skipped (fewer
    tools, no error). Empty scope → empty set (sees nothing)."""
    all_names, by_server = _catalog_names_by_server()
    domains = set(scope.get("domains") or [])
    explicit = set(scope.get("tools") or [])
    resolved: set[str] = set()
    for server, names in by_server.items():
        if server in domains:
            resolved |= names                  # whole-domain inclusion (live names only)
    resolved |= (explicit & all_names)         # explicit tools that exist (phantoms skipped)
    return resolved


def allowed_tool_names(key: str | None) -> set[str] | None:
    """The 3-case decision for a request's key:
      - NO key (None/empty/whitespace) → return None = "no filter, ALL tools" (case 1).
      - VALID key → the resolved scoped tool-name set (∩ live catalog) (case 2). Empty-scope → set().
      - INVALID/not-found key → raise KeyNotFound (case 3).
    Returning None (all-tools) is DISTINCT from returning set() (a valid empty-scope key sees zero)."""
    norm = _normalize_key(key)
    if norm is None:
        return None  # case 1 — no filter, all tools (no-regression path)
    scope = service.get_key_scope(norm)
    if scope is None:
        raise KeyNotFound(norm)  # case 3 — sent-but-unknown → agent-readable error
    return resolve_scope(scope)  # case 2 — the scoped set (empty set = valid sees-nothing)


# --------------------------------------------------------------------------- #
# ASGI wiring — the chosen INJECTION POINT (logged to Assumptions):              #
#   key arrives as the X-MCP-Key HEADER (leaner than ?key=, not in the URL/logs);#
#   an ASGI middleware wrapping each MCP mount (a) reads the header into the      #
#   request-scoped ContextVar, (b) on case-3 (KeyNotFound) short-circuits with    #
#   the agent-readable JSON error BEFORE the request reaches FastMCP; (c) each     #
#   server's list_tools is overridden to filter by the ContextVar.                #
# --------------------------------------------------------------------------- #
def _error_asgi_response(exc: KeyNotFound) -> dict[str, Any]:
    """The agent-readable case-3 body (#87 user-flow in message+hint; code is enum-bound NOT_FOUND
    per team-lead's ruling — the agent-readability lives in message+hint, the code stays enum-valid)."""
    from core.agent_errors import agent_error
    return agent_error(
        "NOT_FOUND",
        f"the MCP key '{_truncate(exc.key)}' is not recognized",
        hint="ask the user to create/fix the key in the MCP-keys UI, or omit the key to get all tools",
    )


def mcp_key_asgi_middleware(app: Any) -> Any:
    """Wrap a mounted MCP ASGI sub-app: read X-MCP-Key → set the ContextVar for the request; if the
    key is sent-but-unknown (case 3), return the agent-readable NOT_FOUND JSON (HTTP 404) WITHOUT
    calling the sub-app (never reaches FastMCP). No-key / valid-key → pass through (the list_tools
    override does the case-1/case-2 filtering). Non-HTTP scopes (lifespan) pass straight through."""
    import json

    async def wrapped(scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)  # lifespan/websocket — untouched
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        raw_key = headers.get(HEADER_NAME)
        token = _request_key.set(_normalize_key(raw_key))
        try:
            norm = _normalize_key(raw_key)
            if norm is not None and service.get_key_scope(norm) is None:
                # case 3 — sent-but-unknown key: agent-readable error, do NOT reach FastMCP
                body = json.dumps(_error_asgi_response(KeyNotFound(norm))).encode()
                await send({"type": "http.response.start", "status": 404,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": body})
                return
            await app(scope, receive, send)  # case 1/2 — pass through; list_tools filters
        finally:
            _request_key.reset(token)

    return wrapped


def install_tool_filter(server: Any) -> None:
    """Override a FastMCP server's list_tools to return only the tools allowed for the request's key
    (read from the ContextVar). No-key (None) → ALL tools (case 1). A valid key → the scoped subset
    (case 2; empty-scope → zero). The case-3 error is handled earlier by the ASGI middleware, so by
    the time list_tools runs the key is either absent or valid."""
    original = server.list_tools

    async def _filtered():
        tools = await original()
        allowed = allowed_tool_names(_request_key.get())  # None=all (case1) | set (case2)
        if allowed is None:
            return tools  # case 1 — no key → all tools (byte-identical no-regression)
        return [t for t in tools if t.name in allowed]  # case 2 — scoped subset

    server.list_tools = _filtered
    # re-register the override on the low-level server (where the tools/list handler is bound).
    server._mcp_server.list_tools()(_filtered)
