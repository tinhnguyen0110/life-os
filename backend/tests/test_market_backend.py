"""tests/test_market_backend.py — backend's own market schema/reader/service tests.

(Separate from tester's T5 scaffold `test_market.py`.) CoinGecko HTTP is MOCKED
(respx) — NEVER hits the real API. Fail-open proven by forcing feed failures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from core.config import settings
from modules.market import reader, service
from modules.market.schema import AlertRule, AssetQuote, MacroSignal

CG_URL = "https://api.coingecko.com/api/v3/simple/price"

CRYPTO_ASSETS = [
    {"symbol": "BTC", "name": "Bitcoin", "assetClass": "crypto", "cgId": "bitcoin"},
    {"symbol": "ETH", "name": "Ethereum", "assetClass": "crypto", "cgId": "ethereum"},
]
ETF_ASSET = {"symbol": "FUEVFVND", "name": "ETF VFVND", "assetClass": "etf", "mock": 24.8}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# reader — happy path (mocked CoinGecko)                                        #
# --------------------------------------------------------------------------- #
@respx.mock
def test_read_quotes_crypto_from_coingecko():
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 60818.0, "usd_24h_change": -3.14},
        "ethereum": {"usd": 1563.8, "usd_24h_change": -6.9},
    }))
    quotes, warnings = reader.read_quotes(CRYPTO_ASSETS)
    by = {q.symbol: q for q in quotes}
    assert by["BTC"].price == 60818.0 and by["BTC"].source == "coingecko"
    assert by["ETH"].price == 1563.8
    assert warnings == []
    assert getattr(by["BTC"], "_feed_change_pct") == -3.14


@respx.mock
def test_one_batched_call_for_all_crypto():
    route = respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 1.0, "usd_24h_change": 0.0},
        "ethereum": {"usd": 2.0, "usd_24h_change": 0.0},
    }))
    reader.read_quotes(CRYPTO_ASSETS)
    assert route.call_count == 1, "must batch all crypto into ONE CoinGecko call"
    assert "bitcoin" in route.calls[0].request.url.params["ids"]
    assert "ethereum" in route.calls[0].request.url.params["ids"]


def test_etf_is_deterministic_mock():
    q1 = reader.read_quote(ETF_ASSET)
    q2 = reader.read_quote(ETF_ASSET)
    assert q1.source == "mock" and q1.assetClass == "etf"
    assert q1.price == q2.price, "mock must be deterministic (stable across calls)"
    assert q1.price > 0
    # seeded by the asset's `mock` base (24.8) → within ±0.5%
    assert abs(q1.price - 24.8) / 24.8 <= 0.01


# --------------------------------------------------------------------------- #
# reader — FAIL-OPEN (critical; first network call of the build)                #
# --------------------------------------------------------------------------- #
@respx.mock
def test_fail_open_on_timeout_uses_last_known(isolated_paths):
    from store import db
    db.record_price("BTC", 59000.0, _now_iso(), source="seed")
    respx.get(CG_URL).mock(side_effect=httpx.TimeoutException("boom"))
    quotes, warnings = reader.read_quotes([CRYPTO_ASSETS[0]])
    assert quotes[0].price == 59000.0
    assert quotes[0].source == "last-known"
    assert any("CoinGecko unavailable" in w for w in warnings)


@respx.mock
def test_fail_open_on_429_ratelimit(isolated_paths):
    respx.get(CG_URL).mock(return_value=httpx.Response(429, json={"error": "rate limited"}))
    quotes, warnings = reader.read_quotes([CRYPTO_ASSETS[0]])
    assert quotes[0].source in ("last-known", "mock")
    assert warnings


@respx.mock
def test_fail_open_on_non_200(isolated_paths):
    respx.get(CG_URL).mock(return_value=httpx.Response(500))
    quotes, warnings = reader.read_quotes([CRYPTO_ASSETS[0]])
    assert quotes
    assert warnings


@respx.mock
def test_fail_open_on_malformed_body(isolated_paths):
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json=["not", "a", "dict"]))
    quotes, warnings = reader.read_quotes([CRYPTO_ASSETS[0]])
    assert quotes and warnings


def test_crypto_missing_cgid_skipped_with_warning():
    bad = {"symbol": "DOGE", "name": "Dogecoin", "assetClass": "crypto"}  # no cgId
    quotes, warnings = reader.read_quotes([bad])
    assert quotes == []
    assert any("missing cgId" in w for w in warnings)


# --------------------------------------------------------------------------- #
# service — changePct derivation                                                #
# --------------------------------------------------------------------------- #
def test_change_pct_from_price_history(isolated_paths):
    from store import db
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    db.record_price("BTC", 50000.0, old_ts, source="seed")
    pct = service.derive_change_pct("BTC", 55000.0, feed_fallback=-99.0)
    assert pct == 10.0, "must use our series, NOT the feed's -99 fallback"


def test_change_pct_falls_back_to_feed_when_series_short(isolated_paths):
    assert service.derive_change_pct("ETH", 1500.0, feed_fallback=-6.9) == -6.9


def test_change_pct_none_when_no_series_no_feed(isolated_paths):
    assert service.derive_change_pct("XRP", 1.0, feed_fallback=None) is None


def test_change_pct_never_divides_by_zero(isolated_paths):
    from store import db
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    db.record_price("ZERO", 0.0, old_ts, source="seed")
    assert service.derive_change_pct("ZERO", 10.0, feed_fallback=None) is None


# --------------------------------------------------------------------------- #
# service — alert eval (hit / near / far), distancePct in PERCENT               #
# --------------------------------------------------------------------------- #
def _rule(symbol, op, threshold, enabled=True):
    return AlertRule(id=f"{symbol.lower()}-1", symbol=symbol, op=op, threshold=threshold, enabled=enabled)


def _quote(symbol, price):
    return AssetQuote(symbol=symbol, name=symbol, assetClass="crypto",
                      price=price, currency="USD", ts=_now_iso(), source="mock")


def test_alert_above_hit():
    t = service.eval_alerts([_quote("BTC", 61000)], [_rule("BTC", "above", 60000)])
    assert t[0].state == "hit"


def test_alert_below_hit():
    t = service.eval_alerts([_quote("BTC", 59000)], [_rule("BTC", "below", 60000)])
    assert t[0].state == "hit"


def test_alert_near_within_5pct():
    # price 58000 vs thr 60000 above → distancePct = (60000-58000)/58000*100 ≈ 3.4% ≤ 5 → near
    t = service.eval_alerts([_quote("BTC", 58000)], [_rule("BTC", "above", 60000)])
    assert t[0].state == "near"


def test_alert_far_beyond_5pct():
    t = service.eval_alerts([_quote("BTC", 50000)], [_rule("BTC", "above", 60000)])
    assert t[0].state == "far"


def test_alert_distance_pct_formula():
    t = service.eval_alerts([_quote("BTC", 50000)], [_rule("BTC", "above", 60000)])
    assert t[0].distancePct == round((60000 - 50000) / 50000 * 100, 2)  # = 20.0


def test_alert_skips_symbol_without_quote():
    t = service.eval_alerts([_quote("BTC", 100)], [_rule("ETH", "above", 1)])
    assert t == []


def test_alert_skips_disabled_rule():
    t = service.eval_alerts([_quote("BTC", 61000)], [_rule("BTC", "above", 60000, enabled=False)])
    assert t == []


# --------------------------------------------------------------------------- #
# service — rule persistence (md_store), id-based                               #
# --------------------------------------------------------------------------- #
def test_add_list_delete_rules(isolated_paths):
    assert service.list_rules() == []
    r1 = service.add_rule("BTC", "above", 70000)
    r2 = service.add_rule("ETH", "below", 1000)
    assert r1.id and r2.id and r1.id != r2.id
    assert len(service.list_rules()) == 2
    # delete by id
    assert service.delete_rule(r1.id) is True
    assert all(r.id != r1.id for r in service.list_rules())
    assert service.delete_rule("nonexistent-9") is False


def test_add_rule_upserts_by_symbol_op(isolated_paths):
    """Re-setting the same (symbol, op) REPLACES — one threshold per symbol+op,
    NOT a duplicate. Regression for the append-not-upsert bug."""
    first = service.add_rule("ETH", "above", 4000)
    second = service.add_rule("ETH", "above", 4500)  # same symbol+op, new threshold
    rules = [r for r in service.list_rules() if r.symbol == "ETH" and r.op == "above"]
    assert len(rules) == 1, f"upsert must not duplicate (symbol,op), got {rules}"
    assert rules[0].threshold == 4500.0
    assert rules[0].id == first.id == second.id, "id preserved across upsert"
    # a DIFFERENT op for the same symbol is a separate rule (not replaced)
    service.add_rule("ETH", "below", 1000)
    assert len(service.list_rules()) == 2


def test_malformed_alerts_md_ignored(isolated_paths):
    from store import md_store
    md_store.write_file(service.ALERTS_MD, "---\nrules: : : bad yaml\n---\n", "seed bad")
    assert service.list_rules() == []


# --------------------------------------------------------------------------- #
# service — macro (string values) + alert history + history endpoint            #
# --------------------------------------------------------------------------- #
def test_macro_is_stub_list_with_string_values():
    macro = service.macro_signals()
    assert all(isinstance(m, MacroSignal) for m in macro)
    assert all(isinstance(m.value, str) for m in macro), "MacroSignal.value is a string"
    names = {m.name for m in macro}
    assert "Fear & Greed" in names


def test_alert_history_from_run_log(isolated_paths):
    import json
    from store import db
    db.record_run(service.MARKET_POLL_ID, "warn", _now_iso(),
                  detail=json.dumps({"kind": "alert", "symbol": "BTC", "op": "above",
                                     "threshold": 60000, "price": 61000}))
    db.record_run(service.MARKET_POLL_ID, "ok", _now_iso(), detail="poll summary not-json")
    events = service.alert_history()
    assert len(events) == 1 and events[0].symbol == "BTC" and events[0].price == 61000


def test_history_windowed_oldest_to_newest(isolated_paths):
    from store import db
    base = datetime.now(timezone.utc)
    db.record_price("BTC", 1.0, (base - timedelta(hours=2)).isoformat(), source="s")
    db.record_price("BTC", 2.0, (base - timedelta(hours=1)).isoformat(), source="s")
    db.record_price("BTC", 0.5, (base - timedelta(hours=100)).isoformat(), source="s")  # outside 24h
    pts = service.history("BTC", hours=24)
    assert [p.price for p in pts] == [1.0, 2.0]  # ascending, 100h-old excluded


@respx.mock
def test_get_market_composite_shape(isolated_paths, monkeypatch):
    monkeypatch.setattr(settings, "market_assets", CRYPTO_ASSETS + [ETF_ASSET])
    respx.get(CG_URL).mock(return_value=httpx.Response(200, json={
        "bitcoin": {"usd": 60000.0, "usd_24h_change": 1.0},
        "ethereum": {"usd": 1500.0, "usd_24h_change": 2.0},
    }))
    data, warnings = service.get_market()
    assert set(data) == {"quotes", "triggers", "macro", "alertHistory"}
    assert len(data["quotes"]) == 3  # BTC, ETH, FUEVFVND
    assert isinstance(data["triggers"], list) and isinstance(data["macro"], list)
