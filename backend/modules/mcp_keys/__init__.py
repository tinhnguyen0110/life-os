"""modules/mcp_keys — per-KEY MCP tool-scoping (#86, parent #6).

A client configures ONE MCP endpoint + ONE key; the SERVER narrows which tools that key sees
to its ``scope`` (the UNION of whole DOMAINS + explicit TOOLS). #86 is the GATING store + CRUD;
#87 (the /mcp key-aware filter, via ``service.get_key_scope``) + #88 (the UI) consume it.

Settings-backed (md_store `settings/mcp_keys.md`, one git commit per write). Key = a filter-
SELECTOR (single-user, no-auth — NOT a secret credential). The router auto-mounts at ``/mcp_keys``.
"""

from .router import MODULE

__all__ = ["MODULE"]
