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
def app_db(isolated_paths, monkeypatch):
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
    # FRED-MACRO: macro_overview/life_brief/insights trigger a macro cold-start refresh,
    # whose no-key CSV path would otherwise hit the LIVE network (slow + flaky in the
    # suite). Neutralize it → deterministic mock (CSV fails). A test wanting the real CSV
    # path overrides macro.reader.httpx.get itself.
    from modules.macro import reader as macro_reader
    monkeypatch.setattr(macro_reader.httpx, "get",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network off in app_db")))
    return isolated_paths


@pytest.fixture
def mock_okx_for_insights(monkeypatch):
    """Patch the exchange so the crypto channel is stablecoin-heavy (USDT) — so the
    undeployed-capital insight has real cross-domain data to fire on."""
    from modules.finance import service as fin
    from modules.exchange.schema import ExchangeOverview, OkxBalance
    # 95% USDT (> the 90% undeployed threshold; mirrors the live ~97.7% reality)
    snap = ExchangeOverview(configured=True, totalUsdValue=10000.0, balances=[
        OkxBalance(symbol="USDT", available=9500, frozen=0, total=9500, usdValue=9500.0),
        OkxBalance(symbol="BTC", available=0.008, frozen=0, total=0.008, usdValue=500.0),
    ])
    monkeypatch.setattr(fin.exchange_service, "get_overview", lambda: (snap, None))


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
    # MCP-DEDUP #70: wiki_overview removed from the shared server (canonical = standalone)
    "life_brief",
    "insights",
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
    "life_brief": "brief",
    "insights": "insights",
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
        # MCP-DEDUP #70: wiki_search/get/backlinks removed (canonical = standalone server)
        rs.finance_simulate({"crypto": 50, "etf": 50}),
        rs.market_correlation("BTC,ETH", hours=24),
        rs.market_relative_strength("ETH", vs="BTC", hours=24),
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
# NB-FINANCE-MCP — pure-compute analytics surfaced read-only: finance_simulate    #
# (what-if, zero side-effect) + market_correlation + market_relative_strength.    #
# --------------------------------------------------------------------------- #
def test_finance_simulate_shape_and_neutral(app_db):
    """finance_simulate returns {result, warnings} with the hypothetical+current shape.
    PURE numbers — no advice key."""
    out = rs.finance_simulate({"crypto": 60, "etf": 40})
    assert "result" in out and "warnings" in out
    assert "hypothetical" in out["result"] and "current" in out["result"]
    flat = json.dumps(out).lower()
    for banned in ("recommendation", "\"advice\"", "buy_sell", "\"action\":"):
        assert banned not in flat


def test_finance_simulate_bad_input_is_honest_error_not_crash(app_db):
    """Bad input → a STRUCTURED agent_error (AGENT-ERROR #46-P2), never a raised HTTPException/
    traceback. The agent branches on error.code + error.retryable instead of parsing free text."""
    for bad in ({}, {"bogus": 50}, {"crypto": -10}):                # empty / unknown / negative
        e = rs.finance_simulate(bad)["error"]
        assert e["code"] == "INVALID_INPUT" and e["retryable"] is False
        assert e["message"] and e["hint"]                          # both populated (the hint names the fix)
    # THE distinguishing: the unknown-channel hint NAMES the valid set the agent should use
    unk = rs.finance_simulate({"bogus": 50})["error"]
    assert "crypto" in unk["hint"] and "etf" in unk["hint"], "hint must name the valid channels"
    # zero-sum is ACCEPTED (router contract) → a result with a warning, not an error
    zero = rs.finance_simulate({"crypto": 0, "etf": 0})
    assert "result" in zero and any("normalize" in w for w in zero["warnings"])
    assert "error" not in zero  # a valid (if zero-sum) allocation is NOT an error


def test_finance_simulate_zero_side_effect_on_holdings(app_db):
    """DISTINGUISHING / the dispatch's core claim: simulate is a READ-ONLY what-if —
    it must NOT touch the persisted portfolio. Snapshot the holdings store before/after
    and assert BYTE + MTIME identical (a what-if that wrote — even a rewrite with the same
    content, which bumps mtime — would be a serious bug). Same discipline as NB1+NB2."""
    from core.config import settings
    from modules.finance import service as fin
    # seed a real holding so there's persisted state to (not) disturb
    from modules.finance.schema import HoldingInput
    fin.upsert_holding(HoldingInput(symbol="BTC", channel="crypto", qty=1, avgCost=100))
    disk = settings.data_dir / fin.HOLDINGS_MD
    before = disk.read_bytes()
    mtime_before = disk.stat().st_mtime_ns
    rs.finance_simulate({"crypto": 30, "etf": 70})  # a what-if that re-weights crypto
    assert disk.read_bytes() == before, "finance_simulate rewrote the holdings store — must be read-only"
    assert disk.stat().st_mtime_ns == mtime_before, "finance_simulate touched holdings.md mtime"
    # and the live overview still reports the seeded holding unchanged
    assert any(h.symbol == "BTC" for h in fin.list_holdings())


def test_market_correlation_shape_and_bounds(app_db):
    """market_correlation → {correlation, warnings}; <2 or >10 symbols → a STRUCTURED agent_error
    (AGENT-ERROR #46-P2: code=INVALID_INPUT, retryable=False), not free text."""
    out = rs.market_correlation("BTC,ETH", hours=24)
    assert "correlation" in out and "matrix" in out["correlation"]
    for bad in ("BTC", ",".join(f"S{i}" for i in range(11))):   # <2, >10
        e = rs.market_correlation(bad)["error"]
        assert e["code"] == "INVALID_INPUT" and e["retryable"] is False
        assert e["message"] and e["hint"]


def test_market_relative_strength_shape(app_db):
    """market_relative_strength → {relativeStrength, warnings}; thin data → None fields,
    never a crash."""
    out = rs.market_relative_strength("ETH", vs="BTC", hours=24)
    assert "relativeStrength" in out
    assert out["relativeStrength"]["symbol"] == "ETH"
    assert out["relativeStrength"]["benchmark"] == "BTC"
    json.dumps(out)


def test_NB_FINANCE_MCP_no_write_leak(app_db):
    """The 3 new analytics tools wrap ONLY pure-compute reads — no portfolio/market
    write symbol reachable (the read gate holds)."""
    ns = set(vars(rs))
    for w in ("upsert_holding", "delete_holding", "set_golden_path", "set_crypto_basis",
              "add_rule", "delete_rule", "poll_once"):
        assert w not in ns, f"NB-FINANCE-MCP leaked a write symbol: {w}"


# --------------------------------------------------------------------------- #
# INSIGHTS (D1) — cross-domain neutral observations over the live read paths.    #
# --------------------------------------------------------------------------- #
def test_insights_shape_and_honest_empty(monkeypatch, app_db):
    """With every source EMPTY (no holdings/crypto/notes/projects) NO rule fires →
    honest-empty {insights: []}, never a crash. (The live dev box has a configured OKX +
    real project repos, so isolate those sources here — the point is the empty-data path.)"""
    from modules.finance import service as fin
    from modules.exchange.schema import ExchangeOverview
    monkeypatch.setattr(fin.exchange_service, "get_overview",
                        lambda: (ExchangeOverview(configured=False, totalUsdValue=0.0, balances=[]), None))
    monkeypatch.setattr(rs, "_proj_list", lambda: ([], []))
    monkeypatch.setattr(rs, "_mkt_tracked", lambda: [])
    monkeypatch.setattr(rs, "_wiki_search", lambda *a, **k: [])
    out = rs.insights()
    assert out["insights"] == []
    assert out["note"] == "nothing notable across modules right now"  # honest-empty, not fabricated
    assert "asOf" in out and out["sources"] == []


def test_insights_shape_frozen(app_db):
    """FROZEN shape: {insights:[{insight,severity,evidence,sources}], asOf, sources, note?}."""
    out = rs.insights()
    assert {"insights", "asOf", "sources"} <= set(out)
    for i in out["insights"]:
        assert {"insight", "severity", "evidence", "sources"} <= set(i)
        assert i["severity"] in ("high", "medium", "low")
        assert isinstance(i["insight"], str) and i["insight"]
        assert i["evidence"], "every insight carries non-empty evidence (anti-hallucination)"
        assert i["sources"], "every insight names its source tool(s)"


def test_insights_each_is_neutral_no_advice_verb(app_db):
    """NEUTRAL (HARD): no advice verb (should/buy/sell/rebalance/move/consider/recommend)
    in ANY emitted insight string — they're composition + evidence statements."""
    out = rs.insights()
    for i in out["insights"]:
        s = i["insight"].lower()
        for verb in ("should", "buy", "sell", "rebalance", "move ", "consider", "recommend"):
            assert verb not in s, f"insight leaked an advice verb {verb!r}: {i['insight']}"


def test_insights_undeployed_capital_fires_on_stablecoin_heavy(mock_okx_for_insights, app_db):
    """undeployed-capital FIRES (high) when the crypto channel is >90% stablecoin; evidence
    carries stablePct + dryPowder; source finance_overview."""
    out = rs.insights()
    ins = next((i for i in out["insights"] if "stablecoin" in i["insight"]), None)
    assert ins is not None, "undeployed-capital should fire on a 90%-stablecoin crypto channel"
    assert ins["severity"] == "high"
    assert ins["sources"] == ["finance_overview"]
    assert ins["evidence"]["stablePct"] > 90.0 and "dryPowder" in ins["evidence"]


def test_insights_undeployed_does_not_fire_when_healthy(monkeypatch, app_db):
    """ANTI-BLANKET (distinguishing): a HEALTHY crypto channel (stablePct 20) → undeployed
    does NOT fire. Proves it keys on the REAL >90% condition, not blanket text."""
    from types import SimpleNamespace
    healthy = SimpleNamespace(channel="crypto", stablePct=20.0, target=20.0, pct=20.0)
    ov = SimpleNamespace(allocations=[healthy], dryPowder=0.0, totalValue=10000.0)
    monkeypatch.setattr(rs, "_fin_overview", lambda: (ov, []))
    assert rs._insight_undeployed_capital() is None


def test_insights_all_crypto_overbought_distinguishing(monkeypatch, app_db):
    """DISTINGUISHING: fires ONLY when ALL tracked crypto are overbought. One neutral → NO
    fire (AND over the set, not 'any overbought')."""
    crypto = [{"symbol": "BTC", "assetClass": "crypto"},
              {"symbol": "ETH", "assetClass": "crypto"}]
    monkeypatch.setattr(rs, "_mkt_tracked", lambda: crypto)

    def _ind(sym, names, hours=720, full=False):
        sig = "overbought" if sym == "BTC" else "neutral"  # ETH neutral → must NOT fire
        return {"indicators": {"summary": {"signals": {"rsi": sig}, "latest": {"rsi": 50}}}}, []
    monkeypatch.setattr(rs, "_mkt_indicators", _ind)
    assert rs._insight_all_crypto_overbought() is None

    # now ALL overbought → fires (medium, source market_indicators, evidence perAsset)
    monkeypatch.setattr(rs, "_mkt_indicators",
                        lambda s, n, hours=720, full=False:
                        ({"indicators": {"summary": {"signals": {"rsi": "overbought"},
                                                     "latest": {"rsi": 80}}}}, []))
    ins = rs._insight_all_crypto_overbought()
    assert ins is not None and ins["severity"] == "medium"
    assert ins["sources"] == ["market_indicators"]
    assert set(ins["evidence"]["perAsset"]) == {"BTC", "ETH"}


def test_insights_fail_soft_one_bad_rule_doesnt_break(monkeypatch, app_db):
    """A rule that raises → tagged in sources as an error, the others still run (fail-soft)."""
    def _boom():
        raise RuntimeError("rule blew up")
    monkeypatch.setattr(rs, "_INSIGHT_RULES", [_boom, rs._insight_stalled_projects])
    out = rs.insights()
    assert "insights" in out  # didn't crash
    assert any("error" in s for s in out["sources"])


def test_insights_severity_ranked_high_to_low(monkeypatch, app_db):
    """high insights sort before medium before low."""
    monkeypatch.setattr(rs, "_INSIGHT_RULES", [
        lambda: {"insight": "lo", "severity": "low", "evidence": {"x": 1}, "sources": ["a"]},
        lambda: {"insight": "hi", "severity": "high", "evidence": {"x": 1}, "sources": ["a"]},
        lambda: {"insight": "md", "severity": "medium", "evidence": {"x": 1}, "sources": ["a"]},
    ])
    out = rs.insights()["insights"]
    assert [i["severity"] for i in out] == ["high", "medium", "low"]


def test_insights_read_only_no_disk_mutation(mock_okx_for_insights, app_db):
    """READ-ONLY: calling insights() mutates no finance store (byte+mtime unchanged)."""
    from core.config import settings
    from modules.finance import service as fin
    from modules.finance.schema import HoldingInput
    fin.upsert_holding(HoldingInput(symbol="ETH", channel="crypto", qty=1, avgCost=2000))
    disk = settings.data_dir / fin.HOLDINGS_MD
    before, mtime = disk.read_bytes(), disk.stat().st_mtime_ns
    rs.insights()
    assert disk.read_bytes() == before and disk.stat().st_mtime_ns == mtime


def test_insights_no_write_symbol_leak(app_db):
    """The insights rules read only — no write symbol reachable."""
    ns = set(vars(rs))
    for w in ("upsert_holding", "create_note", "register_project", "set_config", "enqueue"):
        assert w not in ns, f"insights leaked a write symbol: {w}"


# --------------------------------------------------------------------------- #
# Macro tools (MACRO-2) — Fed/CPI/DXY context, READ-ONLY + neutral, mock-honest  #
# --------------------------------------------------------------------------- #
def test_macro_overview_shape_and_indicators(app_db):
    """macro_overview returns every tracked indicator + a descriptive trend.
    {macro, warnings}; cold-start auto-primes so values are present."""
    out = rs.macro_overview()
    assert set(out) >= {"macro", "warnings"}
    inds = out["macro"]["indicators"]
    # #52 FINANCE-ASSISTANT P1: + the macro-cycle substrate (yield_curve/unemployment/m2/indpro).
    # (fear_greed/btc_dominance are snapshot-only → macro_history, NOT in the FRED-driven overview.)
    assert {i["indicator"] for i in inds} == {
        "fed_funds_rate", "cpi", "dxy",
        "yield_curve_10y2y", "unemployment", "m2_liquidity", "industrial_production",
    }
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
# WIKI-MCP (MCP-DEDUP #70) — the wiki READ tools were REMOVED from this shared    #
# server; canonical = the standalone modules/wiki/mcp/read_server (tested in      #
# test_wiki_mcp_read.py). The 4 read dupes (search/get/overview/backlinks) have   #
# parity tests there; the 2 ported proposal-readback tools (wiki_proposal_status  #
# + wiki_list_proposals) were MOVED to test_wiki_mcp_read.py. What remains here   #
# is the shared read-server's OWN no-write gate (it must bind no wiki write fn)    #
# + the kept _wiki_search/_wiki_overview imports (life_brief + insights use them, #
# NOT as MCP tools).                                                              #
# --------------------------------------------------------------------------- #
def test_shared_read_server_has_no_wiki_tools_after_dedup(app_db):
    """MCP-DEDUP #70: the shared read-server exposes NO wiki_* MCP tool (all moved to
    the standalone). The before/after gate: zero wiki tool keys remain."""
    wiki_tools = [k for k in rs.TOOLS if k.startswith("wiki")]
    assert wiki_tools == [], f"shared read-server still exposes wiki tools: {wiki_tools}"


def test_shared_read_server_no_wiki_write_leak(app_db):
    # The shared read-server must NOT bind any wiki write/mutate fn (its capability gate).
    ns = set(vars(rs))
    for w in ("create_note", "update_note", "delete_note", "merge_notes",
              "enqueue", "create_proposal", "accept_proposal", "reject_proposal"):
        assert w not in ns, f"read-server leaked a wiki write symbol: {w}"
    # _wiki_search + _wiki_overview ARE kept — life_brief (_brief_wiki) + insights
    # (_brief_decision) consume them (read-only reader fns, NOT MCP tools).
    assert "_wiki_search" in ns and "_wiki_overview" in ns
    # the removed wiki-tool imports are GONE (dedup actually happened)
    assert "_wiki_get_note" not in ns and "_wiki_backlinks" not in ns


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
    # FINANCE-FINISH G1: the decision tower (W/verdict/binding/phase/top-alert).
    "decision": "decision",
    # REMINDERS-4 (#30): what's on the user's plate (overdue+today+week un-done).
    "reminders": "reminders",
    # DAILY-TRACING-P4 (#65): habit board — at-risk streaks + today's done/total.
    "tracing": "tracing",
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


# --------------------------------------------------------------------------- #
# #100 — life_brief.wiki LEAN projection (counts + top-N stubs, NOT the full dump) #
# --------------------------------------------------------------------------- #
def test_100_brief_wiki_is_lean_counts_and_top_stubs(app_db):
    """#100: brief.wiki.overview is the LEAN shape — counts + top-3 STUBS (id/title/status, NO
    rawContent), recentActivity capped ≤5, + a truncated flag. NOT the full inbox dump (was 23KB)."""
    from modules.wiki import service as wsvc
    from modules.wiki.schema import NoteCreateInput
    for i in range(5):  # 5 fleeting notes → the inbox; cap-to-3 must kick in
        wsvc.create_note(NoteCreateInput(title=f"Inbox note {i}", content=f"raw body {i} " * 20))
    ov = rs.life_brief()["brief"]["wiki"]["overview"]
    # the LEAN key-set (NOT the full {inbox[],orphans[],...})
    assert set(ov) == {"stats", "proposalCount", "inboxCount", "inboxTop", "orphanCount",
                       "orphanTop", "recentActivity", "truncated"}
    assert ov["inboxCount"] == 5, "the COUNT, not the full list"
    assert len(ov["inboxTop"]) == 3, "top-3 stubs only"
    # stubs carry id/title/status — NO rawContent (the bloat)
    for stub in ov["inboxTop"]:
        assert set(stub) == {"id", "title", "status"}
        assert "rawContent" not in stub
    assert len(ov["recentActivity"]) <= 5
    assert ov["truncated"]["inboxOmitted"] == 2  # 5 - 3
    assert ov["truncated"]["fullDetailVia"] == "wiki_overview"  # point-don't-paste


def test_100_brief_wiki_section_is_small(app_db):
    """#100 the size teeth: the wiki section is now a fraction of the old ~23KB (counts + stubs, not
    41 full notes). On a seeded vault it's well under 3KB."""
    import json
    from modules.wiki import service as wsvc
    from modules.wiki.schema import NoteCreateInput
    for i in range(20):  # a chunky inbox — the old full-paste would be huge
        wsvc.create_note(NoteCreateInput(title=f"Note {i}", content=f"lots of raw body content {i} " * 30))
    wiki_section = rs.life_brief()["brief"]["wiki"]
    size = len(json.dumps(wiki_section))
    assert size < 3000, f"brief.wiki must be lean (<3KB), got {size} (the 23KB full-dump is gone)"


def test_100_standalone_wiki_overview_still_full(app_db):
    """#100 the source is NOT shrunk: the standalone read path still returns the FULL inbox (with
    rawContent) — only the BRIEF's projection is lean. The full-detail surface is unchanged."""
    from modules.wiki import service as wsvc
    from modules.wiki.schema import NoteCreateInput
    for i in range(4):
        wsvc.create_note(NoteCreateInput(title=f"Full {i}", content=f"body {i}"))
    data, _ = rs._wiki_overview()
    assert len(data["inbox"]) == 4, "the source overview keeps the FULL inbox"
    assert "rawContent" in data["inbox"][0], "the full source keeps rawContent (the brief drops it)"


def test_100_brief_wiki_honest_empty(app_db):
    """#100 empty vault → counts 0 + empty top-lists (honest, not a crash); the lean shape holds."""
    ov = rs.life_brief()["brief"]["wiki"]["overview"]
    assert ov["inboxCount"] == 0 and ov["inboxTop"] == []
    assert ov["orphanCount"] == 0 and ov["orphanTop"] == []
    assert ov["truncated"]["inboxOmitted"] == 0


def test_R2G1_new_sections_failsoft(app_db, monkeypatch):
    """Each new section is fail-soft: a down source → {error} for THAT section, the
    rest of the brief still assembles (no 500)."""
    monkeypatch.setattr(rs, "_brief_news", lambda: (_ for _ in ()).throw(RuntimeError("news down")))
    brief = rs.life_brief()["brief"]
    assert "error" in brief["news"] and brief["news"]["source"] == "news"
    # the others unaffected
    assert "error" not in brief["macro"] and "error" not in brief["wiki"]


# --------------------------------------------------------------------------- #
# LIFE-BRIEF-SENTIMENT (#66) — life_brief.macro surfaces the daily "market mood" #
# (Fear & Greed band + BTC dominance), read from the macro store the decision    #
# tower + market block already cite. honest-mirror is the load-bearing gate: a    #
# real point → value+band+source surfaced; no live point → honest available:false #
# (never a fabricated mood). ADDITIVE — the existing Fed/CPI/DXY section intact.   #
# --------------------------------------------------------------------------- #
def _seed_sentiment(value_fng=45.0, btcd=52.0, ts="2026-06-21", source="live"):
    """Seed a real F&G + BTC dominance point into the macro store (the snapshot routine's
    write, source='live' = real). record_point refuses source='mock' (#15), so this is the
    only way a sentiment point exists."""
    from modules.macro import store as macro_store
    macro_store.init_macro_tables()
    macro_store.record_point("fear_greed", value_fng, ts, source)
    macro_store.record_point("btc_dominance", btcd, ts, source)


def test_66_life_brief_macro_surfaces_sentiment_when_real(app_db):
    """HARD GATE: a real F&G value (45 → neutral band) seeded → life_brief.macro.sentiment
    surfaces it with value + band + asOf + source (the consumer-agent can read "market mood")."""
    _seed_sentiment(value_fng=45.0, btcd=52.0, ts="2026-06-21", source="live")
    macro = rs.life_brief()["brief"]["macro"]
    assert "error" not in macro
    sent = macro["sentiment"]
    fng = sent["fearGreed"]
    assert fng["available"] is True
    assert fng["value"] == 45.0
    assert fng["band"] == "neutral"            # 45 is the 45-55 neutral band (#44)
    assert fng["asOf"] == "2026-06-21" and fng["source"] == "live"   # agent can age + trust it
    btcd = sent["btcDominance"]
    assert btcd["available"] is True and btcd["value"] == 52.0 and btcd["source"] == "live"


def test_66_sentiment_band_tracks_value():
    """The band is the #44 3-band classifier: ≤44 fear · 45-55 neutral · ≥56 greed —
    distinguishing (a different value → a different band, not a constant)."""
    for value, expect in [(20.0, "fear"), (44.0, "fear"), (50.0, "neutral"),
                          (55.0, "neutral"), (56.0, "greed"), (90.0, "greed")]:
        from modules.macro import store as macro_store
        # pure classifier check via the same fn _brief_sentiment uses (single source of truth)
        from modules.market.service import _fng_status
        assert _fng_status(value) == expect, f"F&G {value} should be {expect}"


def test_66_life_brief_macro_sentiment_honest_when_no_live_point(app_db):
    """HARD GATE (honest-mirror): NO live F&G point (clean app, network off) → sentiment is
    honest available:false + value:None — NEVER a fabricated mood number. (record_point
    refuses source='mock' so an unprimed series simply has no row → honest unavailable.)"""
    macro = rs.life_brief()["brief"]["macro"]
    assert "error" not in macro
    sent = macro["sentiment"]
    assert sent["fearGreed"]["available"] is False
    assert sent["fearGreed"]["value"] is None and sent["fearGreed"]["band"] is None
    assert sent["fearGreed"]["source"] is None     # no source = no data, not a faked 'live'
    assert sent["btcDominance"]["available"] is False and sent["btcDominance"]["value"] is None


def test_66_sentiment_additive_macro_section_intact(app_db):
    """ADDITIVE: the existing Fed/CPI/DXY macro block still works alongside the new sentiment —
    no regression to the macro overview (the #66 OUT: don't break Fed/CPI/DXY/phase)."""
    macro = rs.life_brief()["brief"]["macro"]
    assert "macro" in macro and "sentiment" in macro          # both present
    inds = {i["indicator"] for i in macro["macro"]["indicators"]}
    assert {"fed_funds_rate", "cpi", "dxy"} <= inds           # the existing indicators survive


def test_66_sentiment_is_neutral_no_advice():
    """NEUTRAL: the sentiment block DESCRIBES the mood — no advice/forecast term leaks
    (a band label + a number, never 'buy the fear' etc.)."""
    _seed_sentiment(value_fng=20.0, btcd=60.0)   # extreme-fear-ish mood
    flat = json.dumps(rs._brief_sentiment()).lower()
    for banned in ("buy", "sell", "should", "recommend", "forecast", "will rise", "will fall"):
        assert banned not in flat, f"sentiment leaked an advice/forecast term: {banned}"


def test_66_daily_brief_has_no_macro_consumer():
    """recheck-all-consumers: daily_brief (modules/brief) is a PRIORITIES brief — it has NO
    macro section to enrich (rules = market/projects/claude/finance/alerts/reminders/tracing).
    This pins that #66's enrichment correctly lands ONLY on life_brief's macro section. If a
    macro rule is ever added to daily_brief, this test fails → wire the sentiment there too."""
    from modules.brief import service as brief_svc
    import inspect
    src = inspect.getsource(brief_svc.generate_brief)
    assert "macro" not in src and "sentiment" not in src, (
        "daily_brief gained a macro/sentiment element — surface #66 sentiment there too"
    )


# --------------------------------------------------------------------------- #
# FINANCE-AUDIT2 (#66) — life_brief surfaces an HONEST portfolio P&L            #
# The bug: life_brief.portfolio.pnlTotal showed a fake +$7 gain while the real  #
# per-coin loss was −$617. The brief is the agent's #1 surface — a TOTAL that    #
# lies about DIRECTION is the most dangerous finance gap. The fix surfaces the   #
# basis-known pnlTotal + a pnlScope so −X% on a few % of the book isn't misread.  #
# --------------------------------------------------------------------------- #
def test_AUDIT2_brief_portfolio_carries_pnlscope(app_db):
    """The portfolio section MUST carry pnlScope alongside pnlTotal — so an agent reading
    the brief knows how much of the book pnlTotal covers (can't misread a basis-known −X%
    as a whole-portfolio loss). On an empty book it's honest-null, but the KEY is present."""
    section = rs._brief_portfolio()
    assert "pnlTotal" in section and "pnlScope" in section, "brief must surface pnlScope"


def test_AUDIT2_brief_portfolio_pnltotal_honest_direction(isolated_paths, monkeypatch):
    """HONEST DIRECTION: seed a losing basis-known holding → the brief's pnlTotal reports
    the LOSS (negative), NOT a snapshot-cost ~$0/positive number. pnlScope labels coverage."""
    from modules.finance import service as fin
    from modules.finance.schema import HoldingInput
    from modules.market.schema import AssetQuote

    # no OKX override; mock the market quote so BTC is below cost (a real loss)
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (None, None))
    monkeypatch.setattr(fin.market_service, "get_quote",
                        lambda s: AssetQuote(symbol=s, name=s, assetClass="crypto", price=40000.0,
                                             currency="USD", ts="2026-06-06T00:00:00+00:00",
                                             source="coingecko") if s == "BTC" else None)
    fin.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))

    section = rs._brief_portfolio()
    assert section["pnlTotal"]["abs"] == -10000.0, "brief must report the real LOSS, not a fake gain"
    assert section["pnlTotal"]["abs"] < 0  # direction is a loss
    assert section["pnlScope"] is not None and section["pnlScope"]["basis"] == "known-cost-only"


# --------------------------------------------------------------------------- #
# FINANCE-FINISH G1 — the decision tower wired into life_brief (9th section)     #
# --------------------------------------------------------------------------- #
def test_G1_life_brief_has_decision_section(app_db):
    """HARD GATE 1: life_brief has a `decision` section with the tower fields + source tag."""
    brief = rs.life_brief()["brief"]
    assert "decision" in brief, "the decision tower must be a life_brief section"
    d = brief["decision"]
    assert d["source"] == "decision"
    assert "error" not in d, f"decision section errored on a clean app: {d.get('error')}"
    assert {"weight", "verdict", "bindingConstraint", "phase", "topGuardianAlert"} <= set(d)
    # weight is a number, verdict a neutral band, phase a state label
    assert isinstance(d["weight"], (int, float))
    assert d["verdict"] in ("strong", "moderate", "thin", "blind")


def test_G1_decision_section_failsoft_keeps_other_8(app_db, monkeypatch):
    """HARD GATE 2: a tower fn raising → life_brief.decision = {error} BUT the OTHER 8 sections
    still assemble (per-section fail-soft, NOT whole-brief failure)."""
    monkeypatch.setattr(rs, "_decision_weight",
                        lambda: (_ for _ in ()).throw(RuntimeError("tower down")))
    brief = rs.life_brief()["brief"]
    assert "error" in brief["decision"] and brief["decision"]["source"] == "decision"
    # the other 8 are unaffected (no error on the clean read paths)
    for section in ("portfolio", "market", "projects", "claude", "decisions", "macro", "news", "wiki"):
        assert "error" not in brief[section], f"{section} should be unaffected by a tower failure"


def test_G1_neutral_recheck_with_decision_section(app_db):
    """HARD GATE 3 (LOAD-BEARING): (1) the EXISTING brief-wide no-advice gate STILL passes WITH
    the decision section added; (2) the NEW decision section itself introduces no advice verb.
    Scoped: the brief-wide check uses the existing banned KEYS (recommendation/advice/signal/
    buy_sell/action); the decision-section check uses the imperative-verb set — both must hold.
    (We do NOT ban 'deploy' brief-wide: the portfolio section legitimately says 'UNDEPLOYED
    stablecoin', a NEUTRAL composition word, not an imperative — the existing neutral test
    already excludes it. The decision section is the new surface to guard.)"""
    import json as _json
    brief = rs.life_brief()["brief"]
    # (1) the existing brief-wide neutral gate (same banned set as test_life_brief_is_neutral)
    flat = _json.dumps(brief).lower()
    for banned in ("recommendation", "advice", "\"signal\"", "buy_sell", "\"action\":"):
        assert banned not in flat, f"brief leaked a non-neutral key/term: {banned}"
    # (2) the NEW decision section specifically — no imperative advice verb (word-boundary so
    # a substring like 'undeployed' can't false-trip). The section is band/state/question only.
    import re
    dec_flat = _json.dumps(brief["decision"]).lower()
    for verb in ("should", "buy", "sell", "rebalance", "deploy", "recommend", "must", "ought"):
        assert re.search(rf"\b{verb}\b", dec_flat) is None, \
            f"the decision section leaked an advice verb: {verb!r}"


def test_G1_additive_does_not_perturb_portfolio_section(app_db):
    """HARD GATE 4: an EXISTING section (portfolio) is byte-unchanged with the decision section
    added — adding decision composes alongside, it doesn't touch the other builders."""
    # build the portfolio section directly + via life_brief → identical
    direct = rs._section("finance", rs._brief_portfolio)
    via_brief = rs.life_brief()["brief"]["portfolio"]
    assert direct == via_brief, "the portfolio section changed when decision was added"


def test_G1_top_guardian_alert_honest_empty(app_db, monkeypatch):
    """honest-empty: no guardian alerts → topGuardianAlert is None (not a fabricated string)."""
    from modules.decision.schema import GuardianReport
    monkeypatch.setattr(rs, "_decision_guardian",
                        lambda: GuardianReport(alerts=[], confidence=1.0, asOf="2026-06-16T00:00:00+00:00", note="none"))
    d = rs.life_brief()["brief"]["decision"]
    assert d["topGuardianAlert"] is None


def test_NG1_life_brief_claude_pct_sane_cross_consumer(app_db):
    """NG1 cross-consumer proof: life_brief.brief.claude.pct must be ≤100 or None —
    NEVER the ~4500% used/cap overflow (the SYNTH leak the source-fix closes). This is
    the surface that leaked it; fixing claude_usage at the source auto-corrects it."""
    pct = rs.life_brief()["brief"]["claude"].get("pct")
    assert pct is None or pct <= 100.0


def test_NG4_check_proposal_status_bad_id_is_found_false(app_db):
    """NG4: a non-int / malformed proposal id → {found:false}, NOT a raw ValueError
    traceback leaked to the agent."""
    out = rs.check_proposal_status("nope123")  # type: ignore[arg-type]
    assert out["found"] is False
    # a valid-but-absent int id is still honest found:false
    assert rs.check_proposal_status(999999)["found"] is False


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
        assert set(a) >= {"symbol", "quote", "indicators", "isMock"}  # #92: +isMock tier-1 flag


# --------------------------------------------------------------------------- #
# #92 — life_brief market: mock-asset tier-1 isMock flag (mirror macro.DXY)      #
# --------------------------------------------------------------------------- #
def _patch_market(monkeypatch, quotes: list[dict]):
    """Make _brief_market see a known quote mix (mock + live) + the matching tracked assets, so the
    isMock discriminator is deterministic (not network-dependent)."""
    monkeypatch.setattr(rs, "_mkt_market", lambda: ({"quotes": quotes}, []))
    monkeypatch.setattr(rs, "_mkt_tracked", lambda: [{"symbol": q["symbol"]} for q in quotes])
    # neutralize the TA read (not under test here)
    monkeypatch.setattr(rs, "_mkt_indicators", lambda *a, **k: ({"indicators": None}, []))


def test_92_mock_asset_flagged_live_not_flagged(app_db, monkeypatch):
    """THE distinguishing teeth: a MOCK asset (source=mock) → isMock True at the ASSET level (no
    drilling quote.source); a LIVE asset (source=coingecko) → isMock False. A real discriminator."""
    _patch_market(monkeypatch, [
        {"symbol": "BTC", "source": "coingecko", "price": 60000},
        {"symbol": "VNINDEX", "source": "mock", "price": 1200},
    ])
    market = rs._brief_market()
    by_sym = {a["symbol"]: a for a in market["assets"]}
    assert by_sym["BTC"]["isMock"] is False, "a LIVE asset must NOT be isMock"
    assert by_sym["VNINDEX"]["isMock"] is True, "a MOCK asset MUST be isMock"


def test_92_top_level_warning_lists_mock_assets(app_db, monkeypatch):
    """Mirror macro.DXY: a top-level warning names the mock assets (unambiguous in one read)."""
    _patch_market(monkeypatch, [
        {"symbol": "BTC", "source": "coingecko"},
        {"symbol": "VNINDEX", "source": "mock"},
        {"symbol": "FUEVFVND", "source": "mock"},
    ])
    market = rs._brief_market()
    mock_warn = [w for w in market["warnings"] if "mock" in w.lower()]
    assert mock_warn, "a top-level mock warning must be present"
    assert "VNINDEX" in mock_warn[0] and "FUEVFVND" in mock_warn[0]
    assert "not live" in mock_warn[0].lower() or "not live data" in mock_warn[0].lower()


def test_92_mock_data_not_lost(app_db, monkeypatch):
    """honest-mirror: the mock asset's price/quote is STILL returned (marked, not removed)."""
    _patch_market(monkeypatch, [{"symbol": "VNINDEX", "source": "mock", "price": 1234}])
    a = rs._brief_market()["assets"][0]
    assert a["isMock"] is True
    assert a["quote"]["price"] == 1234, "the mock value is KEPT (tagged, not dropped)"


def test_92_no_mock_no_warning(app_db, monkeypatch):
    """All-live → isMock False everywhere + NO mock warning (the flag isn't a blanket)."""
    _patch_market(monkeypatch, [
        {"symbol": "BTC", "source": "coingecko"},
        {"symbol": "ETH", "source": "coingecko"},
    ])
    market = rs._brief_market()
    assert all(a["isMock"] is False for a in market["assets"])
    assert not [w for w in market["warnings"] if "mock (no live feed)" in w.lower()]


def test_92_none_quote_is_not_mock(app_db, monkeypatch):
    """A None quote (no data at all) → isMock False (a different honest case from a mock VALUE)."""
    monkeypatch.setattr(rs, "_mkt_market", lambda: ({"quotes": []}, []))   # no quotes
    monkeypatch.setattr(rs, "_mkt_tracked", lambda: [{"symbol": "NOQUOTE"}])
    monkeypatch.setattr(rs, "_mkt_indicators", lambda *a, **k: ({"indicators": None}, []))
    a = rs._brief_market()["assets"][0]
    assert a["quote"] is None and a["isMock"] is False  # no-quote ≠ mock-value


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

    p = ws.propose_quicknote("idea", "worth capturing")
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
    Derived from the live registries, so it cannot drift (the anti-hardcode guard).
    #32: backward-compat counts.read/write/total still mean the SHARED read/write servers."""
    from mcp_servers import write_server as ws

    cat = rs.list_tools_catalog()
    # backward-compat: read = shared read-server, write = shared write-server, total = both.
    assert cat["counts"]["read"] == len(rs.TOOLS)
    assert cat["counts"]["write"] == len(ws.TOOLS)
    assert cat["counts"]["total"] == len(rs.TOOLS) + len(ws.TOOLS)
    # the shared-server tools are present with the right labels (subset of the full all-mount list)
    listed = {(t["server"], t["name"]) for t in cat["tools"]}
    shared = {("read", n) for n in rs.TOOLS} | {("write", n) for n in ws.TOOLS}
    assert shared <= listed, f"catalog dropped shared-server tools: {shared - listed}"


def test_catalog_every_tool_has_description_and_fields(app_db):
    cat = rs.list_tools_catalog()
    valid_servers = {"read", "write", "wiki-read", "wiki-write", "finance", "reminders", "tracing"}
    for t in cat["tools"]:
        assert set(t) >= {"name", "server", "capability", "neutral", "description"}
        assert t["description"], f"{t['name']} has no description"
        assert t["server"] in valid_servers, f"{t['name']} on unknown server {t['server']}"
        assert t["capability"] in ("read", "propose")
        assert isinstance(t["neutral"], bool)
    json.dumps(cat)


# --------------------------------------------------------------------------- #
# #32 — catalog walks ALL mounts (read/write/wiki-read/wiki-write/finance/reminders) #
# --------------------------------------------------------------------------- #
def test_catalog_walks_all_mounts(app_db):
    """#32: the catalog enumerates EVERY mounted server, not just shared read+write. Each mount's
    live TOOLS appear under its server label — so an agent can discover the wiki/finance/reminders
    capabilities that the old (shared-only) catalog hid."""
    import importlib

    cat = rs.list_tools_catalog()
    listed = {(t["server"], t["name"]) for t in cat["tools"]}
    by_mount = cat["counts"]["byMount"]
    # every mount in the registry is represented with its FULL live tool set
    for label, mod_path, _cap in rs._CATALOG_MOUNTS:
        mod = importlib.import_module(mod_path)
        for name in mod.TOOLS:
            assert (label, name) in listed, f"catalog missing {label}/{name}"
        assert by_mount[label] == len(mod.TOOLS), f"byMount[{label}] != live TOOLS count"
    # the specific tools team-lead's verify names: wiki_context + the 11 wiki-read, finance, reminders
    assert ("wiki-read", "wiki_context") in listed
    assert by_mount["wiki-read"] == 15  # #34 +suggest_links #41 +stale #53 +reindex #35 +my_feedback (was 11)
    assert by_mount["wiki-write"] == 8  # #94: +wiki_delete_note +wiki_restore_note (was 6)
    assert by_mount["finance"] == 15
    assert by_mount["reminders"] == 4  # #111: +reminders_channels (was 3)


def test_catalog_mounts_in_sync_with_main(app_db):
    """The catalog's mount registry MUST mirror main._MCP_MOUNTS — so a NEW mount added to the app
    can't be silently missed by the catalog (it'd fail here until added to _CATALOG_MOUNTS too)."""
    import main
    catalog_modpaths = {mod_path for _label, mod_path, _cap in rs._CATALOG_MOUNTS}
    app_modpaths = {mod_path for _path, mod_path in main._MCP_MOUNTS}
    assert catalog_modpaths == app_modpaths, (
        f"catalog mount registry out of sync with main._MCP_MOUNTS: "
        f"only-in-catalog={catalog_modpaths - app_modpaths}, "
        f"only-in-app={app_modpaths - catalog_modpaths}"
    )


def test_catalog_finance_double_listed_under_read_and_finance(app_db):
    """The documented per-mount truth: a finance tool reference-imported by /mcp/finance appears
    under BOTH 'read' (the shared server has it) AND 'finance' (the domain server) — the honest
    'what THIS agent sees' view, NOT a bug. Assert at least one such tool is double-listed."""
    from mcp_servers import finance_server as fs

    cat = rs.list_tools_catalog()
    listed = {(t["server"], t["name"]) for t in cat["tools"]}
    # finance tools that are ALSO in the shared read server → must appear under both labels
    shared_finance = [n for n in fs.TOOLS if n in rs.TOOLS]
    assert shared_finance, "expected finance tools shared with the read server"
    for n in shared_finance:
        assert ("finance", n) in listed and ("read", n) in listed, \
            f"{n} should be listed under both 'finance' and 'read'"


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
    assert len(rs.TOOLS) == 49  # PROJECTS-UNIFY #112: +project_dev_activity (was 48; #111 +reminders_channels)


# =========================================================================== #
# CLAUDE-USAGE-LEAN (#18) — the claude_usage MCP tool is LEAN by default,        #
# verbose=true for the full splits. Lead with the live quota signal; costUSD     #
# $.01; remaining stays honest-null WITH a reason note (the dxy.warning pattern). #
# =========================================================================== #
_FULL_USAGE = {
    "model": "opus-4-8", "used": 3_000_000, "cap": 200_000, "pct": None,
    "remaining": None, "resetIn": "3h 18m", "weekly": 12, "pct5h": 17.0,
    "resetWeek": "5d", "ctxPct": 40.0, "ctxUsed": 80_000, "ctxMax": 200_000,
    "ctxModel": "opus", "quotaSource": "snapshot",
    "series": [{"date": "2026-06-21", "label": "T7", "tokens": 3_000_000}],
    "today": 3_000_000, "avgPerDay": 2_500_000,
    "peak": {"date": "2026-06-20", "label": "T6", "tokens": 4_000_000},
    "byModel": [{"model": "opus-4-8", "inputTokens": 1, "outputTokens": 2, "cacheReadTokens": 0,
                 "cacheCreateTokens": 0, "total": 3, "costUSD": 53627.535}],
    "costUSD": 53627.535,
    "byProject": [{"project": "life-os", "inputTokens": 1, "outputTokens": 2, "cacheReadTokens": 0,
                   "cacheCreateTokens": 0, "total": 3, "costUSD": 100.0, "msgs": 5}],
    "tokenSource": "stats-cache", "asOf": "2026-06-21", "stale": False, "source": "stats-cache",
}


def _patch_usage(monkeypatch, overrides=None):
    """Patch rs._claude_usage to return a controlled full-usage dict (passes through _jsonable)."""
    data = dict(_FULL_USAGE)
    if overrides:
        data.update(overrides)
    monkeypatch.setattr(rs, "_claude_usage", lambda window="5h": data)


def test_claude_usage_lean_by_default(monkeypatch):
    """DEFAULT → LEAN: has the live quota signal (pct5h/resetIn/weekly/today/costUSDAllTime); does
    NOT have the heavy splits (series/byModel/byProject/ctx*). Materially smaller than the 4325-char
    full dump."""
    import json as _json
    _patch_usage(monkeypatch)
    out = rs.claude_usage()
    assert out["verbose"] is False
    u = out["usage"]
    # the live quota signal + the few numbers an agent wants
    for k in ("pct5h", "resetIn", "weekly", "today", "costUSDAllTime"):
        assert k in u, f"lean must keep {k}"
    # #43: the lean cost key is costUSDAllTime (lifetime) — NOT a bare costUSD (would misread as today)
    assert "costUSD" not in u, "lean must NOT carry a bare costUSD (misreads as today-cost)"
    assert u["pct5h"] == 17.0 and u["resetIn"] == "3h 18m"  # leads with the live signal
    # the heavy splits are DROPPED from the default
    for k in ("series", "byModel", "byProject", "ctxPct", "ctxUsed", "ctxMax"):
        assert k not in u, f"lean must DROP {k}"
    # materially smaller
    assert len(_json.dumps(out)) < 800, "lean must be far smaller than the ~4325-char full dump"


def test_claude_usage_verbose_is_full(monkeypatch):
    """verbose=true → FULL: the per-day series + by-model + by-project splits are present."""
    _patch_usage(monkeypatch)
    out = rs.claude_usage(verbose=True)
    assert out["verbose"] is True
    u = out["usage"]
    for k in ("series", "byModel", "byProject", "ctxPct", "used", "cap", "asOf"):
        assert k in u, f"verbose must keep {k}"


def test_claude_usage_cost_formatted_two_decimals(monkeypatch):
    """cost is formatted to 2 decimals (cumulative magnitude is a known item — just format).
    #43: the LEAN key is costUSDAllTime (lifetime, clearly labeled); the VERBOSE key stays costUSD
    (the documented full-model field FE/REST consume). Same value, distinct keys per surface."""
    _patch_usage(monkeypatch, {"costUSD": 53627.53499})
    lean = rs.claude_usage()["usage"]
    verbose = rs.claude_usage(verbose=True)["usage"]
    assert lean["costUSDAllTime"] == 53627.53 and "costUSD" not in lean  # lean = renamed, no bare costUSD
    assert verbose["costUSD"] == 53627.53  # verbose = unchanged full-model field


def test_claude_usage_remaining_null_has_reason_note(monkeypatch):
    """AMENDMENT (the dxy.warning pattern): remaining is null because cap is a PLACEHOLDER
    (used > cap), NOT because quota is exhausted → a remainingNote names the real signal
    (pct5h/resetIn) so the agent isn't confused by the bare null."""
    _patch_usage(monkeypatch, {"remaining": None, "cap": 200_000, "used": 3_000_000})
    u = rs.claude_usage()["usage"]
    assert u["remaining"] is None, "remaining stays honest-null (never faked from a placeholder cap)"
    assert "remainingNote" in u and u["remainingNote"], "a null remaining must carry its reason"
    low = u["remainingNote"].lower()
    assert "pct5h" in low and "resetin" in low, "the note must point to the real live signal"


def test_claude_usage_real_cap_computes_remaining_no_note(monkeypatch):
    """The distinguishing other side: a real manual-override cap with used ≤ cap → remaining
    COMPUTES (non-null) → NO spurious note (the note is ONLY for the placeholder-cap null case)."""
    _patch_usage(monkeypatch, {"remaining": 50_000, "cap": 200_000, "used": 150_000})
    u = rs.claude_usage()["usage"]
    assert u["remaining"] == 50_000, "a real remaining is surfaced"
    assert "remainingNote" not in u, "no note when remaining genuinely computes"


def test_claude_usage_envelope_key_unchanged(monkeypatch):
    """Both lean + verbose keep the documented ``usage`` envelope key (the nullary-tool parity
    test + life_brief's section contract depend on it)."""
    _patch_usage(monkeypatch)
    assert "usage" in rs.claude_usage()
    assert "usage" in rs.claude_usage(verbose=True)
