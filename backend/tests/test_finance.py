"""tests/test_finance.py — finance schema + service (Sprint 4, SPEC §S5/§S6).

Behavior-test math: set holdings + a mocked market price → assert derived numbers
against HAND-CALC (not field-reads). Market quotes mocked (no real CoinGecko).
"""

from __future__ import annotations

import pytest

from modules.finance import service
from modules.finance.schema import GoldenPathInput, HoldingInput
from modules.market.schema import AssetQuote


def _mock_quote(symbol, price):
    return AssetQuote(symbol=symbol, name=symbol, assetClass="crypto",
                      price=price, currency="USD", ts="2026-06-06T00:00:00+00:00", source="coingecko")


@pytest.fixture(autouse=True)
def no_okx_override(monkeypatch):
    """Disable OKX override for all finance unit tests.

    test_finance.py tests manual-holdings logic in isolation. If OKX is configured
    in the local env (which it is — live $10k snapshot in cache), _okx_crypto_value()
    would override the crypto channel value and break every hand-calc assertion.
    Patch it to return (None, None) — i.e. "not configured / no value" — so tests
    exercise the manual pricing path exclusively.
    """
    monkeypatch.setattr(service, "_okx_crypto_value", lambda: (None, None))


@pytest.fixture
def mock_prices(monkeypatch):
    book: dict[str, float] = {}

    def fake_get_quote(symbol):
        return _mock_quote(symbol, book[symbol]) if symbol in book else None

    monkeypatch.setattr(service.market_service, "get_quote", fake_get_quote)
    return book


# --- holdings persistence (upsert by symbol) ---
def test_upsert_list_delete_holdings(isolated_paths):
    assert service.list_holdings() == []
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1.0, avgCost=50000))
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=10, avgCost=400))
    assert len(service.list_holdings()) == 2
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=2.0, avgCost=55000))
    btc = [h for h in service.list_holdings() if h.symbol == "BTC"]
    assert len(btc) == 1 and btc[0].qty == 2.0
    assert service.delete_holding("BTC") is True
    assert all(h.symbol != "BTC" for h in service.list_holdings())
    assert service.delete_holding("BTC") is False


def test_malformed_holdings_md_ignored(isolated_paths):
    from store import md_store
    md_store.write_file(service.HOLDINGS_MD, "---\nholdings: : : bad\n---\n", "bad")
    assert service.list_holdings() == []


# --- golden path baseline ---
def test_golden_path_baseline_when_absent(isolated_paths):
    targets, ladder, warnings = service.get_golden_path()
    assert targets == {"crypto": 38.0, "etf": 24.0, "vn": 18.0, "dry": 20.0}
    assert ladder == {}
    assert any("baseline" in w for w in warnings)


def test_golden_path_set_and_get(isolated_paths):
    service.set_golden_path(GoldenPathInput(
        targets={"crypto": 50, "dry": 50},
        ladder={"crypto": {"reference": 60000, "rungs": [-10, -20]}},
    ))
    targets, ladder, warnings = service.get_golden_path()
    assert targets == {"crypto": 50.0, "dry": 50.0}
    assert ladder["crypto"]["reference"] == 60000
    assert warnings == []


# --- P&L math ---
def test_pnl_math():
    pnl = service._pnl(cost=1000.0, current=1200.0)
    assert pnl.abs == 200.0 and pnl.pct == 20.0
    assert pnl.cost == 1000.0 and pnl.current == 1200.0


def test_pnl_pct_none_when_cost_zero():
    pnl = service._pnl(cost=0.0, current=500.0)
    assert pnl.pct is None and pnl.abs == 500.0


# --- overview hand-calc ---
def test_overview_value_pnl_drift_handcalc(isolated_paths, mock_prices):
    mock_prices["BTC"] = 60000.0
    mock_prices["VOO"] = 450.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=10, avgCost=400))
    overview, warnings = service.get_overview()
    assert overview.totalValue == 64500.0
    assert overview.pnlTotal.abs == 10500.0
    assert overview.pnlTotal.pct == round(10500 / 54000 * 100, 2)
    assert len(overview.holdings) == 2  # holdings list included
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.pct == round(60000 / 64500 * 100, 2)
    assert crypto.drift == round(crypto.pct - 38.0, 2)
    assert crypto.driftAlert is True  # 93% vs 38% → |drift|>5
    assert crypto.pnl.abs == 10000.0


def test_overview_drift_alert_false_when_on_target(isolated_paths, mock_prices):
    # single crypto holding at exactly... make crypto ≈ its 38% target is hard with one
    # holding; instead test driftAlert=False path with a near-target setup.
    service.set_golden_path(GoldenPathInput(targets={"crypto": 100.0}, ladder={}))
    mock_prices["BTC"] = 50000.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.pct == 100.0 and crypto.target == 100.0
    assert crypto.drift == 0.0 and crypto.driftAlert is False


def test_overview_empty_no_div0(isolated_paths, mock_prices):
    overview, _ = service.get_overview()
    assert overview.totalValue == 0.0
    assert overview.pnlTotal.pct is None
    assert overview.change is None


def test_overview_price_fail_open_uses_cost(isolated_paths, mock_prices):
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    overview, warnings = service.get_overview()
    assert overview.totalValue == 50000.0
    assert any("no market price" in w for w in warnings)


def test_overview_fail_open_on_stale_stored_channel(isolated_paths, mock_prices):
    """Reactive S4 bug: a stored golden_path with a channel from an OLD naming
    (e.g. 'cash' before cash→dry) must NOT 500 the overview. Skip it + warn;
    valid channels still computed. RED without the CHANNELS guard in get_overview."""
    from store import md_store
    # stale stored target carrying the retired 'cash' channel + a junk one
    md_store.write_file(
        service.GOLDEN_PATH_MD,
        "---\ntargets:\n  crypto: 38\n  cash: 20\n  bogus: 5\n  dry: 20\nladder: {}\n---\n",
        "stale golden path",
    )
    mock_prices["BTC"] = 60000.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))

    overview, warnings = service.get_overview()  # MUST NOT raise
    chans = sorted(a.channel for a in overview.allocations)
    assert "cash" not in chans and "bogus" not in chans, f"unknown channels leaked: {chans}"
    assert "crypto" in chans  # valid channel still computed
    assert any("unknown stored channel 'cash'" in w for w in warnings)
    assert any("unknown stored channel 'bogus'" in w for w in warnings)
    # valid math still correct
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.pnl.abs == 10000.0


def test_dry_powder_is_dry_channel(isolated_paths, mock_prices):
    mock_prices["USDC"] = 1.0
    service.upsert_holding(HoldingInput(channel="dry", symbol="USDC", qty=10000, avgCost=1.0))
    overview, _ = service.get_overview()
    assert overview.dryPowder == 10000.0


# --- ladder hand-calc ---
def test_ladder_rungs_and_distance():
    # reference 100, rungs -10/-20/-30 → triggers 90/80/70. current 85.
    ladder = service._ladder_for("crypto", reference=100.0, current=85.0, rungs=[-10.0, -20.0, -30.0])
    # entered: triggers ≥ 85 → only 90 → rungsIn=1
    assert ladder.rungsIn == 1
    # next not-entered: first trigger below 85 (current>trigger) = 80 (-20%)
    assert ladder.nextRung == {"pct": -20.0, "triggerPrice": 80.0}
    assert ladder.distancePct == round((85 - 80) / 85 * 100, 2)
    assert ladder.referencePrice == 100.0 and ladder.currentPrice == 85.0


def test_ladder_all_entered():
    ladder = service._ladder_for("crypto", reference=100.0, current=60.0, rungs=[-10.0, -20.0, -30.0])
    assert ladder.rungsIn == 3  # 90,80,70 all ≥ 60
    assert ladder.nextRung is None and ladder.distancePct is None


def test_ladder_none_entered():
    ladder = service._ladder_for("crypto", reference=100.0, current=95.0, rungs=[-10.0, -20.0, -30.0])
    assert ladder.rungsIn == 0
    assert ladder.nextRung == {"pct": -10.0, "triggerPrice": 90.0}


# --- channel detail ---
def test_get_channel_detail_with_ladder(isolated_paths, mock_prices):
    mock_prices["BTC"] = 90.0
    service.set_golden_path(GoldenPathInput(
        targets={"crypto": 100.0},
        ladder={"crypto": {"reference": 100.0, "rungs": [-10.0, -20.0]}},
    ))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=100))
    detail, warnings = service.get_channel("crypto")
    assert detail is not None
    assert detail["channel"] == "crypto"
    assert detail["alloc"]["value"] == 90.0
    # ladder: ref 100, current 90 → trigger 90 entered (rungsIn=1), next 80
    assert detail["ladder"]["rungsIn"] == 1
    assert detail["ladder"]["nextRung"]["triggerPrice"] == 80.0


def test_get_channel_unknown_returns_none(isolated_paths, mock_prices):
    detail, _ = service.get_channel("notachannel")
    assert detail is None


def test_get_channel_target_only_no_holdings(isolated_paths, mock_prices):
    detail, _ = service.get_channel("vn")  # baseline target, no holdings
    assert detail is not None
    assert detail["alloc"]["target"] == 18.0 and detail["alloc"]["value"] == 0.0
    assert detail["ladder"] is None  # no golden_path ladder config


# --- crypto basis ---

def test_get_crypto_basis_unset(isolated_paths):
    """Before any OKX call, basis is None and source is 'unset'."""
    basis, source = service.get_crypto_basis()
    assert basis is None
    assert source == "unset"


def test_ensure_crypto_basis_snapshots_on_first_call(isolated_paths):
    """_ensure_crypto_basis snapshots okx_total when basis not yet set."""
    result = service._ensure_crypto_basis(10000.0)
    assert result == 10000.0
    basis, source = service.get_crypto_basis()
    assert basis == 10000.0
    assert source == "snapshot"


def test_ensure_crypto_basis_does_not_override_existing(isolated_paths):
    """Second call to _ensure_crypto_basis keeps the first snapshot, does not change it."""
    service._ensure_crypto_basis(10000.0)  # first: snapshots at 10000
    result = service._ensure_crypto_basis(15000.0)  # second: must stay at 10000
    assert result == 10000.0
    basis, _ = service.get_crypto_basis()
    assert basis == 10000.0  # unchanged


def test_set_crypto_basis_manual_override(isolated_paths):
    """PUT /crypto-basis sets source='manual'; subsequent _ensure does not override."""
    from modules.finance.schema import CryptoBasisInput
    # First snapshot
    service._ensure_crypto_basis(10000.0)
    # User override
    service.set_crypto_basis(CryptoBasisInput(basis=12000.0))
    basis, source = service.get_crypto_basis()
    assert basis == 12000.0
    assert source == "manual"
    # _ensure should NOT override manual
    result = service._ensure_crypto_basis(15000.0)
    assert result == 12000.0
    basis2, source2 = service.get_crypto_basis()
    assert basis2 == 12000.0 and source2 == "manual"


def test_overview_with_okx_uses_basis_as_cost(isolated_paths, monkeypatch):
    """When OKX is live, overview crypto.cost = snapshotted basis, NOT manual holdings cost."""
    okx_val = 10500.0
    monkeypatch.setattr(service, "_okx_crypto_value", lambda: (okx_val, None))
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    # First call → basis snapshotted = 10500, P&L ≈ 0
    assert crypto.value == 10500.0
    assert crypto.pnl.cost == 10500.0
    assert crypto.pnl.abs == 0.0
    # Second call with higher OKX value — basis stays at snapshot
    monkeypatch.setattr(service, "_okx_crypto_value", lambda: (11000.0, None))
    overview2, _ = service.get_overview()
    crypto2 = next(a for a in overview2.allocations if a.channel == "crypto")
    assert crypto2.value == 11000.0
    assert crypto2.pnl.cost == 10500.0  # unchanged
    assert crypto2.pnl.abs == 500.0  # P&L = 11000 - 10500


# --------------------------------------------------------------------------- #
# Fail-open error/edge paths — a store read that RAISES (not just "file absent")  #
# must degrade gracefully, never propagate. These exercise the except-branches   #
# that the happy-path tests skip.                                                 #
# --------------------------------------------------------------------------- #
def test_list_holdings_returns_empty_when_read_raises(isolated_paths, monkeypatch):
    # md_store.read raising (e.g. permission/IO error) → [] not a crash.
    def boom(_path):
        raise OSError("disk gone")
    monkeypatch.setattr(service.md_store, "read", boom)
    assert service.list_holdings() == []


def test_list_holdings_skips_individual_invalid_holding(isolated_paths):
    # Front-matter with a good holding + a structurally-invalid one. The valid one
    # survives; the invalid is dropped (per-item try/except), not the whole list.
    from store import md_store
    md_store.write_file(
        service.HOLDINGS_MD,
        "---\nholdings:\n"
        "  - symbol: BTC\n    channel: crypto\n    qty: 1\n    avgCost: 100\n"
        "  - not_a_mapping\n"  # invalid item → Holding(**item) raises → skipped
        "---\n",
        "mixed holdings",
    )
    out = service.list_holdings()
    syms = [h.symbol for h in out]
    assert "BTC" in syms
    assert len(out) == 1  # the malformed item was skipped, not fatal


def test_golden_path_baseline_and_warning_when_read_raises(isolated_paths, monkeypatch):
    # Read failure on golden_path.md → fall back to BASELINE_TARGETS + a warning.
    def boom(_path):
        raise OSError("io")
    monkeypatch.setattr(service.md_store, "read", boom)
    targets, _ladder, warnings = service.get_golden_path()
    assert targets == dict(service.BASELINE_TARGETS)
    assert warnings  # at least one warning surfaced (not silent)


def test_get_crypto_basis_non_numeric_is_unset(isolated_paths):
    # A stored basis that can't be cast to float → (None, "unset"), not a ValueError.
    from store import md_store
    md_store.write_file(
        service.CRYPTO_BASIS_MD,
        "---\nbasis: not-a-number\nsource: manual\n---\n",
        "corrupt basis",
    )
    basis, source = service.get_crypto_basis()
    assert basis is None
    assert source == "unset"


def test_parse_front_matter_non_dict_yields_empty():
    # YAML that parses to a non-dict (a bare scalar/list) → {} (distinguishing:
    # a real mapping below DOES parse, proving this isn't an always-{} stub).
    assert service._parse_front_matter("---\n- a\n- b\n---\n") == {}
    parsed = service._parse_front_matter("---\nkey: value\n---\n")
    assert parsed == {"key": "value"}


# --------------------------------------------------------------------------- #
# Portfolio analytics — rebalance / risk / return (math pinned to hand-calc)     #
# --------------------------------------------------------------------------- #
def test_analytics_rebalance_handcalc(isolated_paths, mock_prices):
    """Rebalance amount = targetPct% · total − currentValue. Crafted portfolio:
    crypto $6000 + etf $4000 = $10000 total; targets crypto 50 / etf 50.
    crypto target value 5000 < 6000 → SELL 1000; etf 5000 > 4000 → BUY 1000."""
    mock_prices["BTC"] = 100.0   # 60 BTC → $6000
    mock_prices["VOO"] = 100.0   # 40 VOO → $4000
    service.set_golden_path(GoldenPathInput(targets={"crypto": 50.0, "etf": 50.0}, ladder={}))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=60, avgCost=90))
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=40, avgCost=90))

    a, _ = service.get_analytics()
    assert a.totalValue == 10000.0
    by_ch = {r.channel: r for r in a.rebalance}
    assert by_ch["crypto"].action == "sell" and by_ch["crypto"].amount == 1000.0
    assert by_ch["crypto"].targetValue == 5000.0 and by_ch["crypto"].drift == 10.0  # 60-50
    assert by_ch["etf"].action == "buy" and by_ch["etf"].amount == 1000.0


def test_analytics_on_target_is_hold(isolated_paths, mock_prices):
    """A channel exactly on target → action 'hold', amount 0."""
    mock_prices["BTC"] = 100.0
    service.set_golden_path(GoldenPathInput(targets={"crypto": 100.0}, ladder={}))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=10, avgCost=90))
    a, _ = service.get_analytics()
    crypto = next(r for r in a.rebalance if r.channel == "crypto")
    assert crypto.action == "hold" and crypto.amount == 0.0 and crypto.drift == 0.0


def test_analytics_concentration_hhi_handcalc(isolated_paths, mock_prices):
    """Concentration: BTC $6000 + ETH $2000 = $8000. weights .75/.25 →
    HHI = .75²+.25² = 0.625; top holding BTC 75%; top3 = 100%."""
    mock_prices["BTC"] = 100.0   # 60 → 6000
    mock_prices["ETH"] = 50.0    # 40 → 2000
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=60, avgCost=90))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="ETH", qty=40, avgCost=45))
    a, _ = service.get_analytics()
    assert a.risk.topHoldingSymbol == "BTC" and a.risk.topHoldingPct == 75.0
    assert a.risk.hhi == 0.625
    assert a.risk.top3Pct == 100.0 and a.risk.holdingCount == 2


def test_analytics_total_drift_and_rebalance_distance(isolated_paths, mock_prices):
    """totalAbsDrift = Σ|drift|; rebalanceDistance = ½·that. crypto 100% vs 38% target
    (+62), dry/etf/vn 0% (−20/−24/−18) → Σ|drift| = 124, distance 62."""
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=10, avgCost=90))
    a, _ = service.get_analytics()  # baseline targets crypto38/etf24/vn18/dry20
    assert a.risk.totalAbsDrift == 124.0
    assert a.risk.rebalanceDistance == 62.0


def test_analytics_empty_portfolio_no_crash(isolated_paths):
    """EMPTY portfolio → total 0, all channels 'hold', None risk metrics, returns
    unavailable, a warning — never a 500."""
    a, warnings = service.get_analytics()
    assert a.totalValue == 0.0
    assert all(r.action == "hold" and r.amount == 0.0 for r in a.rebalance)
    assert a.risk.topHoldingPct is None and a.risk.hhi is None and a.risk.holdingCount == 0
    assert a.returns.available is False
    assert any("series" in w for w in warnings)


def test_analytics_target_zero_channel(isolated_paths, mock_prices):
    """A channel with target 0 that HAS value → sell ALL of it (target value 0)."""
    mock_prices["BTC"] = 100.0   # crypto $1000
    mock_prices["VOO"] = 100.0   # etf $1000
    # crypto target 100, etf target 0 → etf should be fully sold.
    service.set_golden_path(GoldenPathInput(targets={"crypto": 100.0, "etf": 0.0}, ladder={}))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=10, avgCost=90))
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=10, avgCost=90))
    a, _ = service.get_analytics()
    etf = next(r for r in a.rebalance if r.channel == "etf")
    assert etf.targetPct == 0.0 and etf.targetValue == 0.0
    assert etf.action == "sell" and etf.amount == 1000.0  # divest entirely


# --- return metrics (pure math) ---
def test_return_metrics_handcalc():
    # series [100,110,99,121] → total return (121-100)/100 = 21%
    rm = service._return_metrics([100.0, 110.0, 99.0, 121.0])
    assert rm.totalReturnPct == 21.0
    assert rm.available is True and rm.volatilityPct is not None  # stddev of period returns


def test_return_metrics_empty_unavailable():
    rm = service._return_metrics([])
    assert rm.available is False and rm.totalReturnPct is None and rm.volatilityPct is None


def test_return_metrics_single_point_unavailable():
    rm = service._return_metrics([100.0])  # need ≥2 for a return
    assert rm.available is False


def test_analytics_is_neutral_no_advice(isolated_paths, mock_prices):
    """The analytics payload carries NEUTRAL numbers only — no buy/sell-ADVICE words
    beyond the mechanical action enum (buy/sell/hold are rebalance directions, not
    recommendations). Spot-check: no 'recommend'/'should'/'advice' strings leak in."""
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=10, avgCost=90))
    a, _ = service.get_analytics()
    blob = str(a.model_dump()).lower()
    for word in ("recommend", "should", "advice", "advise"):
        assert word not in blob
