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


def test_okx_unvalued_coin_shown_honest_null(mock_okx, mock_prices, isolated_paths):
    # a coin with usdValue None is SHOWN (qty visible) with value 0 + honest-null pnl
    # (architect: don't skip, don't assume a price/value) — NOT fabricated, NOT dropped.
    mock_okx([
        OkxBalance(symbol="BTC", available=1.0, frozen=0.0, total=1.0, usdValue=60000.0),
        OkxBalance(symbol="XYZ", available=5.0, frozen=0.0, total=5.0, usdValue=None),
    ], total=60000.0)
    ch, _ = service.get_channel("crypto")
    by_sym = {e["holding"]["symbol"]: e for e in ch["holdings"]}
    assert "XYZ" in by_sym  # SHOWN, not skipped
    xyz = by_sym["XYZ"]
    assert xyz["holding"]["qty"] == 5.0      # qty visible
    assert xyz["value"] == 0.0               # honest-null value (no fabrication)
    assert xyz["price"] is None              # no assumed price
    assert xyz["pnl"] is None                # honest-null pnl
    # a zero-TOTAL coin (not held) is still skipped
    mock_okx([OkxBalance(symbol="ZERO", available=0.0, frozen=0.0, total=0.0, usdValue=None)],
             total=0.0)
    # total 0 → _okx_crypto_holdings returns None (no entries) → fail-soft to manual
    assert service._okx_crypto_holdings() is None


# --------------------------------------------------------------------------- #
# NB4 — honest framing: basisUnknown (value-only pnl isn't a real gain) +        #
# stableValue/stablePct split (stablecoins are dry-powder-like, not exposure).   #
# --------------------------------------------------------------------------- #
def test_nb4_basis_unknown_true_for_value_only_crypto(mock_okx, mock_prices, isolated_paths):
    """OKX per-coin holdings are value-only (avgCost None) → the crypto channel's
    basisUnknown is TRUE, so the cost=0 pnl ($ value as 'abs gain') isn't misread."""
    mock_okx([OkxBalance(symbol="BTC", available=1.0, frozen=0.0, total=1.0, usdValue=60000.0)],
             total=60000.0)
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.basisUnknown is True
    # NB4+D3a: basisUnknown → BOTH pnl.abs AND pnl.pct NULLED (a value-only inflow must not
    # read as a +$X / +Y% gain); cost/current (raw $) KEPT.
    assert crypto.pnl.pct is None
    assert crypto.pnl.abs is None
    assert crypto.pnl.current is not None and crypto.pnl.cost is not None


def test_nb4_basis_unknown_false_for_manual_with_cost(mock_okx, mock_prices, isolated_paths):
    """DISTINGUISHING: a manual etf channel WITH avgCost → basisUnknown FALSE in the SAME
    overview where the value-only crypto channel is TRUE (proves it's per-channel by
    real basis, not a blanket flag)."""
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=10, avgCost=400))
    mock_okx([OkxBalance(symbol="BTC", available=1.0, frozen=0.0, total=1.0, usdValue=60000.0)],
             total=60000.0)
    overview, _ = service.get_overview()
    etf = next(a for a in overview.allocations if a.channel == "etf")
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert etf.basisUnknown is False    # has avgCost → real basis
    assert crypto.basisUnknown is True  # value-only → flagged
    # same overview, two channels DIVERGE → the flag tracks real basis, not a constant.
    # NB4 distinguishing: the manual channel's legit pnl.pct is NOT hidden, only the
    # value-only channel's misleading % is nulled.
    # D3a distinguishing BOTH ways: real-basis etf keeps abs AND pct; value-only crypto
    # nulls BOTH — proves the suppression keys on real basis, not a blanket null.
    assert etf.pnl.pct is not None and etf.pnl.abs is not None   # legit manual P&L SHOWN
    assert crypto.pnl.pct is None and crypto.pnl.abs is None     # value-only gain suppressed


def test_nb4_stable_split_and_high_warning(mock_okx, mock_prices, isolated_paths):
    """Crypto channel majority stablecoins → stableValue/stablePct populated + a
    'dry-powder-like' warning fires (>50%)."""
    mock_okx([
        OkxBalance(symbol="USDT", available=70000, frozen=0, total=70000, usdValue=70000.0),
        OkxBalance(symbol="BTC", available=0.5, frozen=0, total=0.5, usdValue=30000.0),
    ], total=100000.0)
    overview, warnings = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.stableValue == 70000.0
    assert crypto.stablePct == 70.0
    assert any("stablecoin" in w.lower() and "dry-powder" in w.lower() for w in warnings)


def test_nb4_stable_split_low_no_warning_distinguishing(mock_okx, mock_prices, isolated_paths):
    """DISTINGUISHING: a crypto channel that is MOSTLY real exposure (BTC-heavy, little
    stable) → stablePct low + NO dry-powder warning. The SAME tool that warns on a
    stable-heavy channel stays quiet here — proves the warn keys on the ratio, not a
    blanket 'crypto has any stablecoin' flag."""
    mock_okx([
        OkxBalance(symbol="BTC", available=1.5, frozen=0, total=1.5, usdValue=90000.0),
        OkxBalance(symbol="USDT", available=10000, frozen=0, total=10000, usdValue=10000.0),
    ], total=100000.0)
    overview, warnings = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.stableValue == 10000.0
    assert crypto.stablePct == 10.0
    assert not any("dry-powder" in w.lower() for w in warnings)  # 10% < 50% → quiet


def test_nb4_stable_pct_none_for_non_crypto(mock_okx, mock_prices, isolated_paths):
    """stableValue/stablePct are crypto-ONLY — a non-crypto channel reports None (a
    stablecoin only lives in the crypto channel; etf/vn/dry get None, not 0)."""
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=10, avgCost=400))
    mock_okx([OkxBalance(symbol="BTC", available=1.0, frozen=0, total=1.0, usdValue=60000.0)],
             total=60000.0)
    overview, _ = service.get_overview()
    etf = next(a for a in overview.allocations if a.channel == "etf")
    assert etf.stableValue is None and etf.stablePct is None


def test_nb4_get_channel_carries_framing(mock_okx, mock_prices, isolated_paths):
    """GET /finance/{channel} (detail) carries the SAME framing as the overview."""
    mock_okx([
        OkxBalance(symbol="USDT", available=60000, frozen=0, total=60000, usdValue=60000.0),
        OkxBalance(symbol="BTC", available=0.5, frozen=0, total=0.5, usdValue=30000.0),
    ], total=90000.0)
    ch, warnings = service.get_channel("crypto")
    assert ch["alloc"]["basisUnknown"] is True
    assert ch["alloc"]["stablePct"] == round(60000.0 / 90000.0 * 100, 2)
    assert any("dry-powder" in w.lower() for w in warnings)


def test_nb4_empty_channel_basis_unknown_false():
    """Pure-helper edge: an empty channel (no holdings) → basisUnknown False (no false
    alarm) + stable split (None, None) on zero value."""
    assert service._basis_unknown([]) is False
    assert service._stable_split([], 0.0) == (0.0, None)


# --------------------------------------------------------------------------- #
# D3a (b) — crypto drift warning reframed as undeployed-cash when stablePct>90. #
# --------------------------------------------------------------------------- #
def test_d3a_crypto_drift_reframed_when_stable_heavy(mock_okx, mock_prices, isolated_paths):
    """Crypto >90% stablecoin AND drifted vs target → the drift warning is REFRAMED as
    undeployed cash (not crypto over/under-exposure). The plain 'allocation drift' wording
    must NOT appear for crypto; the reframed 'UNDEPLOYED stablecoin' wording must."""
    # crypto = whole portfolio (pct≈100 vs target 38 → drift fires), 98% USDT
    mock_okx([
        OkxBalance(symbol="USDT", available=98000, frozen=0, total=98000, usdValue=98000.0),
        OkxBalance(symbol="BTC", available=0.03, frozen=0, total=0.03, usdValue=2000.0),
    ], total=100000.0)
    _, warnings = service.get_overview()
    crypto_warns = [w for w in warnings if w.startswith("crypto")]
    assert any("UNDEPLOYED stablecoin" in w for w in crypto_warns), \
        "stable-heavy crypto drift must be reframed as undeployed cash"
    assert not any("allocation drift" in w for w in crypto_warns), \
        "the plain drift wording must NOT be used for a stable-dominated crypto channel"


def test_d3a_real_crypto_keeps_plain_drift_distinguishing(mock_okx, mock_prices, isolated_paths):
    """DISTINGUISHING (the other way): a crypto channel that is mostly REAL exposure (BTC,
    only 10% stable) but drifted → keeps the PLAIN 'allocation drift' warning, NOT the
    undeployed-cash reframe. Proves the reframe keys on stablePct>90, not 'crypto drifted'."""
    mock_okx([
        OkxBalance(symbol="BTC", available=1.5, frozen=0, total=1.5, usdValue=90000.0),
        OkxBalance(symbol="USDT", available=10000, frozen=0, total=10000, usdValue=10000.0),
    ], total=100000.0)  # crypto ≈100% of portfolio (drift fires), only 10% stable
    _, warnings = service.get_overview()
    crypto_warns = [w for w in warnings if w.startswith("crypto")]
    assert any("allocation drift" in w for w in crypto_warns), \
        "real-exposure crypto keeps the plain drift warning"
    assert not any("UNDEPLOYED stablecoin" in w for w in crypto_warns), \
        "a 10%-stable crypto channel must NOT be reframed as undeployed"


# --------------------------------------------------------------------------- #
# PERF #68 seam (A): the OKX symbol-discovery pre-read CANNOT drift a number.    #
# get_overview reads OKX up front (to learn which symbols to batch-prefetch),    #
# then _okx_crypto_holdings reads OKX again for the VALUES. In prod both return  #
# the SAME cached _last_snapshot. This test proves the WORST case — even if the  #
# two reads return DIFFERENT snapshots — is correctness-NEUTRAL: the per-coin    #
# VALUE always comes from _okx_crypto_holdings' own read (never the discovery    #
# read, which only yields symbol strings → can't corrupt a value).               #
# --------------------------------------------------------------------------- #
def test_perf68_okx_discovery_read_does_not_drift_value(monkeypatch, mock_prices, isolated_paths):
    """Two DIFFERENT snapshots on successive exchange reads (simulated drift) → the
    crypto VALUE is internally consistent with the LAST read that built the holdings
    (_okx_crypto_holdings), not corrupted by the earlier symbol-discovery read."""
    snaps = [
        # 1st read (symbol discovery in get_overview): BTC @ 60k
        (ExchangeOverview(configured=True, totalUsdValue=60000.0, balances=[
            OkxBalance(symbol="BTC", available=1.0, frozen=0, total=1.0, usdValue=60000.0)]), None),
        # 2nd+ reads (_okx_crypto_value + _okx_crypto_holdings): BTC @ 61k (a tick happened)
        (ExchangeOverview(configured=True, totalUsdValue=61000.0, balances=[
            OkxBalance(symbol="BTC", available=1.0, frozen=0, total=1.0, usdValue=61000.0)]), None),
    ]
    calls = [0]

    def drifting_get_overview():
        i = min(calls[0], len(snaps) - 1)
        calls[0] += 1
        return snaps[i]

    monkeypatch.setattr(service.exchange_service, "get_overview", drifting_get_overview)
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    # the VALUE reflects the holdings-building read (61k), is a single self-consistent
    # snapshot — the discovery read's 60k did NOT leak in. No mixed/torn number.
    assert crypto.value == 61000.0
    assert overview.totalValue == 61000.0
    # and the discovery read happened (proves get_overview DID pre-read for symbols)
    assert calls[0] >= 2


# --------------------------------------------------------------------------- #
# #106 — drift WARNING fires only at |drift|>30% (WARNING_DRIFT_PCT); the       #
# precise >5% signal stays on the structured driftAlert FIELD (unchanged).       #
# --------------------------------------------------------------------------- #
def test_106_mid_drift_no_warning_but_field_still_alerts(mock_okx, mock_prices, isolated_paths):
    """A channel that drifts BETWEEN 5% and 30% → NO noisy 'allocation drift' WARNING (boilerplate
    cut), but its driftAlert FIELD is STILL True (the >5% structured signal is unchanged). crypto
    is BTC (real exposure, no stablecoin reframe) at ~48% vs target 38 → drift +10% (5<10<30)."""
    # crypto $48k BTC (real) + etf $52k → crypto pct = 48% → drift +10% vs target 38%.
    mock_okx([OkxBalance(symbol="BTC", available=0.8, frozen=0, total=0.8, usdValue=48000.0)],
             total=48000.0)
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=130, avgCost=400))  # ~$52k cost-fallback
    overview, warnings = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    # the FIELD still alerts (>5%) — structured signal unchanged
    assert crypto.driftAlert is True, "driftAlert FIELD must still fire at >5% (the field is unchanged)"
    assert abs(crypto.drift) > 5.0 and abs(crypto.drift) <= 30.0, f"need a 5-30% drift, got {crypto.drift}"
    # but NO noisy WARNING for this mid-range drift (the #106 noise cut)
    assert not any("crypto: allocation drift" in w for w in warnings), \
        f"a 5-30% drift must NOT emit a WARNING (only the field): {warnings}"


def test_106_large_drift_still_warns(mock_okx, mock_prices, isolated_paths):
    """DISTINGUISHING: a NOTABLE drift (>30%) DOES still emit the WARNING — proves the threshold
    gates noise, not all drift. crypto ~100% (real BTC) vs target 38 → drift +62% (>30)."""
    mock_okx([OkxBalance(symbol="BTC", available=1.5, frozen=0, total=1.5, usdValue=90000.0)],
             total=90000.0)  # crypto ≈100%, real exposure (no stable) → plain drift, drift +62%
    overview, warnings = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert abs(crypto.drift) > 30.0
    assert any("crypto: allocation drift" in w for w in warnings), \
        ">30% drift must still emit the WARNING"


def test_106_stablecoin_warning_not_duplicated_when_reframed(mock_okx, mock_prices, isolated_paths):
    """#106 dedup: crypto >90% stablecoin AND a notable (>30%) drift → ONLY the UNDEPLOYED reframe
    fires; the separate 'dry-powder-like' line is SUPPRESSED (the two stated the same observation).
    So the stablecoin story appears EXACTLY ONCE, not twice."""
    mock_okx([
        OkxBalance(symbol="USDT", available=98000, frozen=0, total=98000, usdValue=98000.0),
        OkxBalance(symbol="BTC", available=0.03, frozen=0, total=0.03, usdValue=2000.0),
    ], total=100000.0)  # 98% stable, crypto ≈100% → drift +62% (notable) → reframe fires
    _, warnings = service.get_overview()
    crypto_warns = [w for w in warnings if w.startswith("crypto")]
    # the reframe is present...
    assert any("UNDEPLOYED stablecoin" in w for w in crypto_warns)
    # ...and the separate dry-powder line is SUPPRESSED (no duplicate stablecoin observation)
    assert not any("dry-powder" in w for w in crypto_warns), \
        "the dry-powder line must be suppressed when the reframe already tells the stablecoin story (#106 dedup)"
    # exactly ONE crypto-stablecoin warning total
    stable_mentions = [w for w in crypto_warns if "stablecoin" in w.lower() or "dry-powder" in w.lower()]
    assert len(stable_mentions) == 1, f"stablecoin story must appear ONCE, got {len(stable_mentions)}: {stable_mentions}"


def test_106_dry_powder_kept_when_no_reframe(mock_okx, mock_prices, isolated_paths):
    """DISTINGUISHING: a stablecoin-heavy crypto (>50%) but NOT undeployed-with-notable-drift keeps
    the dry-powder line (it's the only stablecoin signal then). 70% stable + crypto ≈100% → 70<90 so
    NOT 'undeployed' → no reframe → the dry-powder line MUST stay (proves the dedup is conditional)."""
    mock_okx([
        OkxBalance(symbol="USDT", available=70000, frozen=0, total=70000, usdValue=70000.0),
        OkxBalance(symbol="BTC", available=0.5, frozen=0, total=0.5, usdValue=30000.0),
    ], total=100000.0)  # 70% stable (>50 dry-powder, <90 not undeployed)
    _, warnings = service.get_overview()
    crypto_warns = [w for w in warnings if w.startswith("crypto")]
    assert any("dry-powder" in w for w in crypto_warns), \
        "70% stable (<90) keeps the dry-powder line — not suppressed (no reframe to subsume it)"
    assert not any("UNDEPLOYED stablecoin" in w for w in crypto_warns), \
        "70% stable is NOT 'undeployed' (>90) → no reframe"
