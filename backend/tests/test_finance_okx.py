"""tests/test_finance_okx.py — OKX-FINANCE: per-coin balances → crypto holdings (G2).

THE invariants (architect/plan):
  - per-coin VALUE-ONLY: OKX balances become crypto holdings with avgCost=None +
    honest-null per-coin P&L (OKX has no per-coin cost basis — never fabricate a 0-cost).
  - NO double-count: OKX REPLACES manual crypto holdings; manual etf/vn/dry untouched.
  - FAIL-SOFT: OKX down/unconfigured → fall back to manual holdings; overview never breaks.
  - aggregate crypto-channel P&L still works (existing OKX-total-vs-snapshot wiring).
  - Holding.avgCost is OPTIONAL (round-trips None).

Mocks exchange_service.get_overview to feed a configured snapshot with balances.
"""

from __future__ import annotations

import pytest

from modules.finance import service
from modules.finance.schema import Holding, HoldingInput
from modules.exchange.schema import ExchangeOverview, OkxBalance


def _okx_snapshot(balances, total, configured=True):
    return ExchangeOverview(
        configured=configured,
        totalUsdValue=total,
        balances=balances,
    ), None


@pytest.fixture
def mock_okx(monkeypatch):
    """Patch exchange_service.get_overview to return a configured OKX snapshot."""
    def _set(balances, total):
        monkeypatch.setattr(service.exchange_service, "get_overview",
                            lambda: _okx_snapshot(balances, total))
    return _set


@pytest.fixture
def mock_prices(monkeypatch):
    monkeypatch.setattr(service.market_service, "get_quote", lambda s: None)  # no manual quotes needed


# --------------------------------------------------------------------------- #
# schema: avgCost optional                                                      #
# --------------------------------------------------------------------------- #
def test_holding_avgcost_optional():
    h = Holding(channel="crypto", symbol="BTC", qty=0.5, source="okx")
    assert h.avgCost is None  # value-only OKX entry — no fabricated cost


# --------------------------------------------------------------------------- #
# per-coin merge: value-only + honest-null P&L                                  #
# --------------------------------------------------------------------------- #
def test_okx_per_coin_holdings_value_only(mock_okx, mock_prices, isolated_paths):
    mock_okx([
        OkxBalance(symbol="BTC", available=0.5, frozen=0.0, total=0.5, usdValue=30000.0),
        OkxBalance(symbol="ETH", available=4.0, frozen=0.0, total=4.0, usdValue=12000.0),
    ], total=42000.0)
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    # the flat holdings list now has the OKX per-coin crypto holdings (value-only)
    crypto_h = [h for h in overview.holdings if h.channel == "crypto"]
    syms = {h.symbol for h in crypto_h}
    assert {"BTC", "ETH"} <= syms
    for h in crypto_h:
        assert h.avgCost is None and h.source == "okx"  # value-only, no fabricated cost


def test_okx_per_coin_pnl_is_honest_null(mock_okx, mock_prices, isolated_paths):
    mock_okx([OkxBalance(symbol="BTC", available=0.5, frozen=0.0, total=0.5, usdValue=30000.0)],
             total=30000.0)
    ch, _ = service.get_channel("crypto")
    entry = next(e for e in ch["holdings"] if e["holding"]["symbol"] == "BTC")
    assert entry["pnl"] is None  # honest-null — no per-coin cost basis, never a fake gain
    assert entry["value"] == 30000.0


# --------------------------------------------------------------------------- #
# no double-count: OKX replaces manual crypto; manual non-crypto untouched      #
# --------------------------------------------------------------------------- #
def test_okx_replaces_manual_crypto_keeps_non_crypto(mock_okx, mock_prices, isolated_paths):
    # seed manual holdings: a manual crypto (should be REPLACED) + manual etf (KEPT).
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DOGE", qty=1000, avgCost=0.1))
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=10, avgCost=400))
    mock_okx([OkxBalance(symbol="BTC", available=1.0, frozen=0.0, total=1.0, usdValue=60000.0)],
             total=60000.0)
    overview, _ = service.get_overview()
    crypto_syms = {h.symbol for h in overview.holdings if h.channel == "crypto"}
    etf_syms = {h.symbol for h in overview.holdings if h.channel == "etf"}
    assert crypto_syms == {"BTC"}          # OKX replaced manual DOGE (no double-count)
    assert "DOGE" not in crypto_syms
    assert "VOO" in etf_syms                # manual non-crypto UNTOUCHED


# --------------------------------------------------------------------------- #
# fail-soft: OKX down/unconfigured → manual holdings, never breaks              #
# --------------------------------------------------------------------------- #
def test_okx_unconfigured_falls_back_to_manual(monkeypatch, mock_prices, isolated_paths):
    monkeypatch.setattr(service.exchange_service, "get_overview",
                        lambda: (ExchangeOverview(configured=False, totalUsdValue=0.0, balances=[]), None))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DOGE", qty=1000, avgCost=0.1))
    overview, _ = service.get_overview()  # MUST NOT raise
    # OKX off → manual crypto holding kept
    assert {h.symbol for h in overview.holdings if h.channel == "crypto"} == {"DOGE"}


def test_okx_raises_fails_soft(monkeypatch, mock_prices, isolated_paths):
    def boom():
        raise RuntimeError("OKX API down")
    monkeypatch.setattr(service.exchange_service, "get_overview", boom)
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DOGE", qty=1000, avgCost=0.1))
    overview, _ = service.get_overview()  # fail-soft — no 500
    assert {h.symbol for h in overview.holdings if h.channel == "crypto"} == {"DOGE"}


# --------------------------------------------------------------------------- #
# aggregate channel P&L still works (existing OKX-total-vs-snapshot)            #
# --------------------------------------------------------------------------- #
def test_aggregate_crypto_pnl_still_works(mock_okx, mock_prices, isolated_paths):
    mock_okx([OkxBalance(symbol="BTC", available=1.0, frozen=0.0, total=1.0, usdValue=60000.0)],
             total=60000.0)
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    # the CHANNEL-level pnl is computed (value vs the snapshot cost basis) — not null,
    # even though per-coin pnl is null. Aggregate "is my crypto up/down" still answerable.
    assert crypto.value == 60000.0
    assert crypto.pnl is not None and crypto.pnl.current == 60000.0


def test_okx_skips_unvalued_coin(mock_okx, mock_prices, isolated_paths):
    # a coin with usdValue None (can't value) is skipped — not a fabricated 0.
    mock_okx([
        OkxBalance(symbol="BTC", available=1.0, frozen=0.0, total=1.0, usdValue=60000.0),
        OkxBalance(symbol="XYZ", available=5.0, frozen=0.0, total=5.0, usdValue=None),
    ], total=60000.0)
    overview, _ = service.get_overview()
    crypto_syms = {h.symbol for h in overview.holdings if h.channel == "crypto"}
    assert crypto_syms == {"BTC"} and "XYZ" not in crypto_syms
