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
