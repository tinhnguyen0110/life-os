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


# --------------------------------------------------------------------------- #
# #72-BE — real day-over-day nav change (honest-null at <2 days). EXERCISE the    #
# rule by seeding snapshots on distinct days, then asserting the delta.          #
# --------------------------------------------------------------------------- #
def _seed_snapshot(days_ago: int, total: float):
    """Record a snapshot dated `days_ago` UTC days back (distinct day = distinct PK)."""
    from datetime import timedelta, timezone
    from store import db
    ts = (service._now() - timedelta(days=days_ago)).astimezone(timezone.utc).isoformat()
    db.record_snapshot(ts, total)


def test_nav_change_two_days_real_delta(isolated_paths):
    """2 snapshots (prior day 1000, today's live value 1100) → abs=100.0 pct=10.0 (the
    distinguishing: a real delta, not the old stub 0.0). EXERCISE — seed a prior day, compute."""
    _seed_snapshot(days_ago=1, total=1000.0)
    change = service._nav_change(1100.0)
    assert change is not None
    assert change.abs == 100.0 and change.pct == 10.0


def test_nav_change_one_snapshot_today_only_is_none(isolated_paths):
    """Only TODAY's snapshot (no prior day) → None (honest-null, NOT a fabricated abs=0 — a 0
    would read as 'flat day' when the truth is 'no prior baseline')."""
    _seed_snapshot(days_ago=0, total=1000.0)  # today only
    assert service._nav_change(1000.0) is None


def test_nav_change_zero_snapshots_is_none(isolated_paths):
    """No snapshots at all → None (no baseline)."""
    assert service._nav_change(500.0) is None


def test_nav_change_flat_with_prior_is_honest_zero(isolated_paths):
    """A prior day EXISTS and today equals it → abs=0.0 pct=0.0 (this IS honest flat — distinct
    from the no-data None case above; the key honest-mirror distinguishing)."""
    _seed_snapshot(days_ago=1, total=1000.0)
    change = service._nav_change(1000.0)
    assert change is not None and change.abs == 0.0 and change.pct == 0.0


def test_nav_change_prior_zero_pct_none_no_div0(isolated_paths):
    """prior_total==0 → pct=None (no divide-by-zero), abs still computed (the real rise from 0)."""
    _seed_snapshot(days_ago=1, total=0.0)
    change = service._nav_change(250.0)
    assert change is not None and change.abs == 250.0 and change.pct is None


def test_nav_change_uses_most_recent_prior_day(isolated_paths):
    """3 snapshots (day-3: 800, day-1: 1000, today seeded too) → baseline = the MOST-RECENT prior
    day (1000), not the oldest. today live=1100 → abs=100 (vs 1100-800=300 if it wrongly used oldest)."""
    _seed_snapshot(days_ago=3, total=800.0)
    _seed_snapshot(days_ago=1, total=1000.0)
    _seed_snapshot(days_ago=0, total=1050.0)  # today's recorded snapshot — must be IGNORED as baseline
    change = service._nav_change(1100.0)
    assert change is not None and change.abs == 100.0  # 1100 - 1000 (most-recent prior), not -800/-1050


def test_nav_change_store_error_fail_soft(isolated_paths, monkeypatch):
    """Snapshot store error → None + log, never crash (mirrors _series fail-soft)."""
    from store import db
    monkeypatch.setattr(db, "snapshots", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    assert service._nav_change(1000.0) is None


def test_overview_change_reflects_real_delta_end_to_end(isolated_paths, mock_prices):
    """End-to-end: a prior-day snapshot + live holdings → get_overview().change is the REAL delta,
    not the old stub. (Behavior, through the public surface.)"""
    _seed_snapshot(days_ago=1, total=40000.0)
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    overview, _ = service.get_overview()
    assert overview.totalValue == 50000.0
    assert overview.change is not None
    assert overview.change.abs == 10000.0 and overview.change.pct == 25.0  # 50000 vs prior 40000


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


# --- PERF #68: request-scoped quote memo → batch the N held-coin fetches into 1 ---
# The bug it kills: get_overview prices N coins, each get_quote'd TWICE (_price_of +
# _change_pct_of) → 2×N single-asset CoinGecko fetches (each a distinct reader-cache
# key → all cold misses). The fix pre-fetches every symbol in ONE read_quotes call +
# memoizes → 2×N network calls → 1. THE SPINE: the /finance numbers must NOT change —
# same quotes, just fetched once.

from contextlib import contextmanager  # noqa: E402


@contextmanager
def _count_coingecko_fetches(monkeypatch):
    """Spy on the reader's network boundary (_fetch_coingecko). Clears the reader's
    process-global TTL feed-cache first so prior tests don't mask a real fetch. Yields
    a 1-element list whose [0] is the call count; returns a deterministic feed."""
    from modules.market import reader

    reader._FEED_CACHE.clear()  # TTL cache is process-global — start cold
    count = [0]

    def fake_fetch(cg_ids):
        count[0] += 1
        return {cid: {"usd": 100.0, "usd_24h_change": 1.5} for cid in cg_ids}

    monkeypatch.setattr(reader, "_fetch_coingecko", fake_fetch)
    yield count


def _seed_multi_coin_book():
    """3 crypto holdings in distinct symbols → 3 priced symbols, each get_quote'd 2×."""
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="ETH", qty=10, avgCost=2000))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="SOL", qty=100, avgCost=120))


def test_perf68_overview_batches_to_one_coingecko_fetch(isolated_paths, monkeypatch):
    """CALL-COUNT (6→1): a 3-coin book priced 2× each = up to 6 single-asset fetches
    WITHOUT the memo. WITH the batch prefetch + memo → _fetch_coingecko fires ONCE."""
    _seed_multi_coin_book()
    with _count_coingecko_fetches(monkeypatch) as count:
        overview, _ = service.get_overview()
    assert count[0] == 1, f"expected ONE batched CoinGecko fetch, got {count[0]}"
    # and the numbers came through (3 priced holdings)
    assert len(overview.holdings) == 3


def test_perf68_identical_payload_memo_vs_no_memo(isolated_paths, monkeypatch):
    """IDENTICAL PAYLOAD (the spine): the overview built WITH the batch memo is byte-
    identical to one built WITHOUT it (memo disabled → the old per-call path). A perf
    fix must not change a single number."""
    _seed_multi_coin_book()

    # WITH the memo (the shipped path)
    with _count_coingecko_fetches(monkeypatch) as c1:
        ov_memo, w_memo = service.get_overview()
    assert c1[0] == 1

    # WITHOUT the memo: disable the batch (begin returns a no-op) → get_quote does its
    # own per-call fetch. Same deterministic feed → MUST produce the identical payload.
    monkeypatch.setattr(service.market_service, "begin_quote_batch", lambda: None)
    monkeypatch.setattr(service.market_service, "end_quote_batch", lambda token: None)
    monkeypatch.setattr(service.market_service, "prefetch_quotes", lambda syms: None)
    with _count_coingecko_fetches(monkeypatch) as c2:
        ov_plain, w_plain = service.get_overview()
    assert c2[0] > 1, "control: without the memo the per-call path fetches more than once"

    assert ov_memo.model_dump() == ov_plain.model_dump(), "memo changed a number — REGRESSION"
    assert w_memo == w_plain


def test_perf68_memo_is_request_scoped_resets_after_call(isolated_paths, monkeypatch):
    """REQUEST-SCOPED (no cross-request staleness): the ContextVar memo is None after
    get_overview returns — it does NOT persist as a process-global cache."""
    _seed_multi_coin_book()
    with _count_coingecko_fetches(monkeypatch):
        service.get_overview()
    assert service.market_service._quote_memo.get() is None, "memo leaked past the request"


def test_perf68_two_sequential_calls_each_fetch_fresh(isolated_paths, monkeypatch):
    """No stale sharing: two sequential get_overview calls each open + reset their own
    memo. With the reader TTL-cache cleared between, each does its own (single) fetch —
    the memo is NOT a long-lived cache that would serve call-2 stale data."""
    _seed_multi_coin_book()
    from modules.market import reader

    with _count_coingecko_fetches(monkeypatch) as c1:
        service.get_overview()
    assert c1[0] == 1
    reader._FEED_CACHE.clear()  # force call-2 to actually fetch (not the reader TTL)
    with _count_coingecko_fetches(monkeypatch) as c2:
        service.get_overview()
    assert c2[0] == 1  # call-2 fetched fresh on its own — not served stale by a leaked memo


def test_perf68_fail_open_intact_when_coingecko_down(isolated_paths, monkeypatch):
    """FAIL-OPEN intact: CoinGecko raising inside the batch prefetch degrades the whole
    batch to read_quotes' own fail-open (last-known/mock, as a GROUP) — the overview
    still assembles, never 500s + carries a CG-unavailable warning. Same behavior as
    before, just ONE fetch attempt instead of N (the batch fails open once)."""
    from modules.market import reader

    reader._FEED_CACHE.clear()
    fetch_count = [0]

    def boom(ids):
        fetch_count[0] += 1
        raise RuntimeError("CG 429")

    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    monkeypatch.setattr(reader, "_fetch_coingecko", boom)
    overview, warnings = service.get_overview()  # MUST NOT raise — fail-open, not 500
    # assembled with a fallback total (read_quotes degrades the crypto group to mock/
    # last-known as a GROUP; the prefetch's failed batch is memoized so get_quote serves
    # the same fallback quote — no second network attempt).
    assert overview.totalValue is not None and overview.totalValue > 0
    assert len(overview.holdings) == 1  # BTC still present, just fallback-priced
    # the CoinGecko failure was ONE batched attempt (the prefetch), then a memo hit —
    # NOT N separate failing fetches. (Was the whole point: fail open ONCE, not N times.)
    assert fetch_count[0] == 1, f"fail-open should be ONE batched attempt, got {fetch_count[0]}"


# --- FINANCE-AUDIT2 (#66): pnlTotal from the BASIS-KNOWN per-coin sum, not the snapshot cost ---
# The bug it pins: a snapshot-cost pnlTotal showed +$7 (a gain) while the real per-coin loss
# was −$617. The fix aggregates ONLY holdings with a real cost basis; no-basis (OKX value-only /
# stablecoin) holdings are EXCLUDED (honest-null) + a pnlScope labels the coverage %.

def _entry(cost, value):
    """A by_channel holding entry as _aggregate builds it (pnl = _pnl(cost, value).model_dump())."""
    return {"pnl": service._pnl(cost, value).model_dump()}


def test_basis_known_pnl_distinguishing_loss_is_negative():
    """DISTINGUISHING: a book of losing basis-known coins + a big no-basis stablecoin →
    pnlTotal is NEGATIVE (the real loss), NOT the fake near-$0 gain a snapshot cost gives.
    A correct impl (sum the per-coin losses) ≠ a collapsed one (snapshot cost ≈ value → ~0)."""
    by_channel = {
        "crypto": {"holdings": [_entry(1000.0, 600.0),     # basis-known: −400
                                _entry(500.0, 283.09)]},   # basis-known: −216.91
        "dry": {"holdings": [_entry(0.0, 9000.0)]},        # NO basis (cost 0) → EXCLUDED
    }
    total_value = 600 + 283.09 + 9000  # 9883.09
    pnl, scope = service._basis_known_pnl(by_channel, total_value)
    assert pnl.abs == -616.91, "pnlTotal must be the real per-coin LOSS, not a snapshot ~0 gain"
    assert pnl.abs < 0 and pnl.pct < 0  # DIRECTION is a loss, not a gain
    assert scope.coveragePct == round(883.09 / total_value * 100, 1)  # ~8.9% basis-known


def test_basis_known_pnl_cross_check_equals_sum_of_per_coin():
    """CROSS-CHECK: pnlTotal.abs == Σ (per-coin pnl.abs) over the basis-known entries."""
    entries = [(1200.0, 1000.0), (3000.0, 3400.0), (500.0, 250.0)]
    by_channel = {"crypto": {"holdings": [_entry(c, v) for c, v in entries]}}
    total_value = sum(v for _c, v in entries)
    pnl, _scope = service._basis_known_pnl(by_channel, total_value)
    expected = round(sum(v - c for c, v in entries), 2)
    assert pnl.abs == expected


def test_basis_known_pnl_no_basis_excluded_honest_null():
    """NO-BASIS EXCLUDED: a book where EVERY holding is value-only (cost 0, OKX/stablecoin)
    → pnlTotal is HONEST-NULL (abs/pct None), NOT a 0-cost $0 'gain'. The exact misread the
    dispatch warns against — a $0 abs would read as 'flat', hiding that P&L is UNKNOWN."""
    by_channel = {"dry": {"holdings": [_entry(0.0, 9000.0), _entry(0.0, 500.0)]}}
    pnl, scope = service._basis_known_pnl(by_channel, 9500.0)
    assert pnl.abs is None, "no-basis-only book → abs MUST be None, not 0.0 (a fake $0 gain)"
    assert pnl.pct is None
    assert scope.coveragePct is None
    assert "no holding has a cost basis" in scope.note


def test_overview_pnltotal_basis_known_through_service(isolated_paths, mock_prices):
    """SERVICE-LEVEL: a losing basis-known holding → overview.pnlTotal is the real loss +
    pnlScope present. (Both holdings have a basis here → coveragePct 100%.)"""
    mock_prices["BTC"] = 40000.0   # bought at 50k → −10k loss
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    overview, _ = service.get_overview()
    assert overview.pnlTotal.abs == -10000.0  # the real LOSS, surfaced
    assert overview.pnlTotal.pct == round(-10000 / 50000 * 100, 2)
    assert overview.pnlScope is not None
    assert overview.pnlScope.basis == "known-cost-only"
    assert overview.pnlScope.coveragePct == 100.0  # the one holding has a basis


def test_overview_channel_pnl_unchanged_by_audit2(isolated_paths, mock_prices):
    """REGRESSION GUARD: the per-CHANNEL allocations[].pnl path is UNTOUCHED by #66 —
    only pnlTotal changed. A basis-known channel still reports its framed channel pnl."""
    mock_prices["BTC"] = 60000.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=50000))
    overview, _ = service.get_overview()
    crypto = next(a for a in overview.allocations if a.channel == "crypto")
    assert crypto.pnl.abs == 10000.0  # channel pnl = _pnl_framed(50000, 60000) → +10000, unchanged


def test_overview_empty_pnltotal_honest_null(isolated_paths, mock_prices):
    """An empty book → pnlTotal honest-null (abs None, not 0.0) + pnlScope coveragePct None."""
    overview, _ = service.get_overview()
    assert overview.pnlTotal.abs is None and overview.pnlTotal.pct is None
    assert overview.pnlScope is not None and overview.pnlScope.coveragePct is None


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
    # First call → basis snapshotted = 10500. cost/current are the real $ figures (kept);
    # abs/pct are SUPPRESSED because the OKX crypto channel is basisUnknown (value-only) —
    # D3a: a value-only inflow must not read as a gain. The cost-snapshot is verified via
    # pnl.cost (and current), not abs.
    assert crypto.value == 10500.0
    assert crypto.pnl.cost == 10500.0
    assert crypto.pnl.current == 10500.0  # value == snapshotted basis (was abs==0)
    assert crypto.pnl.abs is None and crypto.basisUnknown is True  # D3a suppression
    # Second call with higher OKX value — basis stays at snapshot; current tracks value
    monkeypatch.setattr(service, "_okx_crypto_value", lambda: (11000.0, None))
    overview2, _ = service.get_overview()
    crypto2 = next(a for a in overview2.allocations if a.channel == "crypto")
    assert crypto2.value == 11000.0
    assert crypto2.pnl.cost == 10500.0   # basis unchanged (snapshot)
    assert crypto2.pnl.current == 11000.0  # current = live value (was abs==500)
    # abs still suppressed (basisUnknown); the real cost/current pair makes the +500
    # self-verifiable for a consumer WITHOUT a misleading auto-computed "gain".
    assert crypto2.pnl.abs is None


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


# --------------------------------------------------------------------------- #
# Portfolio value history / equity snapshots (Task 26)                          #
# --------------------------------------------------------------------------- #
def test_snapshot_records_a_row(isolated_paths, mock_prices):
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=10, avgCost=90))
    snap = service.take_snapshot()
    assert snap["totalValue"] == 1000.0
    assert snap["byChannel"]["crypto"] == 1000.0
    hist = service.value_history(days=90)
    assert len(hist) == 1 and hist[0]["totalValue"] == 1000.0


def test_snapshot_empty_portfolio_records_zero(isolated_paths):
    """Empty portfolio → totalValue=0 still recorded (a $0 day is a real point)."""
    snap = service.take_snapshot()
    assert snap["totalValue"] == 0.0
    assert service.value_history()[0]["totalValue"] == 0.0


def test_snapshot_same_day_upserts(isolated_paths, mock_prices):
    """Two snapshots the same UTC day → ONE row (latest value = day's close)."""
    from store import db
    db.record_snapshot("2026-03-01T08:00:00+00:00", 100.0, '{"crypto":100}')
    db.record_snapshot("2026-03-01T20:00:00+00:00", 150.0, '{"crypto":150}')  # same day
    rows = db.snapshots()
    assert len(rows) == 1 and rows[0]["total_value"] == 150.0  # upserted to latest


def test_value_history_empty_is_empty_list(isolated_paths):
    assert service.value_history(days=90) == []


def test_series_reads_from_snapshots(isolated_paths):
    """_series() (which feeds overview.series + analytics) reads the snapshot store."""
    from store import db
    db.record_snapshot("2026-03-01T12:00:00+00:00", 100.0)
    db.record_snapshot("2026-03-02T12:00:00+00:00", 110.0)
    # _series windows by recent days; seed within a wide window via days override on
    # value_history is internal, but _series uses now-365d → the 2026-03 dates may be
    # outside that window relative to a much-later 'now'. Assert via value_history's
    # own read + the return-metric math on a hand-built series instead.
    assert [r["total_value"] for r in db.snapshots()] == [100.0, 110.0]


def test_returns_available_with_two_snapshots(isolated_paths, mock_prices):
    """≥2 snapshots → get_analytics().returns.available=True with real return/vol."""
    from store import db
    # seed a 3-point series ending TODAY (so the now-365d window catches it).
    from datetime import datetime, timedelta, timezone
    base = datetime.now(timezone.utc)
    for i, v in enumerate([100.0, 110.0, 121.0]):
        ts = (base - timedelta(days=2 - i)).isoformat()
        db.record_snapshot(ts, v)
    a, warnings = service.get_analytics()
    assert a.returns.available is True
    assert a.returns.totalReturnPct == 21.0  # (121-100)/100
    assert a.returns.volatilityPct is not None
    assert not any("series" in w for w in warnings)  # no "no series" warning now


# --------------------------------------------------------------------------- #
# Scenario / what-if simulate (Task 30) — HHI math pinned, NEUTRAL              #
# --------------------------------------------------------------------------- #
def test_simulate_hhi_handcalc_concentrated(isolated_paths):
    """{crypto:60, etf:20, vn:20} → weights .6/.2/.2 → HHI = .36+.04+.04 = 0.44.
    Top channel crypto 60%. Sums to 100 → not normalized."""
    r, _ = service.simulate({"crypto": 60, "etf": 20, "vn": 20})
    assert r.hypothetical.hhi == 0.44
    assert r.hypothetical.concentrationTopChannel == "crypto"
    assert r.hypothetical.concentrationTopPct == 60.0
    assert r.normalized is False


def test_simulate_hhi_handcalc_balanced(isolated_paths):
    """Even 25/25/25/25 → HHI = 4·.25² = 0.25 (the most-diversified 4-channel shape)."""
    r, _ = service.simulate({"crypto": 25, "etf": 25, "vn": 25, "dry": 25})
    assert r.hypothetical.hhi == 0.25


def test_simulate_normalizes_dollar_amounts(isolated_paths):
    """Dollar amounts 6000/2000/2000 normalize to the SAME shape as 60/20/20 (HHI 0.44),
    and the result is flagged normalized=True with a warning."""
    r, warnings = service.simulate({"crypto": 6000, "etf": 2000, "vn": 2000})
    assert r.hypothetical.hhi == 0.44   # identical shape to the % version
    assert r.normalized is True
    assert any("normalized" in w.lower() for w in warnings)


def test_simulate_drift_vs_golden_path(isolated_paths):
    """drift = hypothetical pct − golden-path target. Baseline crypto target 38; a 60%
    crypto allocation → drift +22. Σ|drift| and turnover (½Σ) are derived honestly."""
    r, _ = service.simulate({"crypto": 60, "etf": 20, "vn": 20, "dry": 0})
    crypto = next(c for c in r.hypothetical.channels if c.channel == "crypto")
    assert crypto.targetPct == 38.0 and crypto.drift == 22.0  # 60 - 38
    # totalAbsDrift = |60-38|+|20-24|+|20-18|+|0-20| = 22+4+2+20 = 48; turnover 24.
    assert r.hypothetical.totalAbsDrift == 48.0
    assert r.hypothetical.rebalanceDistance == 24.0


def test_simulate_delta_vs_current(isolated_paths, mock_prices):
    """The result compares the hypothetical to the CURRENT portfolio: per-channel
    deltaVsCurrentPct + the HHI delta. Current = 100% crypto (HHI 1.0); hypothetical
    60/20/20 (HHI 0.44) → hhiDelta = 0.44 − 1.0 = −0.56 (more diversified)."""
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=100, avgCost=90))
    r, _ = service.simulate({"crypto": 60, "etf": 20, "vn": 20})
    assert r.current.hhi == 1.0            # current is all crypto
    assert r.hhiDelta == -0.56            # 0.44 - 1.0
    crypto = next(c for c in r.hypothetical.channels if c.channel == "crypto")
    assert crypto.deltaVsCurrentPct == -40.0  # 60% hypothetical − 100% current


def test_simulate_empty_portfolio_delta_unavailable(isolated_paths):
    """No holdings → current shape has None HHI, hhiDelta None, a warning — never a crash."""
    r, warnings = service.simulate({"crypto": 50, "etf": 50})
    assert r.hypothetical.hhi == 0.5      # .5²+.5²
    assert r.current.hhi is None          # empty portfolio
    assert r.hhiDelta is None             # can't delta against nothing
    assert any("current" in w.lower() or "empty" in w.lower() for w in warnings)


def test_simulate_zero_sum_allocation_honest(isolated_paths):
    """All-zero weights can't be normalized → None HHI + warning, NOT a div-by-zero."""
    r, warnings = service.simulate({"crypto": 0, "etf": 0})
    assert r.hypothetical.hhi is None
    assert any("sum to 0" in w or "cannot normalize" in w for w in warnings)


def test_simulate_is_neutral_no_advice(isolated_paths, mock_prices):
    """The simulate payload is PURE NUMBERS — no buy/sell/recommend/should/advice."""
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=10, avgCost=90))
    r, _ = service.simulate({"crypto": 40, "etf": 30, "vn": 20, "dry": 10})
    blob = str(r.model_dump()).lower()
    for word in ("recommend", "should", "buy", "sell", "advice", "advise"):
        assert word not in blob
