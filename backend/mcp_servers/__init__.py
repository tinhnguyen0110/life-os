"""mcp_servers — the WHOLE-APP MCP layer exposing life-os to external Claude Code (MCP-1).

The life-os vision: an external agent reads the user's life data (portfolio / market /
projects / Claude-usage / journals / brief …) over MCP, then analyses + advises. The
app itself stays LLM-free (life-os principle: the API is the source of truth; MCP just
exposes it; no embedded LLM).

This package holds the cross-module MCP servers. The first is the **read-server**
(``read_server``) — one read tool per module, each wrapping an EXISTING reader/service
read path and returning clean JSON. It mirrors the wiki MCP capability split:

  - READ-server here = ZERO write capability. It imports ONLY read fns; no module
    mutation (upsert/create/update/delete/set_*/sync/poll) is reachable in its module
    namespace. ``tests/test_mcp_read.py`` proves this structurally (namespace +
    AST-import), exactly like the wiki read-server's M4 gate. A write-server
    (propose-style, per module) is a SEPARATE later process, never bolted onto this one.

LOCATION (why a top-level ``mcp_servers/`` and NOT ``modules/mcp/``):
  - ``core/registry.py`` auto-discovers every PACKAGE under ``modules/`` as a FEATURE
    module and expects each to expose a ``MODULE: BaseModule`` (a mounted HTTP router).
    An MCP server is NOT a feature module — it has no router, nothing to mount — so a
    ``modules/mcp`` package would be flagged "skipped" at boot (tripping the /health
    no-skip gate). registry.py is contractually NOT to be edited to special-case a
    module, so the MCP layer lives OUTSIDE the ``modules/`` scan, as a sibling package.
  - It is NOT named ``mcp`` — a top-level ``mcp/`` at ``/app`` (on ``sys.path[0]``)
    would SHADOW the installed ``mcp`` SDK and break ``from mcp.server.fastmcp import
    FastMCP``. ``mcp_servers`` is a distinct top-level name, so ``import mcp`` (the SDK)
    still resolves. (The wiki servers nest under ``modules/wiki/mcp`` for the same
    anti-shadow reason — never a bare top-level ``mcp/``.)

Run a server:  ``python -m mcp_servers.read_server``  (stdio; registered in Claude
Code config).
"""
