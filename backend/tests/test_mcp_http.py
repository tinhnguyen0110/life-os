"""tests/test_mcp_http.py — MCP-HTTP: the 4 MCP servers mounted over streamable-http
into the existing uvicorn (main.py), reachable for remote/multi-client.

Defensive cases (each a real assertion, per the dispatch):
(a) un-wired lifespan → 500 on every call → so we POST a REAL `initialize` and assert
    200 (NOT merely path!=404 — an un-run session manager answers 500, which a 404-only
    check passes right over). TestClient(app) as a context manager RUNS the lifespan.
(b) DNS-rebinding 421 → TestClient sends Host 'testserver' (non-localhost); without
    enable_dns_rebinding_protection=False the handshake 421s. We KEEP that Host (don't
    override to localhost) so a 200 proves the remote-client path this sprint exists to fix.
(c) 4 distinct managers → assert 4 distinct mcp-session-id values across the 4 mounts.
(d) stdio unbroken → each build_server() still builds + len(TOOLS) == 40/4/11/6
    (MCP-DEDUP #70: shared read 46→40, shared write 10→4, standalone wiki-read 9→11).
(e) no `from __future__ import annotations` added to the 4 server modules.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

import main


MOUNTS = ["/mcp/read", "/mcp/write", "/mcp/wiki-read", "/mcp/wiki-write"]


def _init_body():
    return {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}},
    }


@pytest.fixture
def client(isolated_paths):
    """A TestClient over a fresh app, entered as a context manager so the lifespan runs
    (DB + scheduler + the 4 MCP session managers). isolated_paths keeps the store tmp."""
    importlib.reload(main)
    app = main.create_app()
    with TestClient(app) as c:   # __enter__ runs the lifespan startup
        yield c


# --------------------------------------------------------------------------- #
# (a) + (b) + (c): the 4 handshakes return 200 (NOT 500/421/404) + distinct ids #
# --------------------------------------------------------------------------- #
def test_four_mcp_endpoints_handshake_200(client):
    """Each /<mount>/mcp `initialize` → 200 with an mcp-session-id. 200 (not 404) proves
    the session manager is RUN (a); 200 (not 421) proves DNS-rebinding is OFF for the
    non-localhost TestClient Host (b)."""
    session_ids = []
    for mount in MOUNTS:
        r = client.post(f"{mount}/mcp", json=_init_body(),
                        headers={"Accept": "application/json, text/event-stream"})
        assert r.status_code == 200, f"{mount}/mcp handshake not 200: {r.status_code} {r.text[:200]}"
        sid = r.headers.get("mcp-session-id")
        assert sid, f"{mount}/mcp returned no mcp-session-id"
        session_ids.append(sid)
    # (c) 4 mounts → 4 FastMCP → 4 session managers → 4 DISTINCT session ids (no collision)
    assert len(set(session_ids)) == 4, f"session ids collided: {session_ids}"


def test_json_only_accept_is_406_not_silently_ok(client):
    """ACCEPT GATE (gotcha #3, team-lead-flagged): the SDK requires
    `Accept: application/json, text/event-stream` on the initialize POST. A JSON-ONLY
    Accept must be REJECTED with 406 Not Acceptable, NOT silently accepted. This pins the
    negative so the curl example in MCP-CONFIG §3 can't false-negative — a JSON-only curl
    would get 406 against a perfectly working server, and a reader must know that's the
    header's fault, not a broken mount. (Same /mcp/read/mcp endpoint that 200s above with
    the correct Accept — so this isolates the Accept header as the sole difference.)"""
    r = client.post("/mcp/read/mcp", json=_init_body(),
                    headers={"Accept": "application/json"})  # missing text/event-stream
    assert r.status_code == 406, (
        f"a JSON-only Accept must 406 (the SDK needs text/event-stream too), got "
        f"{r.status_code}: {r.text[:200]}"
    )


def test_health_still_200_alongside_mounts(client):
    """The existing /health stays 200 (the MCP mounts don't shadow the core routes)."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_root_still_redirects(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307  # → /docs, unchanged


# --------------------------------------------------------------------------- #
# (d): stdio unbroken — build_server() still builds + the TOOLS counts hold     #
# --------------------------------------------------------------------------- #
def test_stdio_build_servers_unchanged():
    """Each server's build_server() still returns a FastMCP and the TOOLS counts hold
    (MCP-DEDUP #70: 40 read / 4 write / 11 wiki-read / 6 wiki-write) — stdio path intact.
    (shared read 46→40 and shared write 10→4 dropped the 6 duplicated wiki tools;
    standalone wiki-read 9→11 gained the 2 ported proposal-readback tools.)"""
    import mcp_servers.read_server as rs
    import mcp_servers.write_server as ws
    import modules.wiki.mcp.read_server as wrs
    import modules.wiki.mcp.write_server as wws

    # MCP-DEDUP #70: shared read 46→40 (−6 wiki), shared write 10→4 (−6 wiki_propose_*)
    assert len(rs.TOOLS) == 40
    assert len(ws.TOOLS) == 4
    # the 2 whole-app servers expose TOOLS; build each (default transport_security=None)
    for mod in (rs, ws):
        srv = mod.build_server()
        assert srv is not None and type(srv).__name__ == "FastMCP"
    # the wiki servers add tools explicitly — assert via the built server. MCP-DEDUP #70:
    # standalone wiki-read 9→11 (+wiki_proposal_status/wiki_list_proposals ported in); wiki-write 6.
    wr = wrs.build_server()
    ww = wws.build_server()
    assert wr is not None and ww is not None
    # tool counts on the wiki servers (the registered-tool count)
    assert len(wr._tool_manager.list_tools()) == 11
    assert len(ww._tool_manager.list_tools()) == 6


def test_build_server_default_is_stdio_identical():
    """build_server() with NO arg (stdio path) builds fine — the transport_security param
    defaults to None so the stdio main() entrypoints are behaviourally unchanged."""
    import mcp_servers.read_server as rs
    # both call forms work; default = None = stdio-identical
    assert rs.build_server() is not None
    assert rs.build_server(transport_security=None) is not None


# --------------------------------------------------------------------------- #
# (e): no `from __future__ import annotations` in the 4 server modules          #
# --------------------------------------------------------------------------- #
def test_no_future_annotations_in_server_modules():
    """FastMCP introspects REAL param annotations at registration (stringized annotations
    crash issubclass) — the 4 server modules must NOT add `from __future__ import
    annotations`. Checked via AST (a real ImportFrom node), NOT a substring — the modules
    legitimately MENTION the string in a docstring warning the reader not to add it."""
    import ast
    import inspect

    import mcp_servers.read_server as rs
    import mcp_servers.write_server as ws
    import modules.wiki.mcp.read_server as wrs
    import modules.wiki.mcp.write_server as wws

    for mod in (rs, ws, wrs, wws):
        tree = ast.parse(inspect.getsource(mod))
        future_imports = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) and n.module == "__future__"
            and any(a.name == "annotations" for a in n.names)
        ]
        assert not future_imports, \
            f"{mod.__name__} must NOT `from __future__ import annotations` (FastMCP introspection)"
