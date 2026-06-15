"""tests/test_mcp_read.py — WHOLE-APP MCP read-server tests (MCP-1).

Coverage:
  - CALLABILITY: every tool in the registry runs against an empty/isolated app and
    returns a JSON-serialisable dict (never a bare list / model / None, never a crash).
  - ENVELOPE: each tool's dict carries its documented top-level key.
  - GRACEFUL: a missing entity (unknown channel / project / run) → {found: False},
    not a crash.
  - PARITY: a couple of tools return the same data as their service source.
  - THE CAPABILITY GATE: the read-server has NO write capability — no module-mutation
    symbol is bound in its namespace and none is imported (grep + AST proven, mirroring
    the wiki read-server's M4 gate).
  - server builds (FastMCP registers all tools) without error.

Uses ``isolated_paths`` (conftest) so every read runs against a fresh empty tmp app —
the read fns are all fail-open, so empty data must yield a clean empty envelope.
"""

from __future__ import annotations

import json

import pytest

from mcp_servers import read_server as rs


@pytest.fixture
def app_db(isolated_paths):
    """Empty but INITIALISED app: the wiki + proposal tables exist (the reliability
    read path queries ``wiki_notes``; in the live app these tables always exist —
    this fixture reproduces that, vs a bare tmp dir with no schema). All other reads
    are file-store / SQLite-lazy and fail-open on empty, so nothing else needs seeding.
    """
    from modules.wiki import store as wiki_store
    from modules.wiki import proposals_store as pstore
    from mcp_servers import proposals_store as agent_pstore

    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    agent_pstore.init_proposal_tables()  # MCP-5: the agent-proposal queue table
    return isolated_paths


# Tools that take no required args — callable with zero arguments against an empty app.
NULLARY_TOOLS = [
    "finance_overview",
    "market_overview",
    "projects_list",
    "graveyard_overview",
    "claude_usage",
    "daily_brief",
    "brief_history",
    "journal_entries",
    "decision_entries",
    "activity_feed",
    "exchange_overview",
    "app_settings",
    "reliability_report",
    "macro_overview",
    "news_digest",
    "news_list",
    "wiki_overview",
    "life_brief",
    "market_watchlist",
    "market_summary",
    "list_tools_catalog",
]

# Documented top-level envelope key per nullary tool.
ENVELOPE_KEY = {
    "finance_overview": "overview",
    "market_overview": "market",
    "projects_list": "projects",
    "graveyard_overview": "graveyard",
    "claude_usage": "usage",
    "daily_brief": "brief",
    "brief_history": "briefs",
    "journal_entries": "journal",
    "decision_entries": "decisions",
    "activity_feed": "activity",
    "exchange_overview": "exchange",
    "app_settings": "settings",
    "reliability_report": "report",
    "macro_overview": "macro",
    "news_digest": "digest",
    "news_list": "news",
    "wiki_overview": "overview",
    "life_brief": "brief",
    "market_watchlist": "items",
    "market_summary": "watchlist",
    "list_tools_catalog": "tools",
}


# --------------------------------------------------------------------------- #
# Callability + envelope — every tool returns a JSON-serialisable dict          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", NULLARY_TOOLS)
def test_nullary_tool_returns_jsonable_dict(name, app_db):
    out = rs.TOOLS[name]()
    assert isinstance(out, dict), f"{name} did not return a dict"
    # must be JSON-serialisable (the agent gets it over the wire as JSON)
    json.dumps(out)
    assert ENVELOPE_KEY[name] in out, f"{name} missing envelope key {ENVELOPE_KEY[name]!r}"


def test_registry_covers_all_tools_and_each_is_callable(app_db):
    # Every registered tool is a callable; the nullary set is the no-arg subset.
    assert set(NULLARY_TOOLS) <= set(rs.TOOLS)
    for name, fn in rs.TOOLS.items():
        assert callable(fn), f"{name} is not callable"


def test_arg_tools_return_jsonable_dict(app_db):
    # The arg-taking tools, exercised with explicit args against the empty app.
    for out in (
        rs.market_history("BTC", hours=24, limit=10),
        rs.market_indicators("BTC", indicators="rsi,sma", hours=720),
        rs.market_ohlc("BTC", hours=24, interval=60),
        rs.macro_history("cpi", days=400),
        rs.brief_history(limit=5),
        rs.activity_feed(routine="x", status="ok", range="today"),
        rs.wiki_search("anything", limit=5),
        rs.wiki_get(999999),
        rs.wiki_backlinks(999999),
    ):
        assert isinstance(out, dict)
        json.dumps(out)


def test_market_indicators_shape_and_no_crash(app_db):
    # Neutral TA read path: returns {indicators, warnings}; empty/short series →
    # per-indicator warning, never a crash.
    out = rs.market_indicators("BTC", indicators="summary")
    assert set(out) >= {"indicators", "warnings"}
    assert isinstance(out["warnings"], list)
    json.dumps(out)
    # an unknown indicator name is skipped + warned, not an error
    out2 = rs.market_indicators("BTC", indicators="not-a-real-indicator")
    assert isinstance(out2, dict)
    json.dumps(out2)


# --------------------------------------------------------------------------- #
# Market/TA tools (MCP-6) — OHLC + watchlist + summary, READ-ONLY + neutral      #
# --------------------------------------------------------------------------- #
def test_market_ohlc_shape_and_honest_warning(app_db):
    """OHLC candles for a tracked asset: {found, symbol, interval, candles, warnings}.
    Empty series → honest empty candles + warning, never a crash."""
    out = rs.market_ohlc("BTC", hours=24, interval=60)
    assert out["found"] is True
    assert set(out) >= {"found", "symbol", "interval", "candles", "warnings"}
    assert isinstance(out["candles"], list)
    assert isinstance(out["warnings"], list)
    json.dumps(out)


def test_market_ohlc_untracked_is_found_false(app_db):
    out = rs.market_ohlc("NOPE-NOT-TRACKED")
    assert out == {"found": False, "symbol": "NOPE-NOT-TRACKED"}


def test_market_watchlist_shape(app_db):
    out = rs.market_watchlist()
    assert set(out) >= {"items", "warnings"}
    assert isinstance(out["items"], list)
    json.dumps(out)


def test_market_summary_is_neutral_data(app_db):
    """One-call market read = watchlist + neutral technicals. Must be DATA, not advice
    — no recommendation/buy-sell key leaks (summarize() is neutral in ta.py)."""
    out = rs.market_summary()
    assert "watchlist" in out and isinstance(out["watchlist"], list)
    json.dumps(out)
    flat = json.dumps(out).lower()
    for banned in ("recommendation", "\"advice\"", "buy_sell", "\"action\":"):
        assert banned not in flat, f"market_summary leaked a non-neutral term: {banned}"


# --------------------------------------------------------------------------- #
# Macro tools (MACRO-2) — Fed/CPI/DXY context, READ-ONLY + neutral, mock-honest  #
# --------------------------------------------------------------------------- #
def test_macro_overview_shape_and_indicators(app_db):
    """macro_overview returns every tracked indicator + a descriptive trend.
    {macro, warnings}; cold-start auto-primes so values are present."""
    out = rs.macro_overview()
    assert set(out) >= {"macro", "warnings"}
    inds = out["macro"]["indicators"]
    assert {i["indicator"] for i in inds} == {"fed_funds_rate", "cpi", "dxy"}
    for i in inds:
        assert i["trend"] in ("up", "down", "flat")
    json.dumps(out)


def test_macro_overview_mock_is_honest(app_db, monkeypatch):
    """No FRED key → tool still returns values, tagged source='mock' + a warning, so
    the agent knows it's a placeholder, not live data."""
    from core.config import settings

    monkeypatch.setattr(settings, "fred_api_key", "")
    out = rs.macro_overview()
    assert out["macro"]["source"] == "mock"
    assert any("mock" in w.lower() for w in out["warnings"])


def test_macro_overview_is_neutral_no_forecast(app_db):
    """The macro context must DESCRIBE, never PREDICT — no forecast/advice term leaks."""
    flat = json.dumps(rs.macro_overview()).lower()
    for banned in ("forecast", "will cut", "will rise", "predict", "expect",
                   "recommend", "should buy", "should sell"):
        assert banned not in flat, f"macro_overview leaked a forecast/advice term: {banned}"


def test_macro_history_shape_and_unknown(app_db):
    out = rs.macro_history("cpi", days=400)
    assert out["found"] is True
    assert out["history"]["indicator"] == "cpi"
    assert isinstance(out["history"]["points"], list)
    # unknown indicator → honest found:False, not a crash
    assert rs.macro_history("not-an-indicator") == {"found": False, "indicator": "not-an-indicator"}


# --------------------------------------------------------------------------- #
# NEWS-MCP — wrap news READ over MCP (mirror macro). NEUTRAL, source-cited,      #
# honest-empty, tag-filter, 0 write-leak (gate covered by WRITE_SYMBOLS).        #
# --------------------------------------------------------------------------- #
def _seed_news_item(*, title, url, source="Reuters", tags=None, ts="2026-06-15T00:00:00+00:00"):
    from modules.news import store as news_store
    news_store.upsert_item(title=title, summary="", url=url, source=source,
                           published_ts=ts, tags=tags or [], captured_at=ts)


def test_news_digest_cites_source_and_honest_empty(app_db):
    # honest-empty: nothing captured → count 0, items [], NOT fabricated.
    empty = rs.news_digest()["digest"]
    assert empty["count"] == 0 and empty["items"] == []
    assert "headline" in empty and "note" in empty  # honest note, no invented headline
    # seeded: each item cites its source url
    _seed_news_item(title="Fed holds rates", url="https://reuters.com/a", tags=["MACRO"])
    out = rs.news_digest()["digest"]
    assert out["count"] == 1
    item = out["items"][0]
    assert item["url"] == "https://reuters.com/a" and item["source"] == "Reuters"
    assert item["title"] == "Fed holds rates"


def test_news_list_shape_and_tag_filter(app_db):
    _seed_news_item(title="BTC ETF news", url="https://x.com/btc", tags=["CRYPTO"])
    _seed_news_item(title="VN macro", url="https://x.com/vn", tags=["MACRO"])
    alln = rs.news_list()["news"]
    assert alln["count"] == 2
    assert {"title", "url", "source", "publishedTs"} <= set(alln["items"][0].keys())
    # tag filter narrows; unknown tag → [] clean
    crypto = rs.news_list(tag="CRYPTO")["news"]
    assert crypto["count"] == 1 and crypto["items"][0]["title"] == "BTC ETF news"
    assert rs.news_list(tag="NOPE")["news"]["count"] == 0


def test_news_mcp_neutral_no_leak(app_db):
    # NEUTRAL preserved at the MCP wrapper: no sentiment/advice/forecast term leaks.
    _seed_news_item(title="Bitcoin price moves after Fed meeting",
                    url="https://x.com/neutral", tags=["CRYPTO"])
    flat = json.dumps(rs.news_digest(), ensure_ascii=False).lower()
    for banned in ("buy", "sell", "bullish", "bearish", "recommend", "forecast",
                   "khuyến nghị", "nên mua", "nên bán"):
        assert banned not in flat, f"news_digest leaked a sentiment/advice term: {banned}"


# --------------------------------------------------------------------------- #
# WIKI-MCP — wrap wiki READ over MCP (mirror news). search/get/overview/        #
# backlinks; honest-found-false; integer-id citation; 0 write-leak.             #
# --------------------------------------------------------------------------- #
def _seed_wiki_note(title="Atomicity", content="a note holds one idea"):
    from modules.wiki.service import create_note
    from modules.wiki.schema import NoteCreateInput
    return create_note(NoteCreateInput(title=title, content=content)).id


def test_wiki_search_and_get_roundtrip(app_db):
    nid = _seed_wiki_note(title="Spaced repetition", content="review on a curve")
    # search finds it (ranked results, each with an integer id to cite)
    res = rs.wiki_search("repetition")["results"]
    assert any(r["id"] == nid for r in res)
    assert {"id", "title", "snippet", "status"} <= set(res[0].keys())
    # get by integer id returns the note
    got = rs.wiki_get(nid)
    assert got["found"] is True and got["note"]["id"] == nid
    assert got["note"]["title"] == "Spaced repetition"


def test_wiki_get_missing_is_found_false(app_db):
    assert rs.wiki_get(999999) == {"found": False, "note_id": 999999}


def test_wiki_overview_shape_and_empty_honest(app_db):
    out = rs.wiki_overview()
    assert "overview" in out
    ov = out["overview"]
    assert {"stats", "inbox", "orphans", "recentActivity"} <= set(ov.keys())
    # empty vault → pctWithLink None (never div-zero), warning present
    assert ov["stats"].get("pctWithLink") is None


def test_wiki_backlinks_shape(app_db):
    a = _seed_wiki_note(title="Target", content="t")
    b = _seed_wiki_note(title="Source", content=f"see [[{a}]]")
    out = rs.wiki_backlinks(a)["backlinks"]
    assert {"linked", "unlinked", "outbound"} <= set(out.keys())
    assert any(l["id"] == b for l in out["linked"])  # the inbound link surfaces


def test_wiki_mcp_no_write_leak(app_db):
    # WIKI-MCP capability gate: the read-server must NOT bind any wiki write fn.
    # (the wiki writes are already in WRITE_SYMBOLS; this asserts 0 leak at the
    # read-server namespace, the same gate the AST/namespace tests enforce.)
    ns = set(vars(rs))
    for w in ("create_note", "update_note", "delete_note", "merge_notes",
              "enqueue", "create_proposal", "accept_proposal", "reject_proposal"):
        assert w not in ns, f"read-server leaked a wiki write symbol: {w}"
    # and the read fns ARE reachable (aliased-private) — wired, not absent
    assert "_wiki_search" in ns and "_wiki_get_note" in ns


# --------------------------------------------------------------------------- #
# Graceful failure (no crash) — missing entity → {found: False}                 #
# --------------------------------------------------------------------------- #
def test_unknown_channel_is_found_false(app_db):
    out = rs.finance_channel("no-such-channel")
    assert out["found"] is False
    assert out["channel"] == "no-such-channel"


def test_unknown_project_is_found_false(app_db):
    out = rs.project_get("no-such-project")
    assert out == {"found": False, "project_id": "no-such-project"}


def test_unknown_run_is_found_false(app_db):
    out = rs.activity_run(999999)
    assert out == {"found": False, "run_id": 999999}


# --------------------------------------------------------------------------- #
# Parity — tool output == service output (the tool is a thin read wrapper)       #
# --------------------------------------------------------------------------- #
def test_settings_parity(app_db):
    from modules.settings import service as ssvc

    assert rs.app_settings()["settings"] == ssvc.get_config().model_dump()


def test_journal_parity(app_db):
    from modules.journal import service as jsvc

    stats, warnings = jsvc.list_entries()
    out = rs.journal_entries()
    assert out["journal"] == stats.model_dump()
    assert out["warnings"] == warnings


# --------------------------------------------------------------------------- #
# life_brief — the agent data-layer synthesizer (MCP-2)                          #
# --------------------------------------------------------------------------- #
BRIEF_SECTIONS = {
    "portfolio": "finance",
    "market": "market",
    "projects": "projects",
    "claude": "claude_usage",
    "decisions": "decision_journal",
    # R2-G1: life_brief now folds in macro + news + wiki context.
    "macro": "macro",
    "news": "news",
    "wiki": "wiki",
}


def test_life_brief_full_shape_and_source_tags(app_db):
    """Every section is present, each carries its source tag, the whole thing is
    JSON-serialisable — even on an empty/honest app."""
    out = rs.life_brief()
    assert set(out) == {"brief"}
    brief = out["brief"]
    assert set(brief) == set(BRIEF_SECTIONS), f"unexpected sections: {set(brief)}"
    for section, source in BRIEF_SECTIONS.items():
        assert brief[section]["source"] == source, f"{section} wrong source tag"
    json.dumps(out)


def test_life_brief_sections_have_no_error_on_clean_app(app_db):
    """On a clean initialised app no section should fail-soft to {error} — the read
    paths are all fail-open, so each section assembles."""
    brief = rs.life_brief()["brief"]
    errored = {k: v["error"] for k, v in brief.items() if "error" in v}
    assert errored == {}, f"sections errored on a clean app: {errored}"


def test_life_brief_is_neutral_data_only(app_db):
    """The brief must be DATA, not advice — no recommendation/signal/action keys leak
    into any section (the agent reasons; the tool only aggregates)."""
    brief = rs.life_brief()["brief"]
    flat = json.dumps(brief).lower()
    for banned in ("recommendation", "advice", "\"signal\"", "buy_sell", "\"action\":"):
        assert banned not in flat, f"brief leaked a non-neutral key/term: {banned}"


def test_life_brief_section_failsoft_keeps_brief(app_db, monkeypatch):
    """A single source raising must NOT 500 the brief — that section reports {error}
    and the other four still assemble (fail-soft per section)."""
    def boom():
        raise RuntimeError("simulated source down")

    monkeypatch.setattr(rs, "_brief_portfolio", boom)
    brief = rs.life_brief()["brief"]
    # the broken section reports an error but keeps its source tag
    assert "error" in brief["portfolio"]
    assert brief["portfolio"]["source"] == "finance"


def test_R2G1_life_brief_includes_macro_news_wiki(app_db):
    """R2-G1: life_brief folds in the 3 new context sections, each present + content-
    shaped on a clean app (honest, not errored)."""
    brief = rs.life_brief()["brief"]
    assert {"macro", "news", "wiki"} <= set(brief)
    # macro: descriptive indicators (NEUTRAL data)
    assert "macro" in brief["macro"] and "error" not in brief["macro"]
    # news: a source-cited digest, honest-empty ok
    assert "digest" in brief["news"] and "error" not in brief["news"]
    # wiki: vault overview
    assert "overview" in brief["wiki"] and "error" not in brief["wiki"]


def test_R2G1_new_sections_failsoft(app_db, monkeypatch):
    """Each new section is fail-soft: a down source → {error} for THAT section, the
    rest of the brief still assembles (no 500)."""
    monkeypatch.setattr(rs, "_brief_news", lambda: (_ for _ in ()).throw(RuntimeError("news down")))
    brief = rs.life_brief()["brief"]
    assert "error" in brief["news"] and brief["news"]["source"] == "news"
    # the others unaffected
    assert "error" not in brief["macro"] and "error" not in brief["wiki"]


def test_R2G1_life_brief_still_neutral_with_new_sections(app_db):
    """The 3 new sections must not leak advice/sentiment (macro=descriptive, news=
    source-cited headlines, wiki=stats) — the brief stays DATA-only."""
    brief = rs.life_brief()["brief"]
    flat = json.dumps({k: brief[k] for k in ("macro", "news", "wiki")}, ensure_ascii=False).lower()
    for banned in ("buy", "sell", "bullish", "bearish", "recommend", "forecast", "khuyến nghị"):
        assert banned not in flat, f"a new brief section leaked a sentiment/advice term: {banned}"
    # the rest are unaffected
    for section in ("market", "projects", "claude", "decisions"):
        assert "error" not in brief[section], f"{section} should be unaffected"


def test_life_brief_market_uses_tracked_assets_and_indicators(app_db):
    """The market section lists per-tracked-asset entries, each with a quote +
    (neutral) indicators slot — proving it composes the TA read path, not advice."""
    market = rs.life_brief()["brief"]["market"]
    assert "assets" in market
    assert isinstance(market["assets"], list)
    if market["assets"]:
        a = market["assets"][0]
        assert set(a) >= {"symbol", "quote", "indicators"}


# --------------------------------------------------------------------------- #
# Proposal feedback (MCP-5) — the agent reads its own proposals' disposition     #
# --------------------------------------------------------------------------- #
def test_check_proposal_status_unknown_is_found_false(app_db):
    out = rs.check_proposal_status(999999)
    assert out == {"found": False, "proposalId": 999999}


def test_list_my_proposals_empty_is_clean(app_db):
    out = rs.list_my_proposals()
    assert out == {"proposals": []}


def test_proposal_stats_empty_is_zero(app_db):
    out = rs.proposal_stats()
    assert out["counts"] == {"pending": 0, "accepted": 0, "rejected": 0}
    assert out["acceptanceRate"] is None  # honest: no decided proposals yet


def test_feedback_loop_propose_pending_then_accepted(app_db):
    """The agent-side loop: propose → check=pending → (human accepts via the apply
    service) → check=accepted + appliedRef set. This is what lets the agent learn."""
    from mcp_servers import write_server as ws
    from mcp_servers import proposals_service as psvc

    p = ws.propose_decision("Trim crypto", 60, "portfolio", "over target")
    pid = p["id"]

    # agent checks: still pending
    s1 = rs.check_proposal_status(pid)
    assert s1["found"] is True and s1["status"] == "pending"
    assert s1["appliedRef"] is None

    # it shows in the agent's pending list + stats
    assert pid in {x["id"] for x in rs.list_my_proposals(status="pending")["proposals"]}
    assert rs.proposal_stats()["counts"]["pending"] == 1

    # human accepts (human-only apply path) → applies to the decision module
    psvc.accept(pid, decided_by="user")

    # agent re-checks: now accepted + appliedRef points at the created entry
    s2 = rs.check_proposal_status(pid)
    assert s2["status"] == "accepted"
    assert s2["appliedRef"] is not None
    assert s2["decidedBy"] == "user"

    # stats reflect the decision: 1 accepted, acceptanceRate 1.0
    stats = rs.proposal_stats()
    assert stats["counts"]["accepted"] == 1
    assert stats["acceptanceRate"] == 1.0


def test_feedback_loop_rejected_visible_to_agent(app_db):
    from mcp_servers import write_server as ws
    from mcp_servers import proposals_service as psvc

    p = ws.propose_note("idea", "worth capturing")
    psvc.reject(p["id"], decided_by="user")
    s = rs.check_proposal_status(p["id"])
    assert s["status"] == "rejected"
    assert s["appliedRef"] is None
    assert rs.proposal_stats()["counts"]["rejected"] == 1


# --------------------------------------------------------------------------- #
# Tool catalog (MCP-8) — discoverable, DERIVED from the live registries          #
# --------------------------------------------------------------------------- #
def test_catalog_count_matches_real_servers(app_db):
    """The catalog must list EXACTLY the tools the servers expose — no more, no less.
    Derived from the live registries, so it cannot drift (the anti-hardcode guard)."""
    from mcp_servers import write_server as ws

    cat = rs.list_tools_catalog()
    assert cat["counts"]["read"] == len(rs.TOOLS)
    assert cat["counts"]["write"] == len(ws.TOOLS)
    assert cat["counts"]["total"] == len(rs.TOOLS) + len(ws.TOOLS)
    # the SET of names matches too (not just the count)
    listed = {(t["server"], t["name"]) for t in cat["tools"]}
    expected = {("read", n) for n in rs.TOOLS} | {("write", n) for n in ws.TOOLS}
    assert listed == expected, f"catalog drift: {listed ^ expected}"


def test_catalog_every_tool_has_description_and_fields(app_db):
    cat = rs.list_tools_catalog()
    for t in cat["tools"]:
        assert set(t) >= {"name", "server", "capability", "neutral", "description"}
        assert t["description"], f"{t['name']} has no description"
        assert t["server"] in ("read", "write")
        assert t["capability"] in ("read", "propose")
        assert isinstance(t["neutral"], bool)
    json.dumps(cat)


def test_catalog_states_capability_boundary(app_db):
    """The catalog must spell out the supervision boundary so the agent reasons within
    it: read writes nothing; write only proposes; apply is human-only; agent reads
    verdict; analysis is neutral."""
    cat = rs.list_tools_catalog()
    b = cat["capabilityBoundary"]
    assert set(b) >= {"read", "write", "apply", "feedback", "neutrality"}
    assert "human-only" in b["apply"].lower()
    assert "propos" in b["write"].lower()
    assert "neutral" in b["neutrality"].lower()


def test_catalog_marks_write_tools_as_propose_not_apply(app_db):
    """No write tool is ever labelled with an apply/accept capability — they propose."""
    cat = rs.list_tools_catalog()
    write_tools = [t for t in cat["tools"] if t["server"] == "write"]
    assert write_tools, "expected write tools in the catalog"
    assert all(t["capability"] == "propose" for t in write_tools)


def test_catalog_does_not_grant_write_capability(app_db):
    """The catalog is READ/metadata — building it must not bind any write symbol into
    the read-server's namespace (the lazy write_server import is metadata-only)."""
    for sym in ("enqueue", "_enqueue", "mark_decided", "accept", "reject",
                "set_applied_ref", "write_server"):
        assert sym not in vars(rs), f"catalog leaked {sym!r} into the read-server"


# --------------------------------------------------------------------------- #
# THE CAPABILITY GATE — no write capability (structural, grep + AST proven)      #
# --------------------------------------------------------------------------- #
# Mutation symbols across the wrapped modules: if ANY is reachable from this
# server's namespace / imports, a read tool could be escalated to a write.
WRITE_SYMBOLS = [
    # finance
    "upsert_holding", "delete_holding", "set_golden_path", "set_crypto_basis",
    # market
    "add_rule", "delete_rule", "poll_once",
    # projects
    "register_project", "abandon_project", "restore_project", "refresh_project",
    # journals
    "create_entry", "update_entry", "delete_entry",
    # brief / exchange / settings
    "save_brief", "sync", "set_config", "set_override",
    # wiki write surface must not leak in either
    "create_note", "update_note", "delete_note", "merge_notes",
    "enqueue", "create_proposal", "accept_proposal", "reject_proposal",
    # MCP-5: the agent-proposal queue's WRITE/DECIDE surface — the read-server reads
    # proposal STATUS but must NOT import any of these (the agent can't write/decide
    # its own proposal via the read-server; accept/reject is human-only at REST).
    "mark_decided", "set_applied_ref", "append_audit", "accept", "reject",
    # MACRO-2: the macro module's WRITE surface — the read-server reads macro context
    # but must NOT import refresh/record_point/init_macro_tables (the agent can't write
    # the macro series).
    "refresh", "record_point", "init_macro_tables",
    # NEWS-MCP: the news module's WRITE/FETCH/INIT surface — the read-server reads
    # digest/list but must NOT import capture (RSS fetch+write) / init_news_tables /
    # upsert_item (the agent reads captured news; it cannot capture or init the store).
    "capture", "init_news_tables", "upsert_item",
]


def test_read_server_has_no_write_symbol_in_namespace():
    """No module-mutation name is bound in the read server's module namespace. This is
    the least-privilege gate: a read tool cannot be escalated to a write because the
    write symbols are not importable from here. (Mirrors the wiki read-server gate.)"""
    ns = vars(rs)
    leaked = [s for s in WRITE_SYMBOLS if s in ns]
    assert leaked == [], f"read server leaked write symbols: {leaked}"


def test_read_server_imports_no_write_symbol_ast():
    """Parse the read server's IMPORT statements (AST, not a string grep — a docstring
    legitimately names the excluded symbols) and assert none of them import a module-
    mutation name. The wrapped imports are READ entry-points only."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(rs))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported_names.add(alias.name)                    # the real name
                imported_names.add(alias.asname or alias.name)    # the bound name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.add(alias.name)

    leaked = set(WRITE_SYMBOLS) & imported_names
    assert leaked == set(), f"read server imports write symbols: {leaked}"


def test_imported_read_paths_are_only_aliased_private_names():
    """Every name the server BINDS from a module import is a private (underscore) read
    wrapper — i.e. the server never binds a bare public service symbol into its
    namespace where it could be mistaken for / reused as a write entry-point. This
    catches an accidental ``from x import set_config`` that the WRITE_SYMBOLS list
    might not enumerate."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(rs))
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("modules."):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    # all module-read imports are aliased to a leading-underscore private name
    non_private = [n for n in bound if not n.startswith("_")]
    assert non_private == [], f"non-private bound read imports: {non_private}"


# --------------------------------------------------------------------------- #
# Server builds                                                                  #
# --------------------------------------------------------------------------- #
def test_build_server_registers_all_tools():
    # Building the FastMCP server must not raise and must not drop any registry tool.
    server = rs.build_server()
    assert server is not None
    assert len(rs.TOOLS) == 34  # +4 WIKI-MCP (search/get/overview/backlinks); was 30 (NEWS-MCP)
