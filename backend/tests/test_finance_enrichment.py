"""tests/test_finance_enrichment.py — FINANCE-CORRECTNESS (Task #49).

Per-holding enrichment (price/usdValue/changePct surfaced from _aggregate's already-
computed numbers — NEVER re-priced) + sub-$1 dust fold into one per-channel ·dust entry.

Behavior-tested (not field-read): seed holdings + mock prices → call get_overview() →
assert the SURFACED numbers + the dust fold + the consistency invariant. Uses DIVERGENT
fixtures (a real token, a sub-$1 dust, a missing-quote holding, an unpriceable holding)
so a collapsed/wrong impl gives a different answer than a correct one (memory
verify-with-the-distinguishing-case).

NOTE: the dust-window boundary (whether a priced-sub-cent coin whose usdValue ROUNDS to
0.0 folds) is governed by the team-lead ruling on the spec gap flagged this sprint. These
tests assert the SETTLED behavior; the exact 0.0-boundary case is marked where it depends
on that ruling.
"""

from __future__ import annotations

import pytest

from modules.finance import service
from modules.finance.schema import HoldingInput, Holding
from modules.market.schema import AssetQuote


def _mock_quote(symbol, price, change_pct=None):
    return AssetQuote(symbol=symbol, name=symbol, assetClass="crypto", price=price,
                      currency="USD", ts="2026-06-16T00:00:00+00:00", source="coingecko",
                      changePct=change_pct)


@pytest.fixture(autouse=True)
def no_okx_override(monkeypatch):
    """Disable the live OKX override so these tests exercise the manual-holdings path
    deterministically (the dev box has a live OKX snapshot that would otherwise replace
    the crypto channel). OKX-specific enrichment is tested separately below by patching
    _okx_crypto_holdings directly."""
    monkeypatch.setattr(service, "_okx_crypto_value", lambda: (None, None))


@pytest.fixture
def mock_prices(monkeypatch):
    """A price book: symbol -> price (or (price, changePct)). A symbol NOT in the book →
    get_quote returns None → the cost-fallback pricing path (price=avgCost, changePct null)."""
    book: dict[str, float] = {}

    def fake_get_quote(symbol):
        if symbol not in book:
            return None
        entry = book[symbol]
        if isinstance(entry, tuple):
            return _mock_quote(symbol, entry[0], entry[1])
        return _mock_quote(symbol, entry)

    monkeypatch.setattr(service.market_service, "get_quote", fake_get_quote)
    return book


def _find(holdings: list[Holding], symbol: str) -> Holding | None:
    return next((h for h in holdings if h.symbol == symbol), None)


# --------------------------------------------------------------------------- #
# T1 — per-holding price/usdValue SURFACED from the already-computed numbers    #
# --------------------------------------------------------------------------- #
def test_real_holding_surfaces_price_and_usdvalue(isolated_paths, mock_prices):
    """A priced holding carries the real price + usdValue (= price×qty) on the flat
    holdings list — the numbers _aggregate already computed, NOT re-priced."""
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=3, avgCost=80))
    ov, _ = service.get_overview()
    btc = _find(ov.holdings, "BTC")
    assert btc is not None
    assert btc.price == 100.0
    assert btc.usdValue == 300.0       # 100 × 3 — surfaced, self-describing
    assert btc.isDust is False and btc.count is None


def test_changepct_surfaced_from_market_feed(isolated_paths, mock_prices):
    """changePct is derived via market.derive_change_pct (the watchlist's one feed). With
    a feed-fallback changePct on the quote (and no own series), it surfaces that value."""
    mock_prices["ETH"] = (2000.0, 5.5)   # quote carries a 24h change → feed fallback
    service.upsert_holding(HoldingInput(channel="crypto", symbol="ETH", qty=1, avgCost=1500))
    ov, _ = service.get_overview()
    eth = _find(ov.holdings, "ETH")
    assert eth is not None and eth.changePct == 5.5   # surfaced from the feed fallback


def test_missing_quote_usdvalue_is_avgcost_estimate_changepct_null(isolated_paths, mock_prices):
    """A symbol with NO market quote → cost-fallback: usdValue = avgCost×qty (honest
    ESTIMATE, not 0, not null) but changePct NULL (no live quote to derive a real %).
    Documents which path yields what (dispatch honest-null rule)."""
    # GHOST not in the price book → get_quote None → cost-fallback
    service.upsert_holding(HoldingInput(channel="etf", symbol="GHOST", qty=10, avgCost=5))
    ov, _ = service.get_overview()
    ghost = _find(ov.holdings, "GHOST")
    assert ghost is not None
    assert ghost.usdValue == 50.0      # 5 × 10 honest estimate (NOT 0, NOT null)
    assert ghost.price == 5.0          # avgCost as the fallback price
    assert ghost.changePct is None     # no live quote → null, never fabricated


# --------------------------------------------------------------------------- #
# CONSISTENCY INVARIANT — sum(per-holding usdValue per channel, incl dust) ≈    #
# channel allocations[].value, with rounding TOLERANCE (team-lead lock #1)      #
# --------------------------------------------------------------------------- #
def test_consistency_invariant_sum_matches_channel_value(isolated_paths, mock_prices):
    """The per-holding usdValue numbers (INCLUDING the dust summary) must sum to the
    channel's ChannelAlloc.value within ±$0.01 per holding (each value is round(price*qty,2),
    so summing N rounded values ≠ the channel's own rounded sum — use tolerance, not ==)."""
    mock_prices.update({"BTC": 100.0, "ETH": 33.33, "VOO": 7.77})
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=2, avgCost=80))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="ETH", qty=3, avgCost=20))
    service.upsert_holding(HoldingInput(channel="etf", symbol="VOO", qty=11, avgCost=5))
    ov, _ = service.get_overview()
    by_channel_sum: dict[str, float] = {}
    by_channel_n: dict[str, int] = {}
    for h in ov.holdings:
        by_channel_sum[h.channel] = round(by_channel_sum.get(h.channel, 0.0) + float(h.usdValue or 0.0), 2)
        by_channel_n[h.channel] = by_channel_n.get(h.channel, 0) + 1
    for alloc in ov.allocations:
        n = max(by_channel_n.get(alloc.channel, 1), 1)
        tol = 0.01 * n
        assert abs(by_channel_sum.get(alloc.channel, 0.0) - alloc.value) <= tol, (
            f"{alloc.channel}: sum(holdings usdValue)={by_channel_sum.get(alloc.channel)} "
            f"vs alloc.value={alloc.value} exceeds ±{tol}"
        )


# --------------------------------------------------------------------------- #
# T2 — dust fold: sub-$1 holdings collapse into one ·dust summary entry          #
# --------------------------------------------------------------------------- #
def test_dust_folds_into_one_summary_entry(isolated_paths, mock_prices):
    """DISTINGUISHING: a real token stays individual; ≥2 sub-$1 holdings in a channel
    collapse into ONE ·dust entry (isDust, count=n, usdValue=sum). A correct impl differs
    from a no-fold impl (which would show 3 individual crypto lines)."""
    mock_prices.update({"BTC": 100.0, "DUSTA": 0.30, "DUSTB": 0.20})
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))    # $100 real
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTA", qty=1, avgCost=0.1)) # $0.30 dust
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTB", qty=1, avgCost=0.1)) # $0.20 dust
    ov, _ = service.get_overview()
    crypto = [h for h in ov.holdings if h.channel == "crypto"]
    # BTC individual + ONE dust entry = 2 lines (not 3)
    assert _find(crypto, "BTC") is not None
    dust = [h for h in crypto if h.isDust]
    assert len(dust) == 1, f"expected exactly one ·dust entry, got {[h.symbol for h in crypto]}"
    d = dust[0]
    assert d.symbol == service.DUST_SYMBOL
    assert d.count == 2                          # two folded holdings
    assert d.usdValue == 0.5                     # 0.30 + 0.20 — value preserved
    assert d.price is None and d.changePct is None   # a sum-of-many has no single price


def test_dust_entry_is_a_valid_holding(isolated_paths, mock_prices):
    """team-lead lock #2: the ·dust entry passes Holding's field constraints — qty=0 is OK
    (ge=0), symbol='·dust' is OK (min_length=1) — and a real token never literally collides
    with '·dust' (the · prefix is collision-proof)."""
    mock_prices["DUSTA"] = 0.50
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTA", qty=1, avgCost=0.1))
    ov, _ = service.get_overview()
    dust = next(h for h in ov.holdings if h.isDust)
    # it IS a valid Holding (constructed without raising) — re-validate to be explicit
    Holding(**dust.model_dump())
    assert dust.qty == 0                         # ge=0 allows 0
    assert dust.symbol == "·dust" and len(dust.symbol) >= 1
    # no REAL holding ever has the dust symbol (collision-proof prefix)
    reals = [h for h in ov.holdings if not h.isDust]
    assert all(h.symbol != service.DUST_SYMBOL for h in reals)


def test_null_usdvalue_is_not_folded(isolated_paths, mock_prices):
    """dispatch lock (d): null≠dust. An UNPRICEABLE holding (no quote AND no avgCost →
    usdValue None) is NOT folded — unknown ≠ small, it stays visible individually so the
    agent sees 'I don't know this token's worth', not a hidden dust line."""
    # GHOSTNOBASIS: no quote (not in book) AND avgCost 0 → price fallback 0, value 0,
    # _holding_from_entry → usdValue None (price 0 path: price is 0 not None, value 0).
    # To force the TRUE unpriceable path (price None) we use an OKX-style entry below; here
    # we assert the manual no-basis case stays visible (not folded into dust).
    service.upsert_holding(HoldingInput(channel="etf", symbol="GHOSTNOBASIS", qty=1, avgCost=0))
    ov, _ = service.get_overview()
    g = _find(ov.holdings, "GHOSTNOBASIS")
    assert g is not None, "a no-basis holding must stay visible, never folded away"
    assert g.isDust is False


def test_unpriceable_null_usdvalue_stays_individual(isolated_paths, mock_prices, monkeypatch):
    """The TRUE unpriceable path (price None → usdValue None): an OKX value-only coin with
    no usdValue. It must surface usdValue=None (NOT 0) AND stay individual (null≠dust)."""
    # Patch the OKX path to yield one unpriceable coin (price None, value 0).
    now = "2026-06-16T00:00:00+00:00"
    unpriceable = Holding(channel="crypto", symbol="NOVALUE", qty=5, avgCost=None,
                          source="okx", asOf=now)
    monkeypatch.setattr(service, "_okx_crypto_value", lambda: (1000.0, None))
    monkeypatch.setattr(service, "_ensure_crypto_basis", lambda v: 0.0)
    monkeypatch.setattr(service, "_okx_crypto_holdings", lambda: [
        {"holding": unpriceable.model_dump(), "price": None, "source": "okx",
         "value": 0.0, "pnl": None, "changePct": None},
    ])
    ov, _ = service.get_overview()
    nv = _find(ov.holdings, "NOVALUE")
    assert nv is not None, "an unpriceable coin must stay visible (unknown ≠ small)"
    assert nv.usdValue is None            # missing price ≠ zero worth
    assert nv.isDust is False             # null is NOT folded


def test_priced_subcent_usdvalue_zero_IS_folded(isolated_paths, mock_prices):
    """THE BUG-KILLER (team-lead RULING, the distinguishing case): a coin OKX/market PRICES
    at sub-cent — price NOT null, but usdValue ROUNDS to exactly 0.0 (ETH/LINK/DOGE 1e-7 qty,
    the consumer-agent's literal complaint) — MUST fold into ·dust. A test with usdValue=0.50
    would pass even against the broken `0 < usdValue` predicate; this one uses a 0.0-usdValue-
    WITH-price fixture so the `0 ≤` boundary is actually exercised (folds under the ruling,
    would stay an ugly $0.00 line under the literal `0<`)."""
    mock_prices.update({"BTC": 100.0, "TINY": 1e-9})   # TINY priced but 1e-9 → value rounds to 0.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="TINY", qty=1, avgCost=0))
    ov, _ = service.get_overview()
    tiny = _find(ov.holdings, "TINY")
    assert tiny is None, "a priced sub-cent (usdValue==0.0) coin must be FOLDED, not an individual $0.00 line"
    dust = [h for h in ov.holdings if h.isDust and h.channel == "crypto"]
    assert len(dust) == 1 and dust[0].count == 1     # TINY folded into the dust summary
    # the priced-but-0.0 coin had a non-null price → it WAS dust-eligible (the distinguishing fact)


def test_usdvalue_exactly_one_dollar_not_folded(isolated_paths, mock_prices):
    """BOUNDARY: usdValue EXACTLY $1.00 is NOT dust (< threshold is STRICT — ≥ threshold
    stays visible). Proves the strict inequality, not ≤."""
    mock_prices["ONEBUCK"] = 1.00
    service.upsert_holding(HoldingInput(channel="crypto", symbol="ONEBUCK", qty=1, avgCost=0.5))
    ov, _ = service.get_overview()
    one = _find(ov.holdings, "ONEBUCK")
    assert one is not None and one.usdValue == 1.00 and one.isDust is False
    assert not any(h.isDust for h in ov.holdings)    # exactly $1 → no dust entry


def test_real_token_big_value_stays_individual(isolated_paths, mock_prices):
    """A real token well above $1 (PEPE-like big qty) stays an individual line, never folded."""
    mock_prices["PEPE"] = 0.000001
    service.upsert_holding(HoldingInput(channel="crypto", symbol="PEPE", qty=50_000_000, avgCost=0))  # $50
    ov, _ = service.get_overview()
    pepe = _find(ov.holdings, "PEPE")
    assert pepe is not None and pepe.usdValue == 50.0 and pepe.isDust is False


def test_no_dust_entry_when_no_dust(isolated_paths, mock_prices):
    """0 sub-$1 holdings in a channel → NO ·dust entry (honest: don't invent an empty one)."""
    mock_prices["BTC"] = 100.0
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))
    ov, _ = service.get_overview()
    assert not any(h.isDust for h in ov.holdings)


def test_dust_fold_does_not_change_total_or_channel_value(isolated_paths, mock_prices):
    """The fold is DISPLAY-only: totalValue + channel value are UNCHANGED (the dust's
    usdValue still counts — it's summed into the channel value before the fold)."""
    mock_prices.update({"BTC": 100.0, "DUSTA": 0.40, "DUSTB": 0.40})
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTA", qty=1, avgCost=0.1))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTB", qty=1, avgCost=0.1))
    ov, _ = service.get_overview()
    # total = 100 + 0.40 + 0.40 = 100.80 (dust value counted, not dropped)
    assert ov.totalValue == 100.8
    crypto_alloc = next(a for a in ov.allocations if a.channel == "crypto")
    assert crypto_alloc.value == 100.8


# --------------------------------------------------------------------------- #
# (e) consumers still work — read_server holdingCount counts the dust line       #
# --------------------------------------------------------------------------- #
def test_read_server_holding_count_is_sane_with_dust(isolated_paths, mock_prices):
    """The read-server _brief_portfolio reads len(ov.holdings) as holdingCount. With a
    dust fold the count includes the ·dust line as 1 (fine) — assert it's the expected
    folded count, not a crash and not the pre-fold count."""
    from mcp_servers import read_server as rs
    mock_prices.update({"BTC": 100.0, "DUSTA": 0.30, "DUSTB": 0.20})
    service.upsert_holding(HoldingInput(channel="crypto", symbol="BTC", qty=1, avgCost=80))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTA", qty=1, avgCost=0.1))
    service.upsert_holding(HoldingInput(channel="crypto", symbol="DUSTB", qty=1, avgCost=0.1))
    # _brief_portfolio is the consumer of len(ov.holdings)
    portfolio = rs._brief_portfolio()
    # BTC + one ·dust line = 2 (the two dust holdings folded to one)
    assert portfolio["holdingCount"] == 2
