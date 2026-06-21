"""tests/test_mcp_http.py — MCP-HTTP: the 7 MCP servers mounted over streamable-http
into the existing uvicorn (main.py), reachable for remote/multi-client.

The mounts: shared read/write + standalone wiki-read/wiki-write + the per-domain finance (#28-T1
precedent), reminders (#28), and tracing (#65) servers. MOUNTS below MUST stay in sync with
main._MCP_MOUNTS (a test pins that) so the handshake/stateless tests exercise EVERY live mount —
a mount added to main.py but not here would silently lose its live-HTTP coverage (the count-gotcha's
sibling: DAILY-TRACING-P2 closed the reminders+tracing gap the comment already claimed).

Defensive cases (each a real assertion, per the dispatch):
(a) un-wired lifespan → 500 on every call → so we POST a REAL `initialize` and assert
    200 (NOT merely path!=404 — an un-run session manager answers 500, which a 404-only
    check passes right over). TestClient(app) as a context manager RUNS the lifespan.
(b) DNS-rebinding 421 → TestClient sends Host 'testserver' (non-localhost); without
    enable_dns_rebinding_protection=False the handshake 421s. We KEEP that Host (don't
    override to localhost) so a 200 proves the remote-client path this sprint exists to fix.
(c) MCP-STATELESS (#75): the mounts are stateless_http=True → the handshake issues NO
    mcp-session-id (no per-session state) so a backend RESTART can't drop a client; a
    tools/list works with NO prior initialize-session (restart-survivable). (Was: distinct
    session ids — stateful; the agent-first switch removed sessions entirely.)
(d) stdio unbroken → each build_server() still builds + the per-server tool counts hold (asserted
    live below — shared read/write + standalone wiki-read 15 (#23/#34/#41/#53/#35) / wiki-write 8 (#94) /
    finance subset 15). Historical: MCP-DEDUP #70 shared read 46→40, write 10→4, wiki-read 9→11.
(e) no `from __future__ import annotations` added to the server modules.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

import main


# DAILY-TRACING-P2 (#65): all 7 live mounts (must match main._MCP_MOUNTS). reminders + tracing were
# missing — the handshake/stateless tests now exercise EVERY mount (the per-domain-mount coverage the
# comment above already claimed). Keep in sync with _MCP_MOUNTS when a mount is added.
MOUNTS = ["/mcp/read", "/mcp/write", "/mcp/wiki-read", "/mcp/wiki-write", "/mcp/finance",
          "/mcp/reminders", "/mcp/tracing"]


def _init_body():
    return {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}},
    }


@pytest.fixture
def client(isolated_paths, monkeypatch):
    """A TestClient over a fresh app, entered as a context manager so the lifespan runs
    (DB + scheduler + the MCP session managers). isolated_paths keeps the store tmp.

    SUITE-REFACTOR (#73): conftest sets LIFEOS_SKIP_MCP_MOUNTS=1 suite-wide (the REST tests don't
    need MCP). THIS file DOES test the MCP mounts → delete the flag so create_app builds them."""
    monkeypatch.delenv("LIFEOS_SKIP_MCP_MOUNTS", raising=False)
    importlib.reload(main)
    app = main.create_app()
    with TestClient(app) as c:   # __enter__ runs the lifespan startup
        yield c


# --------------------------------------------------------------------------- #
# (a) + (b) + (c): the 4 handshakes return 200 (NOT 500/421/404) + distinct ids #
# --------------------------------------------------------------------------- #
def test_all_mcp_endpoints_handshake_200(client):
    """Each /<mount>/mcp `initialize` → 200 (all 7 live mounts incl. the per-domain finance/
    reminders/tracing). 200 (not 404) proves the session manager is
    RUN (a); 200 (not 421) proves DNS-rebinding is OFF for the non-localhost TestClient
    Host (b). MCP-STATELESS (#75): the servers are stateless_http=True now, so the
    handshake issues NO mcp-session-id (no session to track) — that is the agent-first WIN
    (a backend restart can't drop a session that doesn't exist). See the dedicated
    stateless test below for the no-session-id assertion."""
    for mount in MOUNTS:
        r = client.post(f"{mount}/mcp", json=_init_body(),
                        headers={"Accept": "application/json, text/event-stream"})
        assert r.status_code == 200, f"{mount}/mcp handshake not 200: {r.status_code} {r.text[:200]}"


def test_MOUNTS_in_sync_with_main_mcp_mounts():
    """DAILY-TRACING-P2 (#65) — the structural fix for the stale-MOUNTS gap (a mount added to
    main._MCP_MOUNTS but not to this test's MOUNTS silently loses its handshake/stateless coverage).
    Pin MOUNTS == the live _MCP_MOUNTS paths so the handshake + stateless tests above ALWAYS exercise
    EVERY live mount — adding a future mount without updating MOUNTS now fails HERE, not silently."""
    live = [path for path, _mod in main._MCP_MOUNTS]
    assert set(MOUNTS) == set(live), (
        f"MOUNTS out of sync with main._MCP_MOUNTS — missing {set(live) - set(MOUNTS)}, "
        f"stale {set(MOUNTS) - set(live)}")


def test_stateless_handshake_issues_no_session_id(client):
    """MCP-STATELESS (#75) — the spine: a stateless server holds NO per-session state, so
    the `initialize` handshake returns NO mcp-session-id header. THIS is what makes a backend
    RESTART non-disruptive — there's no session id a client would have to re-initialize after
    the server comes back. (Stateful mode issued one per mount; stateless issues none.)"""
    for mount in MOUNTS:
        r = client.post(f"{mount}/mcp", json=_init_body(),
                        headers={"Accept": "application/json, text/event-stream"})
        assert r.status_code == 200
        assert r.headers.get("mcp-session-id") is None, (
            f"{mount}/mcp issued an mcp-session-id — not stateless "
            f"(a session id means a restart could orphan the client)")


def test_stateless_call_needs_no_prior_session(client):
    """RESTART-SURVIVABLE behavior: a stateless server accepts a tools/list with NO
    mcp-session-id header and NO prior initialize-session — i.e. a client that was
    connected before a restart keeps working without re-initializing. (In stateful mode
    a call without the session id from initialize would 400/404; stateless serves it.)"""
    r = client.post("/mcp/read/mcp",
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    headers={"Accept": "application/json, text/event-stream"})
    # 200 = served without a session handshake (the restart-survivable property). Not a
    # 4xx "missing session id" the stateful server would have returned.
    assert r.status_code == 200, (
        f"stateless tools/list without a session must 200 (restart-survivable), got "
        f"{r.status_code}: {r.text[:200]}")


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
    (MCP-DEDUP #70: 40 read / 4 write / 11 wiki-read / 6 wiki-write; MCP-DOMAINS T1:
    15 finance) — stdio path intact. (shared read 46→40 and shared write 10→4 dropped the
    6 duplicated wiki tools; standalone wiki-read 9→11 gained the 2 ported proposal-readback
    tools; finance is a 15-tool subset of read — ADDITIVE, read itself unchanged at 40.)"""
    import mcp_servers.finance_server as fs
    import mcp_servers.read_server as rs
    import mcp_servers.write_server as ws
    import modules.wiki.mcp.read_server as wrs
    import modules.wiki.mcp.write_server as wws

    # MCP-DEDUP #70: shared read 46→40 (−6 wiki), shared write 10→4 (−6 wiki_propose_*)
    assert len(rs.TOOLS) == 46  # REPO-MEMORY-P2 #64: +repo_memory (was 45; #64-P1 +code_insight)
    assert len(ws.TOOLS) == 4
    # MCP-DOMAINS T1: finance subset = 15 (ADDITIVE — read above unchanged by the finance subset)
    assert len(fs.TOOLS) == 15
    # the whole-app servers expose TOOLS; build each (default transport_security=None)
    for mod in (rs, ws, fs):
        srv = mod.build_server()
        assert srv is not None and type(srv).__name__ == "FastMCP"
    # the wiki servers add tools explicitly — assert via the built server. MCP-DEDUP #70:
    # standalone wiki-read 9→11 (+wiki_proposal_status/wiki_list_proposals ported in); wiki-write 6.
    # WIKI-LINK-CORRECTNESS #19: wiki-read 11→12 (+wiki_tree, the MCP mirror of REST /wiki/tree).
    # WIKI-RETRIEVAL-3 #23 (F1=b): wiki-read 12→11 (+wiki_context, −wiki_graph −wiki_backlinks;
    # wiki_context supersets the two removed granular tools → net −1).
    # WIKI-SUGGEST-LINK #34: wiki-read 11→12 (+wiki_suggest_links).
    # WIKI-STALE-DETECTOR #41: wiki-read 12→13 (+wiki_stale).
    # WIKI-RECONCILE #53: wiki-read 13→14 (+wiki_reindex).
    # WIKI-WRITE-FEEDBACK #35: wiki-read 14→15 (+wiki_my_feedback).
    wr = wrs.build_server()
    ww = wws.build_server()
    assert wr is not None and ww is not None
    # tool counts on the wiki servers (the registered-tool count)
    assert len(wr._tool_manager.list_tools()) == 15
    assert len(ww._tool_manager.list_tools()) == 8  # #94: +wiki_delete_note +wiki_restore_note (was 6)


def test_build_server_default_is_stdio_identical():
    """build_server() with NO arg (stdio path) builds fine — the transport_security param
    defaults to None so the stdio main() entrypoints are behaviourally unchanged."""
    import mcp_servers.read_server as rs
    # both call forms work; default = None = stdio-identical
    assert rs.build_server() is not None
    assert rs.build_server(transport_security=None) is not None


# --------------------------------------------------------------------------- #
# (e): no `from __future__ import annotations` in the server modules             #
# --------------------------------------------------------------------------- #
def test_no_future_annotations_in_server_modules():
    """FastMCP introspects REAL param annotations at registration (stringized annotations
    crash issubclass) — the server modules must NOT add `from __future__ import
    annotations`. Checked via AST (a real ImportFrom node), NOT a substring — the modules
    legitimately MENTION the string in a docstring warning the reader not to add it.
    (reminders_server + tracing_server have the same AST check in their own test files.)"""
    import ast
    import inspect

    import mcp_servers.finance_server as fs
    import mcp_servers.read_server as rs
    import mcp_servers.write_server as ws
    import modules.wiki.mcp.read_server as wrs
    import modules.wiki.mcp.write_server as wws

    for mod in (rs, ws, wrs, wws, fs):
        tree = ast.parse(inspect.getsource(mod))
        future_imports = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) and n.module == "__future__"
            and any(a.name == "annotations" for a in n.names)
        ]
        assert not future_imports, \
            f"{mod.__name__} must NOT `from __future__ import annotations` (FastMCP introspection)"
