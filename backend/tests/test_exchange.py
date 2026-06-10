"""tests/test_exchange.py — exchange module unit tests (mocked httpx)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.exchange import service
from modules.exchange.schema import ExchangeOverview


@pytest.fixture(autouse=True)
def reset_snapshot():
    """Reset in-memory cache between tests."""
    service._last_snapshot = None
    yield
    service._last_snapshot = None


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
