"""tests/test_finance_mcp_shape.py — FINANCE-MCP-SHAPE (Task #50).

T1: the finance_analytics MCP read tool (mirror of finance_simulate/finance_overview) —
callable, correct {analytics, warnings} envelope, JSON-serialisable, empty portfolio →
zeroed/None metrics (no crash), and the read-server TOOLS count is 41.

T2: the _finance_warnings() DRY refactor is BYTE-IDENTICAL — the warnings list emitted by
get_overview / get_analytics / get_channel-detail / simulate must EQUAL (list ==, order
included) the pre-refactor output. Behavior-tested on a fixture that triggers gp + price +
drift warnings (memory behavior-test-not-field-read: exercise the OUTPUT, not "helper
exists"). The expected lists are the captured pre-refactor baseline.
"""

from __future__ import annotations

import json

import pytest

from modules.finance import service as fin
from modules.finance.schema import HoldingInput


# --------------------------------------------------------------------------- #
# T1 — finance_analytics MCP read tool                                          #
# --------------------------------------------------------------------------- #
@pytest.fixture
def app_db(isolated_paths):
    """Initialised wiki/proposal tables (read_server's reliability path queries them);
    everything else is file-store/SQLite-lazy + fail-open on empty."""
    from modules.wiki import store as wiki_store
    from modules.wiki import proposals_store as pstore
    from mcp_servers import proposals_store as agent_pstore
    wiki_store.init_wiki_tables()
    pstore.init_proposal_tables()
    agent_pstore.init_proposal_tables()
    return isolated_paths


def test_finance_analytics_tool_registered_and_count(app_db):
    """finance_analytics is in the read-server registry; total tool count is 42 (PROJECT-MEMORY #42
    added project_context; #28 added reminders_list; was 40 after MCP-DEDUP #70 removed 6 wiki dups)."""
    from mcp_servers import read_server as rs
    assert "finance_analytics" in rs.TOOLS
    assert len(rs.TOOLS) == 49  # PROJECTS-UNIFY #112: +project_dev_activity (was 48; #111 +reminders_channels)


def test_finance_analytics_envelope_and_jsonable(app_db, monkeypatch):
    """The tool returns {analytics, warnings}; analytics carries the PortfolioAnalytics shape;
    JSON-serialisable; an empty portfolio → zeroed/None metrics, no crash."""
    from mcp_servers import read_server as rs
    # isolate OKX so the empty tmp portfolio really is empty (the dev box has a live OKX snap)
    from modules.exchange.schema import ExchangeOverview
    monkeypatch.setattr(fin.exchange_service, "get_overview",
                        lambda: (ExchangeOverview(configured=False, totalUsdValue=0.0, balances=[]), None))
    out = rs.finance_analytics()
    assert set(out) >= {"analytics", "warnings"}
    assert isinstance(out["warnings"], list)
    a = out["analytics"]
    assert {"totalValue", "rebalance", "risk", "returns", "asOf"} <= set(a)
    assert a["totalValue"] == 0.0                       # empty portfolio
    assert a["risk"]["holdingCount"] == 0               # zeroed, not a crash
    assert a["risk"]["hhi"] is None                     # None (honest), no div-0
    json.dumps(out)                                     # serialisable over the wire


def test_finance_analytics_is_neutral_no_advice(app_db, monkeypatch):
    """NEUTRAL data only — no advice/recommendation key leaks (rebalance amounts are numbers,
    not 'you should buy')."""
    from mcp_servers import read_server as rs
    from modules.finance.schema import HoldingInput
    from modules.market.schema import AssetQuote
    monkeypatch.setattr(fin.market_service, "get_quote",
                        lambda s: AssetQuote(symbol=s, name=s, assetClass="crypto", price=100.0,
                                             currency="USD", ts="2026-06-16T00:00:00+00:00",
                                             source="mock"))
    fin.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))
    flat = json.dumps(rs.finance_analytics()).lower()
    for banned in ("recommendation", "\"advice\"", "buy_sell", "\"action\": \"recommend\""):
        assert banned not in flat, f"finance_analytics leaked a non-neutral term: {banned}"


def test_finance_analytics_capability_gate_no_write_leak(app_db):
    """finance_analytics imports only the read fn get_analytics → no write symbol reachable
    (the read-server's no-write gate auto-holds)."""
    from mcp_servers import read_server as rs
    ns = set(vars(rs))
    for w in ("set_golden_path", "upsert_holding", "delete_holding", "set_crypto_basis"):
        assert w not in ns, f"finance_analytics leaked a write symbol: {w}"
    # and the read fn IS bound, aliased-private
    assert "_fin_analytics" in ns


# --------------------------------------------------------------------------- #
# T2 — _finance_warnings() refactor is BYTE-IDENTICAL (the HARD LOCK)            #
# --------------------------------------------------------------------------- #
@pytest.fixture
def warn_fixture(isolated_paths, monkeypatch):
    """A portfolio that triggers gp (golden-path absent → baseline) + price (no-quote cost-
    fallback) + drift warnings across overview/analytics/channel/simulate. OKX off so it's
    deterministic; every symbol unpriced → the cost-fallback warning fires per holding."""
    from modules.exchange.schema import ExchangeOverview
    monkeypatch.setattr(fin.exchange_service, "get_overview",
                        lambda: (ExchangeOverview(configured=False, totalUsdValue=0.0, balances=[]), None))
    monkeypatch.setattr(fin.market_service, "get_quote", lambda s: None)  # all → cost-fallback
    fin.upsert_holding(HoldingInput(symbol="GHOST", channel="crypto", qty=1, avgCost=5))
    fin.upsert_holding(HoldingInput(symbol="ZZZ", channel="etf", qty=2, avgCost=3))
    return isolated_paths


# The byte-identical anchor (REST≡MCP parity HARD LOCK). Both surfaces emit this EXACT list/order.
# #106: the noisy per-channel drift WARNING now fires ONLY at |drift|>30% (WARNING_DRIFT_PCT) — the
# precise >5% signal lives on the structured driftAlert FIELD (unchanged). So of this fixture's four
# drifts (crypto +7.5%, dry -20%, etf +30.6%, vn -18%) only etf (+30.6% > 30) keeps a WARNING; the
# other three are suppressed boilerplate. (4 drift warnings → 1: exactly the #106 noise cut.)
_BASE_OVERVIEW = [
    "golden-path absent — using baseline targets (crypto38/etf24/vn18/dry20)",
    "GHOST: no market price — using avgCost",
    "ZZZ: no market price — using avgCost",
    "etf: allocation drift +30.6% (target 24.0%, actual 54.55%)",
]
_BASE_ANALYTICS = _BASE_OVERVIEW + ["no portfolio value series yet — return/volatility unavailable"]
_BASE_CHANNEL = _BASE_OVERVIEW[:3]   # gp + the two price warnings (no drift/okx on the detail path)
_BASE_SIMULATE = _BASE_OVERVIEW      # gp + price + drift (simulate folds in _current_channel_pct's overview warnings)


def test_overview_warnings_byte_identical(warn_fixture):
    _, w = fin.get_overview()
    assert w == _BASE_OVERVIEW, f"overview warnings changed:\n{w}"


def test_analytics_warnings_byte_identical(warn_fixture):
    _, w = fin.get_analytics()
    assert w == _BASE_ANALYTICS, f"analytics warnings changed:\n{w}"


def test_channel_detail_warnings_byte_identical(warn_fixture):
    _, w = fin.get_channel("crypto")
    assert w == _BASE_CHANNEL, f"channel-detail warnings changed:\n{w}"


def test_simulate_warnings_byte_identical(warn_fixture):
    _, w = fin.simulate({"crypto": 60, "etf": 40})
    assert w == _BASE_SIMULATE, f"simulate warnings changed:\n{w}"


def test_finance_warnings_helper_returns_shared_prefix(warn_fixture):
    """The helper returns (targets, ladder, by_channel, warnings) and its warnings == the
    gp+price prefix (the first 3 entries of the overview list, before drift is appended)."""
    holdings = fin.list_holdings()
    targets, ladder, by_channel, warnings = fin._finance_warnings(holdings)
    assert isinstance(targets, dict) and isinstance(by_channel, dict)
    # the shared prefix = golden-path absent + the two cost-fallback price warnings
    assert warnings == _BASE_OVERVIEW[:3]


def test_refactor_did_not_change_brief_consumer(warn_fixture):
    """(d) brief unaffected: the read-server _brief_portfolio still surfaces overview warnings
    (the refactor changed the SOURCE path, not the output) — its warnings flow unchanged."""
    from mcp_servers import read_server as rs
    portfolio = rs._brief_portfolio()
    # _brief_portfolio carries overview's warnings list through — same gp+price prefix present
    assert "golden-path absent — using baseline targets (crypto38/etf24/vn18/dry20)" in portfolio["warnings"]


# --------------------------------------------------------------------------- #
# Byte-identical WITH an OKX warning (team-lead ask: cover the okx warn too —    #
# it's appended AFTER the helper's gp+price prefix, NOT routed through the       #
# helper; this proves the refactor didn't disturb the okx-append order/position) #
# --------------------------------------------------------------------------- #
@pytest.fixture
def okx_warn_fixture(isolated_paths, monkeypatch):
    """A portfolio where OKX is live AND emits a warning (deterministically patched), so the
    okx_warn line is present in the overview/channel warnings — alongside gp + price + drift.
    A richer case than warn_fixture: a refactor that dropped/reordered the okx append would
    fail here even though warn_fixture (okx off) would pass (verify-with-the-distinguishing-case)."""
    monkeypatch.setattr(fin, "_okx_crypto_value",
                        lambda: (5000.0, "OKX: balances stale (>1h) — showing cached"))
    monkeypatch.setattr(fin, "_okx_crypto_holdings", lambda: None)  # fail-soft → keep manual
    monkeypatch.setattr(fin, "_ensure_crypto_basis", lambda v: 4800.0)
    monkeypatch.setattr(fin.market_service, "get_quote", lambda s: None)  # cost-fallback warns
    fin.upsert_holding(HoldingInput(symbol="GHOST", channel="crypto", qty=1, avgCost=5))
    fin.upsert_holding(HoldingInput(symbol="ZZZ", channel="etf", qty=2, avgCost=3))
    return isolated_paths


# Baselines WITH the okx warning present (the okx line sits AFTER the gp+price prefix the helper
# owns, BEFORE the drift warnings — proving append-order intact). #106: of the four drifts only
# crypto (+61.9% > 30 WARNING_DRIFT_PCT) keeps a WARNING; dry/etf/vn (-20/-23.9/-18, all ≤30) are
# suppressed boilerplate. The okx-line position relative to the (now single) drift warning is intact.
_OKX_BASE_OVERVIEW = [
    "golden-path absent — using baseline targets (crypto38/etf24/vn18/dry20)",
    "GHOST: no market price — using avgCost",
    "ZZZ: no market price — using avgCost",
    "OKX: balances stale (>1h) — showing cached",
    "crypto: allocation drift +61.9% (target 38.0%, actual 99.88%)",
]
_OKX_BASE_CHANNEL = [
    "golden-path absent — using baseline targets (crypto38/etf24/vn18/dry20)",
    "GHOST: no market price — using avgCost",
    "ZZZ: no market price — using avgCost",
    "OKX: balances stale (>1h) — showing cached",
]


def test_overview_warnings_byte_identical_with_okx(okx_warn_fixture):
    _, w = fin.get_overview()
    assert w == _OKX_BASE_OVERVIEW, f"overview warnings (okx) changed:\n{w}"


def test_channel_warnings_byte_identical_with_okx(okx_warn_fixture):
    _, w = fin.get_channel("crypto")
    assert w == _OKX_BASE_CHANNEL, f"channel warnings (okx) changed:\n{w}"
