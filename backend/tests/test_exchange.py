"""tests/test_exchange.py — exchange module unit tests (mocked httpx)."""

from __future__ import annotations

import importlib
import pytest
from unittest.mock import MagicMock, patch

import pytest
import respx
import httpx

from modules.exchange import service
from modules.exchange.schema import ExchangeOverview


@pytest.fixture(autouse=True)
def reset_snapshot():
    """Reset in-memory cache between tests."""
    service._last_snapshot = None
    yield
    service._last_snapshot = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _with_creds(**kw):
    """Patch all three OKX credential settings at once."""
    return [
        patch.object(service.settings, "okx_api_key",        kw.get("key", "key")),
        patch.object(service.settings, "okx_api_secret",     kw.get("secret", "secret")),
        patch.object(service.settings, "okx_api_passphrase", kw.get("pass_", "pass")),
    ]


def test_unconfigured_returns_empty_overview():
    """When no API key set, returns configured=False, totalUsdValue=0."""
    with patch.object(service.settings, "okx_api_key", ""), \
         patch.object(service.settings, "okx_api_secret", ""), \
         patch.object(service.settings, "okx_api_passphrase", ""):
        overview, warning = service.sync()
    assert overview.configured is False
    assert overview.totalUsdValue == 0.0
    assert overview.balances == []
    assert warning is None


def test_sync_parses_balances():
    """Sync with mocked reader returns parsed OkxBalance list."""
    raw_balances = [
        {"ccy": "BTC", "availBal": "0.5", "frozenBal": "0.1", "eqUsd": "30000.0"},
        {"ccy": "USDT", "availBal": "1000", "frozenBal": "0", "eqUsd": "1000.0"},
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw_balances), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, warning = service.sync()

    assert overview.configured is True
    assert overview.totalUsdValue == pytest.approx(31000.0)
    assert len(overview.balances) == 2
    # BTC should be first (higher USD value)
    assert overview.balances[0].symbol == "BTC"
    assert overview.balances[0].total == pytest.approx(0.6)


def test_sync_handles_balance_fetch_error():
    """If balance fetch fails, returns empty balances with a warning."""
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", side_effect=Exception("timeout")), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, warning = service.sync()

    assert overview.balances == []
    assert warning is not None
    assert "balance fetch failed" in warning


def test_get_overview_caches_snapshot():
    """get_overview returns cached result on second call without re-fetching."""
    raw_balances = [{"ccy": "ETH", "availBal": "2.0", "frozenBal": "0", "eqUsd": "6000.0"}]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw_balances) as mock_bal, \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        service.get_overview()
        service.get_overview()  # second call — should use cache

    assert mock_bal.call_count == 1  # fetched once, not twice


def test_sync_parses_positions():
    """Sync with open positions returns OkxPosition list."""
    raw_positions = [
        {
            "instId": "BTC-USDT-SWAP",
            "posSide": "long",
            "pos": "0.1",
            "avgPx": "65000",
            "upl": "500.0",
            "margin": "1300.0",
            "lever": "5",
        }
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=[]), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=raw_positions):
        overview, _ = service.sync()

    assert len(overview.positions) == 1
    pos = overview.positions[0]
    assert pos.instId == "BTC-USDT-SWAP"
    assert pos.side == "long"
    assert pos.unrealizedPnl == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# A4 — edge cases / error paths not previously covered
# ---------------------------------------------------------------------------

def test_malformed_balance_item_skipped_rest_parsed():
    """A balance item with a non-numeric availBal is silently skipped;
    the valid item that follows is still parsed (parse continues, doesn't abort)."""
    raw = [
        {"ccy": "BAD", "availBal": "not-a-number", "frozenBal": "0", "eqUsd": "100"},
        {"ccy": "USDT", "availBal": "500", "frozenBal": "0", "eqUsd": "500.0"},
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, _ = service.sync()

    # BAD item is dropped; USDT is present
    syms = [b.symbol for b in overview.balances]
    assert "BAD" not in syms
    assert "USDT" in syms
    assert overview.totalUsdValue == pytest.approx(500.0)


def test_balance_eqUsd_zero_string_not_counted_in_total():
    """A balance with eqUsd='0' (or '') → usdValue=None; NOT added to totalUsdValue."""
    raw = [
        {"ccy": "DUST", "availBal": "1000", "frozenBal": "0", "eqUsd": "0"},
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, _ = service.sync()

    assert overview.totalUsdValue == pytest.approx(0.0)
    assert overview.balances[0].usdValue is None


def test_balance_eqUsd_empty_string_treated_as_none():
    """eqUsd='' → usdValue=None, not an error."""
    raw = [{"ccy": "XRP", "availBal": "200", "frozenBal": "0", "eqUsd": ""}]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, _ = service.sync()

    assert overview.balances[0].usdValue is None
    assert overview.totalUsdValue == pytest.approx(0.0)


def test_position_qty_zero_parsed_not_skipped():
    """pos='0' (zero quantity) is a valid position, parsed as qty=0.0 (boundary check)."""
    raw_positions = [{
        "instId": "ETH-USDT-SWAP", "posSide": "short",
        "pos": "0", "avgPx": "3000", "upl": "0", "margin": "0", "lever": "10",
    }]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=[]), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=raw_positions):
        overview, _ = service.sync()

    assert len(overview.positions) == 1
    assert overview.positions[0].qty == pytest.approx(0.0)


def test_malformed_position_item_skipped_rest_parsed():
    """A position item with a non-numeric pos is skipped; a valid item still parsed."""
    raw_positions = [
        {"instId": "BAD-SWAP", "posSide": "long", "pos": "???", "avgPx": "1", "upl": "0", "margin": "0", "lever": "1"},
        {"instId": "BTC-USDT-SWAP", "posSide": "long", "pos": "1", "avgPx": "60000", "upl": "100", "margin": "1000", "lever": "5"},
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=[]), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=raw_positions):
        overview, _ = service.sync()

    inst_ids = [p.instId for p in overview.positions]
    assert "BAD-SWAP" not in inst_ids
    assert "BTC-USDT-SWAP" in inst_ids


def test_position_fetch_error_balances_still_present():
    """Position fetch throws → positions=[], warning mentions 'position fetch failed',
    but the balance list is still populated (two independent fail-soft paths)."""
    raw_bal = [{"ccy": "BTC", "availBal": "1", "frozenBal": "0", "eqUsd": "60000"}]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw_bal), \
         patch("modules.exchange.service.reader.fetch_positions", side_effect=Exception("positions down")):
        overview, warning = service.sync()

    assert len(overview.balances) == 1
    assert overview.balances[0].symbol == "BTC"
    assert overview.positions == []
    assert warning is not None
    assert "position fetch failed" in warning


def test_both_fetches_fail_empty_snapshot_two_warnings():
    """Both balance + position fetches throw → empty snapshot, warning contains both."""
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", side_effect=Exception("bal down")), \
         patch("modules.exchange.service.reader.fetch_positions", side_effect=Exception("pos down")):
        overview, warning = service.sync()

    assert overview.balances == []
    assert overview.positions == []
    assert overview.totalUsdValue == pytest.approx(0.0)
    assert warning is not None
    assert "balance fetch failed" in warning
    assert "position fetch failed" in warning


def test_get_overview_after_sync_failure_returns_stale_cache():
    """A successful sync populates the cache; a subsequent sync failure does NOT clear
    the snapshot — get_overview still returns the last successful snapshot."""
    raw_bal = [{"ccy": "ETH", "availBal": "5", "frozenBal": "0", "eqUsd": "15000"}]
    # First sync succeeds
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw_bal), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        service.sync()

    cached_snap = service._last_snapshot
    assert cached_snap is not None
    assert len(cached_snap.balances) == 1

    # Now get_overview should return the cached snap without calling reader again
    with patch("modules.exchange.service.reader.fetch_balances") as mock_bal:
        overview, warning = service.get_overview()
    mock_bal.assert_not_called()
    assert overview.balances[0].symbol == "ETH"
    assert warning is None


def test_balances_sorted_by_usd_value_descending():
    """Multiple balances are returned sorted by usdValue descending (highest USD first)."""
    raw = [
        {"ccy": "DOGE", "availBal": "10000", "frozenBal": "0", "eqUsd": "100.0"},
        {"ccy": "BTC",  "availBal": "1",     "frozenBal": "0", "eqUsd": "60000.0"},
        {"ccy": "ETH",  "availBal": "5",     "frozenBal": "0", "eqUsd": "15000.0"},
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, _ = service.sync()

    syms = [b.symbol for b in overview.balances]
    assert syms == ["BTC", "ETH", "DOGE"]


def test_sync_sets_synced_at_timestamp():
    """After a successful sync, syncedAt is set (not None)."""
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=[]), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, _ = service.sync()

    assert overview.syncedAt is not None
    assert "T" in overview.syncedAt  # ISO-8601 has a T separator


def test_reader_get_raises_on_okx_error_code():
    """_get() raises ValueError when OKX returns code != '0'."""
    from modules.exchange import reader

    error_body = {"code": "50001", "msg": "Invalid API key", "data": []}
    with patch.object(reader.settings, "okx_api_key", "key"), \
         patch.object(reader.settings, "okx_api_secret", "secret"), \
         patch.object(reader.settings, "okx_api_passphrase", "pass"), \
         respx.mock() as mock_router:
        mock_router.get("https://www.okx.com/api/v5/account/balance").mock(
            return_value=httpx.Response(200, json=error_body)
        )
        with pytest.raises(ValueError, match="OKX error 50001"):
            reader.fetch_balances()


def test_reader_get_raises_on_http_error():
    """_get() raises httpx.HTTPStatusError on a non-200 HTTP response."""
    from modules.exchange import reader

    with patch.object(reader.settings, "okx_api_key", "key"), \
         patch.object(reader.settings, "okx_api_secret", "secret"), \
         patch.object(reader.settings, "okx_api_passphrase", "pass"), \
         respx.mock() as mock_router:
        mock_router.get("https://www.okx.com/api/v5/account/balance").mock(
            return_value=httpx.Response(401, json={"msg": "Unauthorized"})
        )
        with pytest.raises(httpx.HTTPStatusError):
            reader.fetch_balances()


# =========================================================================== #
# DUST-FOLD (#17) — sub-$1 balances fold into one ·dust summary (DISPLAY-only)   #
# =========================================================================== #
# Mirrors finance's holdings dust-fold philosophy on the flat OkxBalance list. The dust
# predicate is usdValue-only (OkxBalance has no price); null-usdValue stays VISIBLE (unknown ≠
# small — the finance lock); strict < $1; total UNCHANGED (fold is display-only, value preserved).

from modules.exchange.schema import OkxBalance  # noqa: E402


def _bal(symbol, usd):
    """An OkxBalance with the given symbol + usdValue (qty fields irrelevant to the fold)."""
    return OkxBalance(symbol=symbol, available=0.0, frozen=0.0, total=0.0, usdValue=usd)


# --- (a) sub-$1 priced dust → folded into one ·dust row ---
def test_DUST_subdollar_balances_are_folded():
    """ETH 7e-7, DOGE rounds-to-0, LINK $0.50 (all < $1) → ONE ·dust summary (isDust, count=3,
    usdValue=Σ). The big USDT stays individual."""
    bals = [_bal("USDT", 9000.0), _bal("ETH", 0.0000007), _bal("DOGE", 0.0), _bal("LINK", 0.50)]
    folded = service._fold_dust_balances(bals)
    symbols = [b.symbol for b in folded]
    assert "USDT" in symbols and service.DUST_SYMBOL in symbols
    assert "ETH" not in symbols and "DOGE" not in symbols and "LINK" not in symbols
    dust = next(b for b in folded if b.isDust)
    assert dust.count == 3, f"·dust must fold all 3 sub-$1 balances, got count={dust.count}"
    assert dust.usdValue == pytest.approx(0.50, abs=1e-6)  # 7e-7 + 0 + 0.50, rounded
    assert dust.symbol == service.DUST_SYMBOL
    assert dust.available == 0.0 and dust.frozen == 0.0 and dust.total == 0.0
    assert dust.accAvgPx is None and dust.spotUpl is None


# --- (b) ≥$1 stays individual (not over-folding); exactly $1.00 is the strict boundary ---
def test_DUST_dollar_and_above_stay_individual():
    """A balance ≥ $1 is NOT dust — stays an individual row. Exactly $1.00 stays visible (strict
    `< threshold`), $0.99 folds (the boundary distinguishing)."""
    bals = [_bal("BTC", 1.00), _bal("SOL", 5.0), _bal("PEPE", 0.99)]
    folded = service._fold_dust_balances(bals)
    symbols = [b.symbol for b in folded]
    assert "BTC" in symbols, "exactly $1.00 must stay visible (strict <)"
    assert "SOL" in symbols
    assert "PEPE" not in symbols, "$0.99 (< $1) must fold"
    dust = next((b for b in folded if b.isDust), None)
    assert dust is not None and dust.count == 1 and dust.usdValue == pytest.approx(0.99)


# --- (c) null-usdValue stays VISIBLE (the distinguishing — unknown ≠ small) ---
def test_DUST_null_usdvalue_stays_visible():
    """A balance with usdValue=None is UNKNOWN, not small → NOT folded (the finance lock). A
    naive `usdValue < 1 or None` would WRONGLY fold it; assert it stays an individual row."""
    bals = [_bal("USDT", 9000.0), _bal("MYSTERY", None), _bal("ETH", 0.0000007)]
    folded = service._fold_dust_balances(bals)
    symbols = [b.symbol for b in folded]
    assert "MYSTERY" in symbols, "null-usdValue must stay VISIBLE (unknown ≠ small)"
    mystery = next(b for b in folded if b.symbol == "MYSTERY")
    assert mystery.isDust is False and mystery.usdValue is None
    # only the real dust (ETH) is folded, not MYSTERY
    dust = next(b for b in folded if b.isDust)
    assert dust.count == 1, "only ETH is dust; MYSTERY (unknown) is not folded"


def test_DUST_predicate_matches_lock():
    """_is_dust_balance: < $1 known → dust; exactly $1 / ≥$1 / None → not dust."""
    assert service._is_dust_balance(_bal("a", 0.5)) is True
    assert service._is_dust_balance(_bal("b", 0.0)) is True          # rounds-to-0 priced coin
    assert service._is_dust_balance(_bal("c", 1.00)) is False        # strict boundary
    assert service._is_dust_balance(_bal("d", 2.0)) is False
    assert service._is_dust_balance(_bal("e", None)) is False        # unknown ≠ small


def test_DUST_no_dust_no_summary_row():
    """0 dust balances → NO ·dust row is added (the list is unchanged)."""
    bals = [_bal("USDT", 9000.0), _bal("BTC", 30000.0)]
    folded = service._fold_dust_balances(bals)
    assert not any(b.isDust for b in folded)
    assert len(folded) == 2


# --- (d) total_usd UNCHANGED through the real sync() flow (DISPLAY-only) ---
def test_DUST_total_usd_unchanged_through_sync():
    """End-to-end: sync() with a real OKX-shaped payload containing sub-$1 dust folds the LIST but
    totalUsdValue is computed from the FULL set BEFORE the fold → Σ(folded incl ·dust) == total."""
    raw_balances = [
        {"ccy": "USDT", "availBal": "9000", "frozenBal": "0", "eqUsd": "9000.0"},
        {"ccy": "BTC", "availBal": "0.01", "frozenBal": "0", "eqUsd": "1.00"},     # exactly $1 → kept
        {"ccy": "ETH", "availBal": "0.0000004", "frozenBal": "0", "eqUsd": "0.0000007"},  # dust
        {"ccy": "LINK", "availBal": "0.001", "frozenBal": "0", "eqUsd": "0.50"},   # dust
    ]
    with patch.object(service.settings, "okx_api_key", "key"), \
         patch.object(service.settings, "okx_api_secret", "secret"), \
         patch.object(service.settings, "okx_api_passphrase", "pass"), \
         patch("modules.exchange.service.reader.fetch_balances", return_value=raw_balances), \
         patch("modules.exchange.service.reader.fetch_positions", return_value=[]):
        overview, _ = service.sync()

    # the ·dust row exists, dust coins are folded, big + exactly-$1 stay individual
    symbols = [b.symbol for b in overview.balances]
    assert service.DUST_SYMBOL in symbols
    assert "ETH" not in symbols and "LINK" not in symbols
    assert "USDT" in symbols and "BTC" in symbols
    # totalUsdValue is the FULL pre-fold sum (9000 + 1 + ~0 + 0.50)
    assert overview.totalUsdValue == pytest.approx(9001.5000007, abs=1e-4)
    # DISPLAY-only invariant: Σ(folded balances' usdValue) == totalUsdValue (to the cent)
    folded_sum = sum(b.usdValue or 0.0 for b in overview.balances)
    assert folded_sum == pytest.approx(overview.totalUsdValue, abs=0.01), \
        "Σ(folded incl ·dust) must equal the pre-fold total (display-only fold)"
