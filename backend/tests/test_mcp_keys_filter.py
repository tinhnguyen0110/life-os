"""tests/test_mcp_keys_filter.py — the #87 key-aware tool filter (the 3 cases, PURE).

A client configs ONE /mcp endpoint + ONE optional X-MCP-Key; the server narrows which tools that
key sees. The 3 cases (user-decided): NO key → all · valid key → scoped subset · unknown key →
agent-readable error. store-lenient / filter-honest: an unknown scoped tool is SKIPPED (no phantom),
empty-scope sees nothing, nonexistent key raises.

These test the PURE filter (allowed_tool_names / resolve_scope) against the live catalog — the
HTTP wiring (ContextVar + middleware) is verified on the LIVE container (per verify-mcp-on-http-
not-import-cache; the streamable-http SSE flow can't be exercised in-process).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcp_servers.read_server import list_tools_catalog
from modules.mcp_keys import filter as filt
from modules.mcp_keys import service as svc
from modules.mcp_keys.schema import Scope


@pytest.fixture
def store(isolated_paths):
    return isolated_paths


def _finance_names() -> set[str]:
    return {t["name"] for t in list_tools_catalog()["tools"] if t["server"] == "finance"}


# --------------------------------------------------------------------------- #
# Case 1 — NO key → all tools (None = no filter)                                 #
# --------------------------------------------------------------------------- #
def test_case1_no_key_returns_none_all_tools(store):
    assert filt.allowed_tool_names(None) is None  # None = no filter, ALL tools


def test_case1_empty_and_whitespace_key_is_no_key(store):
    """Defensive: empty-string / whitespace key → treated as NO key (all tools), not an error."""
    assert filt.allowed_tool_names("") is None
    assert filt.allowed_tool_names("   ") is None


# --------------------------------------------------------------------------- #
# Case 2 — valid key → exactly its scoped tools (∩ live catalog)                 #
# --------------------------------------------------------------------------- #
def test_case2_domain_key_returns_exactly_that_domains_tools(store):
    k = svc.create_key("fin", Scope(domains=["finance"]))["key"]
    assert filt.allowed_tool_names(k) == _finance_names()  # exactly finance, nothing else


def test_case2_explicit_tools_key(store):
    """A key scoped to exactly 3 real tool names returns exactly those 3 (the teeth)."""
    names = list(_finance_names())[:3]
    k = svc.create_key("three", Scope(tools=names))["key"]
    assert filt.allowed_tool_names(k) == set(names)


def test_case2_union_domain_and_explicit(store):
    """scope = union(domain tools) ∪ explicit tools — both contribute, no double-count."""
    fin = _finance_names()
    # an explicit tool from a DIFFERENT mount + the whole finance domain
    other = next(t["name"] for t in list_tools_catalog()["tools"] if t["server"] != "finance")
    k = svc.create_key("u", Scope(domains=["finance"], tools=[other]))["key"]
    assert filt.allowed_tool_names(k) == fin | {other}


# --------------------------------------------------------------------------- #
# Case 3 — unknown key → KeyNotFound (agent-readable, NOT all-tools/empty)        #
# --------------------------------------------------------------------------- #
def test_case3_unknown_key_raises_keynotfound(store):
    with pytest.raises(filt.KeyNotFound):
        filt.allowed_tool_names("this-key-does-not-exist")


def test_case3_error_body_has_agent_readable_fields(store):
    """The case-3 ASGI error body carries code/message/hint/retryable (the user-flow in msg+hint)."""
    body = filt._error_asgi_response(filt.KeyNotFound("abcdef123456"))
    err = body["error"]
    assert err["code"] == "NOT_FOUND"
    assert "not recognized" in err["message"]
    assert "omit the key to get all tools" in err["hint"]
    assert err["retryable"] is False
    assert "abcdef123456" not in err["message"]  # token truncated, never echoed in full


# --------------------------------------------------------------------------- #
# store-lenient / filter-honest + empty-scope                                    #
# --------------------------------------------------------------------------- #
def test_filter_honest_phantom_tool_skipped(store):
    """A scoped tool NOT in the live catalog is SKIPPED (no phantom, no error) — only live tools."""
    real = list(_finance_names())[0]
    k = svc.create_key("ghost", Scope(tools=[real, "this_tool_was_removed"]))["key"]
    assert filt.allowed_tool_names(k) == {real}  # phantom dropped, real kept


def test_filter_honest_phantom_domain_skipped(store):
    """A scoped DOMAIN that doesn't exist contributes nothing (no error)."""
    k = svc.create_key("gd", Scope(domains=["no-such-mount"]))["key"]
    assert filt.allowed_tool_names(k) == set()


def test_empty_scope_key_sees_zero_not_none(store):
    """empty-scope key → set() (valid sees-nothing), DISTINCT from None (no-key = all tools)."""
    k = svc.create_key("empty", Scope())["key"]
    result = filt.allowed_tool_names(k)
    assert result == set()           # zero tools
    assert result is not None        # NOT the all-tools sentinel


def test_two_keys_two_different_sets(store):
    """Two keys with different scopes → two different tool sets."""
    k1 = svc.create_key("a", Scope(domains=["finance"]))["key"]
    k2 = svc.create_key("b", Scope(domains=["reminders"]))["key"]
    s1, s2 = filt.allowed_tool_names(k1), filt.allowed_tool_names(k2)
    assert s1 != s2 and s1 and s2     # both non-empty, distinct


# --------------------------------------------------------------------------- #
# resolve_scope (the pure resolver) directly                                     #
# --------------------------------------------------------------------------- #
def test_resolve_scope_empty_is_empty(store):
    assert filt.resolve_scope({"domains": [], "tools": []}) == set()


def test_normalize_key_strips(store):
    assert filt._normalize_key("  abc  ") == "abc"
    assert filt._normalize_key("") is None
    assert filt._normalize_key(None) is None


# --------------------------------------------------------------------------- #
# GET /mcp_keys/catalog — REST wrapper over list_tools_catalog (#87 fold-in)     #
# unblocks #88's scope-editor (the catalog was MCP-only). REST≡MCP byte-identical.#
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(store):
    from main import create_app
    return TestClient(create_app())


def test_catalog_route_is_byte_identical_to_mcp(client):
    """GET /mcp_keys/catalog → 200, data == the EXISTING list_tools_catalog() payload (REST≡MCP,
    same fn, no recompute)."""
    r = client.get("/mcp_keys/catalog")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data == list_tools_catalog()  # byte-identical to the MCP source


def test_catalog_has_tools_and_per_mount_counts(client):
    """The scope-editor needs tools[{name,server}] + the per-mount counts to tick on."""
    data = client.get("/mcp_keys/catalog").json()["data"]
    assert isinstance(data["tools"], list) and data["tools"]
    row = data["tools"][0]
    assert {"name", "server"} <= set(row)        # the UI ticks on server (domain) + name (tool)
    by_mount = data["counts"]["byMount"]
    assert isinstance(by_mount, dict) and sum(by_mount.values()) == len(data["tools"])


def test_catalog_route_not_shadowed_by_key_path(client):
    """The static /catalog path resolves to the catalog (NOT treated as a key) — a real key named
    'catalog' is impossible (keys are tokens), but pin that GET /catalog is the catalog route."""
    data = client.get("/mcp_keys/catalog").json()["data"]
    assert "tools" in data and "counts" in data  # the catalog shape, not a key row / 404
