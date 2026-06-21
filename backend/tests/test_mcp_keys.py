"""tests/test_mcp_keys.py — per-KEY MCP tool-scoping store + CRUD (#86).

A KEY narrows which MCP tools a client sees (scope = union of domains + tools). #86 is the
GATING store+CRUD; #87 (the /mcp filter) consumes get_key_scope. The load-bearing distinction:
an EMPTY-scope key returns {domains:[],tools:[]} (a valid sees-nothing key), a NONEXISTENT key
returns None (the #87 invalid-key signal) — both proven here.

BEHAVIOR-TESTED: drive CRUD through the real md_store (isolated tmp) + assert value-by-value;
read the persisted state back (not field-reads).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from modules.mcp_keys import service as svc
from modules.mcp_keys.schema import Scope


@pytest.fixture
def store(isolated_paths):
    """isolated_paths gives a fresh tmp data_dir → mcp_keys.md is empty per test."""
    return isolated_paths


@pytest.fixture
def client(store):
    from main import create_app
    return TestClient(create_app())


# --------------------------------------------------------------------------- #
# Service CRUD — value-by-value                                                  #
# --------------------------------------------------------------------------- #
def test_create_returns_key_and_row(store):
    row = svc.create_key("agent A", Scope(domains=["finance"], tools=["wiki_search"]))
    assert row["key"]                       # a generated selector token
    assert row["label"] == "agent A"
    assert row["scope"] == {"domains": ["finance"], "tools": ["wiki_search"]}
    assert isinstance(row["toolCount"], int) and row["toolCount"] >= 1  # resolved union size
    assert row["createdAt"]                 # ISO ts


def test_list_then_get_then_update_then_delete_roundtrip(store):
    created = svc.create_key("rt", Scope(domains=["read"]))
    k = created["key"]
    # LIST
    rows = svc.list_keys()
    assert len(rows) == 1 and rows[0]["key"] == k
    # GET scope
    assert svc.get_key_scope(k) == {"domains": ["read"], "tools": []}
    # UPDATE
    upd = svc.update_key(k, label="rt2", scope=Scope(domains=["read"], tools=["daily_brief"]))
    assert upd["label"] == "rt2"
    assert upd["scope"] == {"domains": ["read"], "tools": ["daily_brief"]}
    assert svc.get_key_scope(k) == {"domains": ["read"], "tools": ["daily_brief"]}
    # DELETE
    assert svc.delete_key(k) is True
    assert svc.list_keys() == []
    assert svc.get_key_scope(k) is None     # gone


def test_update_partial_label_only_keeps_scope(store):
    k = svc.create_key("p", Scope(domains=["wiki-read"]))["key"]
    upd = svc.update_key(k, label="renamed")  # scope=None → unchanged
    assert upd["label"] == "renamed"
    assert upd["scope"] == {"domains": ["wiki-read"], "tools": []}  # preserved


# --------------------------------------------------------------------------- #
# THE distinguishing case — empty-scope key ≠ no key (the #87 contract)          #
# --------------------------------------------------------------------------- #
def test_empty_scope_key_returns_empty_lists_not_none(store):
    """A key with scope {domains:[],tools:[]} is a VALID sees-nothing key → get_key_scope returns
    {domains:[],tools:[]}, NOT None. This is what #87 distinguishes from key-not-found."""
    k = svc.create_key("sees nothing", Scope())["key"]
    assert svc.get_key_scope(k) == {"domains": [], "tools": []}  # valid, empty — NOT None


def test_nonexistent_key_returns_none(store):
    """A key that does not exist → None (the #87 invalid-key signal). Distinct from empty-scope."""
    assert svc.get_key_scope("definitely-not-a-real-key") is None


def test_empty_scope_toolcount_is_zero(store):
    """An empty-scope key resolves to 0 tools (sees nothing) — toolCount == 0."""
    row = svc.create_key("nothing", Scope())
    assert row["toolCount"] == 0


# --------------------------------------------------------------------------- #
# toolCount resolution — union of domains + explicit tools vs the live catalog   #
# --------------------------------------------------------------------------- #
def test_toolcount_resolves_domain_union(store):
    """toolCount = the resolved union size. A whole-domain scope counts that mount's tools; an
    explicit tool ALREADY in the domain is not double-counted (set union)."""
    from mcp_servers.read_server import list_tools_catalog
    catalog = list_tools_catalog()
    finance_tools = [t["name"] for t in catalog["tools"] if t["server"] == "finance"]
    assert finance_tools, "fixture sanity: finance mount should have tools"
    # domain=finance + an explicit finance tool (already in the domain) → no double-count
    row = svc.create_key("fin", Scope(domains=["finance"], tools=[finance_tools[0]]))
    assert row["toolCount"] == len(set(finance_tools))  # union == the domain's tools, not +1


def test_toolcount_unknown_tool_not_counted(store):
    """An explicit tool NOT in the catalog is stored (forward-compat) but does NOT inflate
    toolCount (lenient resolution — it just yields fewer effective tools)."""
    row = svc.create_key("ghost", Scope(tools=["this_tool_does_not_exist"]))
    assert row["toolCount"] == 0
    # but it IS stored as-given (forward-compat, not hard-failed)
    assert svc.get_key_scope(row["key"]) == {"domains": [], "tools": ["this_tool_does_not_exist"]}


# --------------------------------------------------------------------------- #
# Persistence — survives a fresh service read (md_store round-trip)              #
# --------------------------------------------------------------------------- #
def test_persists_across_fresh_read(store):
    """The key is written to md_store → a fresh _load() (simulating a restart) sees it. Proves
    the settings-backed persistence (one git commit), not just in-memory."""
    k = svc.create_key("persist", Scope(domains=["read"]))["key"]
    # a fresh read straight from the store (no in-memory cache — service is stateless)
    reloaded = svc.get_key_scope(k)
    assert reloaded == {"domains": ["read"], "tools": []}
    # and the md file exists on disk
    from store import md_store
    assert md_store.read(svc.MCP_KEYS_MD) is not None


def test_load_failopen_empty_when_no_file(store):
    """No mcp_keys.md yet → list_keys()/get_key_scope fail-OPEN to empty (never 500)."""
    assert svc.list_keys() == []
    assert svc.get_key_scope("anything") is None


# --------------------------------------------------------------------------- #
# REST API — CRUD + agent-readable NOT_FOUND + auto-discovery                    #
# --------------------------------------------------------------------------- #
def test_rest_crud_roundtrip(client):
    # POST
    r = client.post("/mcp_keys", json={"label": "rest", "scope": {"domains": ["read"], "tools": []}})
    assert r.status_code == 200
    data = r.json()["data"]
    k = data["key"]
    assert data["label"] == "rest"
    # GET
    rows = client.get("/mcp_keys").json()["data"]
    assert any(row["key"] == k for row in rows)
    # PUT
    r = client.put(f"/mcp_keys/{k}", json={"label": "rest2"})
    assert r.status_code == 200 and r.json()["data"]["label"] == "rest2"
    # DELETE
    r = client.delete(f"/mcp_keys/{k}")
    assert r.status_code == 200 and r.json()["data"]["deleted"] == k


def test_rest_put_unknown_key_is_agent_error_404(client):
    r = client.put("/mcp_keys/nope-not-real", json={"label": "x"})
    assert r.status_code == 404
    err = r.json()["error"]   # flat agent_error body, NOT nested under "detail"
    assert err["code"] == "NOT_FOUND"
    assert err["hint"] and err["retryable"] is False


def test_rest_delete_unknown_key_is_agent_error_404(client):
    r = client.delete("/mcp_keys/nope-not-real")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_rest_create_bad_label_is_422(client):
    """Empty label → 422 (Pydantic min_length at the boundary)."""
    r = client.post("/mcp_keys", json={"label": "", "scope": {"domains": [], "tools": []}})
    assert r.status_code == 422


def test_module_auto_discovered_in_health(client):
    """The module auto-mounts via the registry → /health lists 'mcp_keys' (no core/main.py edit)."""
    modules = client.get("/health").json()["data"].get("modules", [])
    assert "mcp_keys" in modules, f"mcp_keys not auto-discovered: {modules}"
