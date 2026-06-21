"""modules/mcp_keys/service.py — per-KEY MCP scoping store + CRUD (#86).

Settings-backed (md_store `settings/mcp_keys.md`, YAML front-matter, ONE git commit per write —
the settings/config.md pattern), but a SEPARATE file because keys are a LIST, not the singleton
config. Fail-OPEN read (absent/malformed → empty list, never 500), fail-CLOSED write (a persist
failure raises). NO new db/infra layer.

A key is a filter-SELECTOR (no-auth, single-user): ``get_key_scope(key)`` is the load-bearing
export #87's /mcp filter consumes — returns the key's ``{domains, tools}`` or None (None =
key-not-found → #87's agent-readable invalid-key error). An EMPTY scope returns ``{domains:[],
tools:[]}`` (a valid sees-nothing key), NOT None — that distinction is what #87 depends on.

DECIDED + logged (## Assumptions):
- scope validation = LENIENT/store-as-given (architect-leaned): a domain/tool not in the live
  catalog is stored as-is (forward-compat — a tool that later (dis)appears just changes the
  resolved count); #87 resolves against the catalog at filter-time. No hard-fail on an unknown name.
- key generation = ``secrets.token_urlsafe(24)`` — a selector, not a credential; never logged.
- ``toolCount`` (the list row) = the RESOLVED union size vs the LIVE catalog (domains-union ∪ tools),
  computed here so the UI/agent sees the effective count without re-resolving.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

import yaml

from store import md_store

from .schema import KeyRow, Scope

logger = logging.getLogger("life-os.mcp_keys.service")

MCP_KEYS_MD = "settings/mcp_keys.md"
_KEY_BYTES = 24  # secrets.token_urlsafe length seed (selector token, not a secret)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Persistence — md_store list (mirror settings/config.md, but a LIST)           #
# --------------------------------------------------------------------------- #
def _render(records: list[dict[str, Any]]) -> str:
    """records → ``---\\n keys: [...] \\n---\\n`` (YAML front-matter holding the list)."""
    block = yaml.safe_dump({"keys": records}, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n"


def _load() -> list[dict[str, Any]]:
    """Read the stored key records. Fail-OPEN: absent/malformed → [] (never 500)."""
    try:
        content = md_store.read(MCP_KEYS_MD)
    except Exception as exc:  # noqa: BLE001 — fail-open: a store-read error → empty, never crash
        logger.warning("mcp_keys read failed — treating as empty: %s", exc)
        return []
    if not content:
        return []
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return []
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        logger.warning("mcp_keys malformed — treating as empty: %s", exc)
        return []
    if not isinstance(data, dict):
        return []
    keys = data.get("keys")
    return keys if isinstance(keys, list) else []


def _save(records: list[dict[str, Any]]) -> None:
    """Persist the full list (ONE git commit). Fail-CLOSED: a write failure raises."""
    md_store.write_file(MCP_KEYS_MD, _render(records), "update mcp_keys")


# --------------------------------------------------------------------------- #
# toolCount resolution — the resolved union size vs the LIVE catalog            #
# --------------------------------------------------------------------------- #
def _resolve_tool_count(scope: Scope) -> int:
    """The size of (every tool whose mount ∈ scope.domains) ∪ (scope.tools that exist in the
    catalog). Fail-OPEN: if the catalog can't be read, fall back to the raw explicit-tool count
    (never crash the CRUD over a catalog hiccup)."""
    try:
        from mcp_servers.read_server import list_tools_catalog
        catalog = list_tools_catalog()
        tools = catalog.get("tools", []) or []
    except Exception as exc:  # noqa: BLE001 — catalog unavailable → degrade, don't crash CRUD
        logger.warning("mcp_keys: catalog unavailable for toolCount — raw fallback: %s", exc)
        return len(set(scope.tools))
    domains = set(scope.domains)
    explicit = set(scope.tools)
    catalog_names = {t.get("name") for t in tools}
    resolved: set[str] = set()
    for t in tools:
        name, server = t.get("name"), t.get("server")
        if server in domains:           # whole-domain inclusion
            resolved.add(name)
    for name in explicit:               # explicit tools that actually exist in the catalog
        if name in catalog_names:
            resolved.add(name)
    return len(resolved)


def _to_row(rec: dict[str, Any]) -> dict[str, Any]:
    """A stored record → the agent-readable KeyRow dict (adds the resolved toolCount)."""
    scope = Scope(**(rec.get("scope") or {}))
    return KeyRow(
        key=rec["key"], label=rec.get("label", ""), scope=scope,
        toolCount=_resolve_tool_count(scope), createdAt=rec.get("createdAt", ""),
    ).model_dump()


# --------------------------------------------------------------------------- #
# CRUD — the FROZEN exports (#87/#88 consume these)                             #
# --------------------------------------------------------------------------- #
def list_keys() -> list[dict[str, Any]]:
    """All keys as agent-readable rows (with resolved toolCount), newest-first."""
    records = _load()
    rows = [_to_row(r) for r in records]
    rows.sort(key=lambda r: r["createdAt"], reverse=True)  # newest-first
    return rows


def create_key(label: str, scope: Scope) -> dict[str, Any]:
    """Generate a new key (urlsafe selector token) + persist. Returns the agent-readable row
    (INCLUDING the generated ``key`` — the only time the full token is returned in a list-shape)."""
    records = _load()
    rec = {
        "key": secrets.token_urlsafe(_KEY_BYTES),
        "label": label,
        "scope": scope.model_dump(),
        "createdAt": _now_iso(),
    }
    records.append(rec)
    _save(records)
    return _to_row(rec)


def update_key(key: str, label: str | None = None, scope: Scope | None = None) -> dict[str, Any] | None:
    """Partial-update a key's label/scope. Returns the updated row, or None if no such key
    (→ router maps to the agent-readable NOT_FOUND). A None field is left unchanged."""
    records = _load()
    for rec in records:
        if rec.get("key") == key:
            if label is not None:
                rec["label"] = label
            if scope is not None:
                rec["scope"] = scope.model_dump()
            _save(records)
            return _to_row(rec)
    return None  # key not found


def delete_key(key: str) -> bool:
    """Remove a key. Returns True if removed, False if no such key (→ router NOT_FOUND)."""
    records = _load()
    remaining = [r for r in records if r.get("key") != key]
    if len(remaining) == len(records):
        return False  # nothing removed → key not found
    _save(remaining)
    return True


def get_key_scope(key: str) -> dict[str, Any] | None:
    """THE #87 gate: the key's ``{domains, tools}`` if it exists, else None.

    🔴 EMPTY scope returns ``{domains:[], tools:[]}`` (a VALID sees-nothing key) — NOT None. None
    means key-NOT-FOUND (#87 turns that into the agent-readable invalid-key error). This empty-vs-
    None distinction is the load-bearing contract #87 depends on."""
    for rec in _load():
        if rec.get("key") == key:
            scope = Scope(**(rec.get("scope") or {}))
            return scope.model_dump()  # {domains, tools} — empty lists if sees-nothing, never None
    return None  # key not found
