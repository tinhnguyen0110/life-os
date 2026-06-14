"""modules/wiki/mcp — MCP servers exposing the life-os wiki to external Claude Code (M4).

TWO servers, hard-separated by capability (spec L142/L145, the M4 security gate):
  - ``read_server`` (W4b) — wraps the wiki READ endpoints as MCP tools. ZERO write
    capability: it imports ONLY read fns + the audit appender, NEVER a mutation/
    enqueue fn. A confused-deputy / tool-poisoning attack can't escalate a read
    tool to a write because the write symbols are not in this module's import graph.
  - ``write_server`` (W4c, next) — separate module; propose_* tools that enqueue
    into the W4a proposal queue (never a direct vault write).

NAMING / LOCATION: nested under ``modules/wiki/`` (NOT a top-level ``mcp/`` at /app).
A top-level ``mcp/`` package would SHADOW the installed ``mcp`` SDK (``/app`` is on
sys.path[0]), breaking ``from mcp.server.fastmcp import FastMCP``. As a nested
sub-package the dotted path is ``modules.wiki.mcp`` — it never collides with the
top-level ``import mcp``. Entrypoint: ``python -m modules.wiki.mcp.read_server``.
"""
