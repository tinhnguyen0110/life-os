"""tests/test_finance_assistant_p1.py — FINANCE-ASSISTANT Phase 1 (Task #52).

The Phase-1 data substrate, behavior-tested with DIVERGENT fixtures:
  T1 — OKX cost-basis → real per-coin pnl (avgCost = accAvgPx). A coin WITH a basis gets a
       real (possibly negative) pnl; a basis-less coin (stablecoin) → honest-null. The
       spotUpl SANITY cross-check: our recomputed pnl.pct ≈ OKX's own spotUplRatio×100.
  T2 — macro +4 indicators via the no-key FRED CSV; FRED-000 → fail-open mock + low
       confidence, NEVER a 500 (the HARD defensive case).
  T3 — the daily macro+sentiment snapshot routine writes F&G/BTC.d/yield to macro_history;
       monthly FRED values dedupe (upsert by ts).
"""

from __future__ import annotations

import pytest

from modules.exchange.schema import ExchangeOverview, OkxBalance


# --------------------------------------------------------------------------- #
# T1 — OKX cost-basis → real pnl (avgCost = accAvgPx); the spotUpl cross-check   #
# --------------------------------------------------------------------------- #
def _okx_snap(balances: list[OkxBalance]) -> ExchangeOverview:
    total = sum(b.usdValue or 0.0 for b in balances)
    return ExchangeOverview(configured=True, totalUsdValue=total, balances=balances)


@pytest.fixture
def okx_basis_fixture(isolated_paths, monkeypatch):
    """A DIVERGENT OKX portfolio: a LOSING coin (PEPE-like, real accAvgPx, current well below),
    a basis-LESS coin (USDT stablecoin, accAvgPx None), and a coin priced by our feed. So a
    correct impl (pnl real+negative for PEPE, null for USDT) differs from a collapsed one."""
    from modules.finance import service as fin
    from modules.market import service as mkt
    from modules.market.schema import AssetQuote

    # PEPE: accAvgPx 0.00000702, qty 28.5M, OKX values it ~$84 → real ~-58% loss.
    pepe = OkxBalance(symbol="PEPE", available=28_500_000, frozen=0, total=28_500_000,
                      usdValue=84.0, accAvgPx=0.00000702, spotUpl=-116.0, spotUplRatio=-0.58)
    # USDT: stablecoin, OKX exposes NO basis (accAvgPx None) → pnl must stay honest-null.
    usdt = OkxBalance(symbol="USDT", available=10000, frozen=0, total=10000,
                      usdValue=10000.0, accAvgPx=None, spotUpl=None, spotUplRatio=None)
    snap = _okx_snap([pepe, usdt])
    monkeypatch.setattr(fin.exchange_service, "get_overview", lambda: (snap, None))
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (snap.totalUsdValue, None))
    # our price feed: no quote → the OKX value/qty display price is used (changePct null is fine)
    monkeypatch.setattr(mkt, "get_quote", lambda s: None)
    return snap


def test_okx_coin_with_basis_gets_real_negative_pnl(okx_basis_fixture):
    """DISTINGUISHING: PEPE has a real accAvgPx → its per-coin pnl is REAL and NEGATIVE
    (~-58%), NOT null. A no-basis impl would leave it null (the pre-#52 'pnl null everywhere')."""
    from modules.finance import service as fin
    entries = fin._okx_crypto_holdings()
    pepe = next(e for e in entries if e["holding"]["symbol"] == "PEPE")
    assert pepe["holding"]["avgCost"] == 0.00000702          # wired from accAvgPx
    assert pepe["pnl"] is not None, "PEPE must have a real pnl, not null"
    assert pepe["pnl"]["pct"] is not None and pepe["pnl"]["pct"] < 0   # a real LOSS
    assert pepe["pnl"]["pct"] < -40                          # ~-58%, decisively negative


def test_okx_basisless_coin_pnl_is_honest_null(okx_basis_fixture):
    """DISTINGUISHING the other way: USDT has NO accAvgPx → avgCost None → pnl honest-null
    (never a fabricated 0-basis +∞% gain). null ≠ a real number."""
    from modules.finance import service as fin
    entries = fin._okx_crypto_holdings()
    usdt = next(e for e in entries if e["holding"]["symbol"] == "USDT")
    assert usdt["holding"]["avgCost"] is None
    assert usdt["pnl"] is None, "a basis-less coin's pnl must stay honest-null"


def test_okx_spotupl_sanity_cross_check(okx_basis_fixture):
    """SANITY (team-lead LOCKED): our recomputed pnl.pct must be CLOSE (<5pp) to OKX's OWN
    spotUplRatio×100 — same basis, value differs only by our-feed-vs-OKX-price. A LARGE
    divergence would mean a price-feed bug. Here our display price = OKX value/qty (we have no
    quote), so it should match OKX's ratio almost exactly."""
    from modules.finance import service as fin
    entries = fin._okx_crypto_holdings()
    pepe = next(e for e in entries if e["holding"]["symbol"] == "PEPE")
    our_pct = pepe["pnl"]["pct"]
    okx_pct = pepe["okxSpotUplRatio"] * 100.0          # OKX's own ratio → pct
    assert abs(our_pct - okx_pct) < 5.0, (
        f"pnl divergence too large: ours={our_pct} vs OKX={okx_pct} (>5pp = price-feed bug)")


def test_okxbalance_additive_fields_default_none():
    """ADDITIVE-only: the 3 new OkxBalance fields are nullable + default None — an old-shaped
    construction (no cost-basis) still validates (no consumer breaks)."""
    b = OkxBalance(symbol="BTC", available=1, frozen=0, total=1)   # no new fields supplied
    assert b.accAvgPx is None and b.spotUpl is None and b.spotUplRatio is None


def test_parse_balances_empty_accavgpx_is_none_not_zero():
    """The OKX parse: '' (a coin with no basis) → None, NOT 0.0 (a 0 basis would read as a
    fake +∞% gain). _opt_float guards this."""
    from modules.exchange import service as exsvc
    raw = [{"ccy": "USDT", "availBal": "100", "frozenBal": "0", "eqUsd": "100",
            "accAvgPx": "", "spotUpl": "", "spotUplRatio": ""},
           {"ccy": "PEPE", "availBal": "1000", "frozenBal": "0", "eqUsd": "5",
            "accAvgPx": "0.00000702", "spotUpl": "-3.2", "spotUplRatio": "-0.58"}]
    balances, _ = exsvc._parse_balances(raw)
    by_sym = {b.symbol: b for b in balances}
    assert by_sym["USDT"].accAvgPx is None        # '' → None, not 0
    assert by_sym["PEPE"].accAvgPx == 0.00000702  # parsed
    assert by_sym["PEPE"].spotUplRatio == -0.58


# --------------------------------------------------------------------------- #
# T5 — per-holding pnl SURFACED on finance_overview (the agent surface). The      #
# DISTINGUISHING case: in ONE response, a real-basis coin's pnl is REAL while a    #
# basis-less coin's is null — per-holding granularity, NOT channel-masked.         #
# --------------------------------------------------------------------------- #
def test_T5_per_holding_pnl_real_and_null_same_response(okx_basis_fixture):
    """DISTINGUISHING (team-lead HARD): finance_overview's crypto channel carries a REAL pnl
    on PEPE (~-58%, real basis) AND a NULL pnl on USDT (no basis) IN THE SAME response. This
    proves per-holding granularity — the channel-level basisUnknown nulls the aggregate (USDT
    98%-by-value dominates), which would MASK PEPE's real loss on the main agent surface. An
    all-have-basis fixture would pass even against the broken channel-only version."""
    from modules.finance import service as fin
    ov, _ = fin.get_overview()
    crypto = {h.symbol: h for h in ov.holdings if h.channel == "crypto"}
    # PEPE: real, negative pnl surfaced on the Holding
    assert crypto["PEPE"].pnl is not None, "PEPE must carry a real pnl on finance_overview"
    assert crypto["PEPE"].pnl.pct is not None and crypto["PEPE"].pnl.pct < -40   # ~-58%
    # USDT: basis-less → honest-null pnl IN THE SAME response (not masked, not fabricated)
    assert crypto["USDT"].pnl is None or crypto["USDT"].pnl.pct is None, \
        "a basis-less coin's pnl must be null, not a fabricated number"


def test_T5_per_holding_pnl_matches_aggregate_not_recomputed(okx_basis_fixture):
    """The surfaced pnl is the EXACT number _aggregate/_okx_crypto_holdings computed (threaded,
    not re-derived) — consistency. Compare the Holding.pnl to the entry's pnl."""
    from modules.finance import service as fin
    entries = {e["holding"]["symbol"]: e for e in fin._okx_crypto_holdings()}
    ov, _ = fin.get_overview()
    pepe = next(h for h in ov.holdings if h.symbol == "PEPE")
    assert pepe.pnl is not None
    assert pepe.pnl.pct == entries["PEPE"]["pnl"]["pct"]   # same number, threaded


def test_T5_spotupl_sanity_on_surfaced_pnl(okx_basis_fixture):
    """spotUpl cross-check on the SURFACED finance_overview pnl (not just the entry): the
    Holding.pnl.pct should be within ~5pp of OKX's spotUplRatio×100 (same avgCost feeds both)."""
    from modules.finance import service as fin
    ov, _ = fin.get_overview()
    pepe = next(h for h in ov.holdings if h.symbol == "PEPE")
    okx_pct = -0.58 * 100.0   # the fixture's spotUplRatio
    assert abs(pepe.pnl.pct - okx_pct) < 5.0


def test_T5_channel_basisunknown_unchanged(okx_basis_fixture):
    """basisUnknown UNTOUCHED (mandatory d): the channel-level ChannelAlloc.pnl + basisUnknown
    behave exactly as before — a USDT-dominated crypto channel aggregate is still honestly null
    (the per-holding add does NOT change the aggregate)."""
    from modules.finance import service as fin
    ov, _ = fin.get_overview()
    crypto_alloc = next(a for a in ov.allocations if a.channel == "crypto")
    assert crypto_alloc.basisUnknown is True          # USDT 99%-by-value → majority no-basis
    assert crypto_alloc.pnl.abs is None and crypto_alloc.pnl.pct is None   # aggregate null, unchanged


def test_T5_dust_entry_pnl_is_none(isolated_paths, monkeypatch):
    """A ·dust summary entry has pnl None (a sum-of-many has no single pnl, like price/changePct)."""
    from modules.finance import service as fin
    from modules.market import service as mkt
    from modules.market.schema import AssetQuote
    from modules.finance.schema import HoldingInput
    monkeypatch.setattr(fin, "_okx_crypto_value", lambda: (None, None))
    prices = {"BTC": 100.0, "DUSTY": 0.30, "DUSTZ": 0.20}  # 2 sub-$1 → fold into one ·dust
    monkeypatch.setattr(mkt, "get_quote",
                        lambda s: AssetQuote(symbol=s, name=s, assetClass="crypto",
                                             price=prices.get(s, 0.0), currency="USD",
                                             ts="2026-06-16T00:00:00+00:00", source="mock")
                        if s in prices else None)
    fin.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))
    fin.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTY", qty=1, avgCost=0.1))
    fin.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTZ", qty=1, avgCost=0.1))
    ov, _ = fin.get_overview()
    dust = next(h for h in ov.holdings if h.isDust)
    assert dust.pnl is None


# --------------------------------------------------------------------------- #
# T2 — macro +4 indicators; FRED-000 fail-open (HARD), confidence seam           #
# --------------------------------------------------------------------------- #
@pytest.fixture
def macro_db(isolated_paths):
    from modules.macro import store as mstore
    mstore.init_macro_tables()
    return isolated_paths


def test_macro_has_four_new_indicators(macro_db, monkeypatch):
    """The 4 macro-cycle indicators are tracked + surface in get_overview (with whatever
    source the CSV yields). Mock the CSV to a real point so they're source='fred'."""
    from modules.macro import reader as mr, service as ms
    monkeypatch.setattr(mr, "_fetch_fred_csv",
                        lambda series_id, limit=12: [{"date": "2026-06-01", "value": 1.23},
                                                     {"date": "2026-06-02", "value": 1.25}])
    ov, _ = ms.get_overview()
    keys = {v.indicator for v in ov.indicators}
    for new in ("yield_curve_10y2y", "unemployment", "m2_liquidity", "industrial_production"):
        assert new in keys, f"{new} missing from macro overview"
    # P2 (#54): the seam is now the REAL compute_q (freshness×coverage×agreement), NOT the P1
    # 0.9/0.2 source-stub. A fred point with a present value → coverage 1, agreement 1, and a
    # real freshness from its ts → confidence ∈ (0, 1] (a number that TRACKS freshness, not a
    # constant). (The exact value depends on now−ts; just assert it's a real q in range.)
    yc = next(v for v in ov.indicators if v.indicator == "yield_curve_10y2y")
    assert yc.source == "fred"
    assert 0.0 < yc.confidence <= 1.0


def test_fred_000_fails_open_to_mock_never_500(macro_db, monkeypatch):
    """HARD (team-lead): a FRED CSV HTTP-000 (T10Y2Y's live state) → the indicator is STILL
    present in get_overview with source='mock' + LOW confidence + a warning, NO exception.
    The retry exhausts, then fail-open."""
    from modules.macro import reader as mr, service as ms

    def boom(*a, **k):
        raise RuntimeError("HTTP 000")  # simulate the dead endpoint
    monkeypatch.setattr(mr.httpx, "get", boom)

    ov, warnings = ms.get_overview()  # MUST NOT raise
    yc = next(v for v in ov.indicators if v.indicator == "yield_curve_10y2y")
    assert yc.source == "mock"            # fell open (the honesty signal)
    # FINANCE-AUDIT-S1 (#59): a MOCK indicator is now EXCLUDED from confidence (mock = the
    # ABSENCE of real data → coverage 0 → confidence 0). This is the audit fix: a mock must
    # NEVER raise confidence (the 4.6× inversion is gone). So a mock's confidence is 0, not a
    # "real q in range" — the honesty is the source='mock' tag + the warning + the now-0 conf.
    assert yc.confidence == 0.0, "a mock indicator must be excluded → confidence 0 (#59)"
    assert yc.latest is not None          # still has a (mock) value — honest, present
    assert any("mock" in w.lower() for w in warnings)


def test_fred_retry_then_succeed(macro_db, monkeypatch):
    """The retry RESCUES a transient blip: fail once, then succeed → source='fred', no mock."""
    from modules.macro import reader as mr

    calls = {"n": 0}

    def flaky(series_id, limit=12):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient 504")
        return [{"date": "2026-06-01", "value": 0.35}]
    monkeypatch.setattr(mr, "_fetch_fred_csv", flaky)
    pts, warning = mr.fetch_latest("yield_curve_10y2y")
    assert warning is None and pts and pts[-1]["source"] == "fred"
    assert calls["n"] == 2  # failed once, retried, succeeded


# --------------------------------------------------------------------------- #
# T3 — daily macro+sentiment snapshot routine + monthly dedupe                   #
# --------------------------------------------------------------------------- #
def test_macro_snapshot_writes_sentiment_to_history(macro_db, monkeypatch):
    """The routine snapshots F&G/BTC.d/yield into macro_history → readable via get_history."""
    from modules.macro import reader as mr, service as ms
    monkeypatch.setattr(mr, "fetch_fear_greed", lambda: (23.0, "live"))
    monkeypatch.setattr(mr, "fetch_btc_dominance", lambda: (56.48, "live"))
    monkeypatch.setattr(mr, "fetch_latest",
                        lambda ind: ([{"indicator": "yield_curve_10y2y", "value": 0.35,
                                       "ts": "2026-06-16", "source": "fred"}], None))
    status, summary = ms.macro_sentiment_snapshot()
    assert status == "ok"
    fng = ms.get_history("fear_greed", days=30)
    assert fng is not None and fng.points and fng.points[-1].value == 23.0
    btcd = ms.get_history("btc_dominance", days=30)
    assert btcd is not None and btcd.points and btcd.points[-1].value == 56.48


def test_macro_snapshot_failsoft_one_source_down(macro_db, monkeypatch):
    """A down source (F&G) → warn + the OTHERS still land (fail-soft per signal, no abort)."""
    from modules.macro import reader as mr, service as ms
    monkeypatch.setattr(mr, "fetch_fear_greed", lambda: (None, "mock"))  # down
    monkeypatch.setattr(mr, "fetch_btc_dominance", lambda: (56.48, "live"))
    monkeypatch.setattr(mr, "fetch_latest", lambda ind: ([], "mock"))
    status, summary = ms.macro_sentiment_snapshot()
    assert status == "warn"
    # BTC.d still landed despite F&G being down
    btcd = ms.get_history("btc_dominance", days=30)
    assert btcd is not None and btcd.points and btcd.points[-1].value == 56.48


def test_monthly_macro_value_dedupes_by_ts(macro_db, monkeypatch):
    """DEDUPE (mandatory e): a monthly FRED value re-fetched on a later day keeps its month
    ts → record_point upserts (no duplicate row). Refreshing twice with the SAME monthly point
    must NOT grow the row count."""
    from modules.macro import reader as mr, service as ms, store as mstore
    # one fixed monthly point for unemployment
    monkeypatch.setattr(mr, "fetch_latest",
                        lambda ind: ([{"indicator": ind, "value": 4.1, "ts": "2026-06-01",
                                       "source": "fred"}], None))
    ms.refresh()
    n1 = mstore.count("unemployment")
    ms.refresh()  # same monthly point again (a later day, same ts)
    n2 = mstore.count("unemployment")
    assert n1 == n2 == 1, f"monthly value duplicated: {n1} -> {n2} (must upsert by ts)"
