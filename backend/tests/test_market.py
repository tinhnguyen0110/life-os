"""tests/test_market.py — Sprint 3 T5: market module verification.

Sections:
  A. Schema shapes  — AssetQuote / AlertRule / AlertRuleInput / AlertTrigger /
                       PricePoint / MacroSignal field presence + types (FROZEN)
  B. Reader unit    — httpx mocked (NEVER real in CI), mock-class deterministic,
                       fail-open on feed-down/timeout/429, timeout present in call
  C. Service unit   — derive_change_pct math (from price_history + feed fallback),
                       eval_alerts hit/near/far + distancePct formula,
                       add_rule UPSERT (BTC/above × 2 → 1 rule, threshold=new),
                       delete_rule by id
  D. DB persistence — price_history row-exists after record_price (Sprint-13
                       lesson: query the DB, not just trust the return value)
  E. API endpoints  — GET /market envelope, GET /market/history/{symbol},
                       POST /market/alerts upsert, DELETE /market/alerts/{id},
                       feed-down → warning not 500
  F. Routine        — market-poll in /health after module mounts

httpx is NEVER really called — every CoinGecko call is intercepted via
unittest.mock.patch. Real network access in CI = instant test failure.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Section A — Schema shapes (FROZEN as of mtime 17:14)
# ---------------------------------------------------------------------------
pytest.importorskip(
    "modules.market.schema",
    reason="modules/market/schema not yet implemented",
)

from modules.market.schema import (  # noqa: E402
    AlertEvent,
    AlertRule,
    AlertRuleInput,
    AlertTrigger,
    AssetQuote,
    MacroSignal,
    PricePoint,
)


class TestSchemaShapes:
    """A — field presence + types on frozen shapes."""

    def test_asset_quote_fields(self):
        aq = AssetQuote(
            symbol="BTC", name="Bitcoin", assetClass="crypto",
            price=60818.0, changePct=None, currency="USD",
            ts="2026-06-06T10:00:00+00:00", source="coingecko",
        )
        assert aq.symbol == "BTC"
        assert aq.assetClass == "crypto"
        assert isinstance(aq.price, float)
        assert aq.changePct is None

    def test_asset_quote_change_pct_populated(self):
        aq = AssetQuote(symbol="BTC", name="Bitcoin", assetClass="crypto",
                        price=60818.0, changePct=-3.06, currency="USD",
                        ts="2026-06-06T10:00:00+00:00", source="coingecko")
        assert aq.changePct == pytest.approx(-3.06)

    def test_asset_quote_source_values(self):
        for src in ("coingecko", "mock", "last-known"):
            aq = AssetQuote(symbol="X", name="X", assetClass="etf",
                            price=100.0, currency="USD",
                            ts="2026-06-06T10:00:00+00:00", source=src)
            assert aq.source == src

    def test_alert_rule_has_id(self):
        """AlertRule requires server-assigned id field."""
        r = AlertRule(id="btc-above-1", symbol="BTC", op="above", threshold=70000.0)
        assert r.id == "btc-above-1"
        assert r.symbol == "BTC"
        assert r.op == "above"
        assert r.threshold == 70000.0
        assert r.enabled is True

    def test_alert_rule_op_literal(self):
        """op must be 'above' or 'below'."""
        with pytest.raises(Exception):
            AlertRule(id="x", symbol="BTC", op="sideways", threshold=70000.0)

    def test_alert_rule_threshold_positive(self):
        with pytest.raises(Exception):
            AlertRule(id="x", symbol="BTC", op="above", threshold=0.0)

    def test_alert_rule_input_no_id(self):
        """AlertRuleInput is the POST body — no id field (server assigns)."""
        body = AlertRuleInput(symbol="BTC", op="above", threshold=70000.0)
        assert body.symbol == "BTC"
        assert not hasattr(body, "id") or body.model_fields.get("id") is None

    def test_alert_trigger_has_distance_pct(self):
        """AlertTrigger uses distancePct (not distance)."""
        t = AlertTrigger(
            symbol="BTC", op="above", threshold=70000.0,
            price=68000.0, state="near", distancePct=2.94,
        )
        assert t.distancePct == pytest.approx(2.94)
        assert not hasattr(t, "distance") or "distance" not in t.model_fields

    def test_alert_trigger_states(self):
        for state in ("hit", "near", "far"):
            t = AlertTrigger(symbol="BTC", op="above", threshold=70000.0,
                             price=68000.0, state=state, distancePct=2.94)
            assert t.state == state

    def test_macro_signal_value_is_string(self):
        """MacroSignal.value is a str (display-ready, mixed units like '38' or '$72')."""
        m = MacroSignal(name="Fear & Greed", value="38", status="fear", note="extreme fear")
        assert isinstance(m.value, str), "MacroSignal.value must be str, not float"
        assert m.value == "38"

    def test_price_point_fields(self):
        pp = PricePoint(asset="BTC", price=60818.0, ts="2026-06-06T10:00:00+00:00")
        assert pp.asset == "BTC"
        assert pp.price == 60818.0


# ---------------------------------------------------------------------------
# Section B — Reader unit (httpx ALWAYS mocked)
# ---------------------------------------------------------------------------
pytest.importorskip(
    "modules.market.reader",
    reason="modules/market/reader not yet implemented",
)

from modules.market.reader import read_quote, read_quotes  # noqa: E402

CRYPTO_BTC = {"symbol": "BTC", "name": "Bitcoin",   "assetClass": "crypto", "cgId": "bitcoin"}
CRYPTO_ETH = {"symbol": "ETH", "name": "Ethereum",  "assetClass": "crypto", "cgId": "ethereum"}
MOCK_VOO   = {"symbol": "VOO", "name": "Vanguard",  "assetClass": "etf",    "mock": 512.0}
MOCK_VN    = {"symbol": "VNINDEX", "name": "VN-Index", "assetClass": "vn",  "mock": 1280.0}

FAKE_CG = {
    "bitcoin":  {"usd": 60818.0, "usd_24h_change": -3.14},
    "ethereum": {"usd": 3500.0,  "usd_24h_change": 1.2},
}


def _fake_resp(data: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = data
    r.raise_for_status = MagicMock()
    return r


class TestReader:
    """B — reader: httpx mocked, fail-open, deterministic mock, timeout."""

    def test_crypto_calls_httpx_not_real_network(self):
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)) as mg:
            quotes, warnings = read_quotes([CRYPTO_BTC, CRYPTO_ETH])
            assert mg.called, "reader must call httpx.get for crypto assets"
        btc = next(q for q in quotes if q.symbol == "BTC")
        assert btc.price == pytest.approx(60818.0)
        assert btc.source == "coingecko"

    def test_mock_class_no_network_call(self):
        with patch("modules.market.reader.httpx.get") as mg:
            quotes, _ = read_quotes([MOCK_VOO, MOCK_VN])
            assert not mg.called, "mock-class must NOT call httpx.get"
        voo = next(q for q in quotes if q.symbol == "VOO")
        assert voo.price > 0
        assert voo.source == "mock"

    def test_mock_class_deterministic(self):
        """Same symbol → same price on repeated calls (no randomness)."""
        with patch("modules.market.reader.httpx.get"):
            q1, _ = read_quotes([MOCK_VOO])
            q2, _ = read_quotes([MOCK_VOO])
        assert q1[0].price == q2[0].price

    def test_fail_open_no_raise_on_request_error(self):
        """CoinGecko network error → no raise, returns list + warnings."""
        import httpx as hx
        with patch("modules.market.reader.httpx.get",
                   side_effect=hx.RequestError("timeout", request=MagicMock())):
            quotes, warnings = read_quotes([CRYPTO_BTC])
        assert isinstance(quotes, list)
        assert len(warnings) > 0, "must emit warning when feed is down"

    def test_fail_open_no_raise_on_http_status_error(self):
        """CoinGecko 429/500 → no raise."""
        import httpx as hx
        resp = MagicMock()
        resp.raise_for_status.side_effect = hx.HTTPStatusError(
            "429", request=MagicMock(), response=MagicMock()
        )
        with patch("modules.market.reader.httpx.get", return_value=resp):
            quotes, warnings = read_quotes([CRYPTO_BTC])
        assert isinstance(quotes, list)

    def test_fail_open_returns_last_known_or_mock(self):
        """After CoinGecko failure, BTC quote source must be last-known or mock."""
        import httpx as hx
        with patch("modules.market.reader.httpx.get",
                   side_effect=hx.RequestError("timeout", request=MagicMock())):
            quotes, _ = read_quotes([CRYPTO_BTC])
        assert len(quotes) == 1
        assert quotes[0].symbol == "BTC"
        assert quotes[0].source in ("last-known", "mock")

    def test_fail_open_per_asset_btc_survives_bogus(self):
        """CoinGecko silently omits unknown id — BTC still comes through."""
        bogus = {"symbol": "BOGUS", "name": "Bogus", "assetClass": "crypto", "cgId": "bogus_xyz"}
        partial = {"bitcoin": {"usd": 60818.0, "usd_24h_change": -3.14}}
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(partial)):
            quotes, _ = read_quotes([CRYPTO_BTC, bogus])
        assert "BTC" in [q.symbol for q in quotes]

    def test_reader_has_timeout(self):
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)) as mg:
            read_quotes([CRYPTO_BTC])
        assert mg.called, "httpx.get must be called for crypto asset"
        # timeout can be positional or keyword — check all args
        call = mg.call_args
        has_timeout = (
            "timeout" in (call.kwargs or {})
            or any("timeout" in str(a) for a in (call.args or []))
        )
        assert has_timeout, "httpx.get must be called with timeout= to avoid hanging"

    def test_read_quote_convenience(self):
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            q = read_quote(CRYPTO_BTC)
        assert isinstance(q, AssetQuote)
        assert q.symbol == "BTC"


# ---------------------------------------------------------------------------
# Section C — Service unit
# ---------------------------------------------------------------------------
pytest.importorskip(
    "modules.market.service",
    reason="modules/market/service not yet implemented",
)

from modules.market.service import (  # noqa: E402
    add_rule,
    delete_rule,
    derive_change_pct,
    eval_alerts,
    list_rules,
)


def _isolated_service(tmp_path, monkeypatch):
    """Reset service state to a clean tmp_path data dir + fresh DB."""
    from core.config import settings
    from store import db

    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    db.init_db(str(tmp_path / "store" / "test.db"))


class TestServiceMath:
    """C — derive_change_pct, eval_alerts, add_rule upsert, delete_rule."""

    def test_change_pct_positive(self, tmp_path, monkeypatch):
        _isolated_service(tmp_path, monkeypatch)
        from core.config import settings
        from store import db
        from datetime import datetime, timedelta, timezone

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        db.record_price("BTC", 59000.0, old_ts)
        pct = derive_change_pct("BTC", 60818.0, feed_fallback=None)
        assert pct is not None and pct == pytest.approx(3.08, abs=0.1)
        db.close_db()

    def test_change_pct_negative(self, tmp_path, monkeypatch):
        _isolated_service(tmp_path, monkeypatch)
        from store import db
        from datetime import datetime, timedelta, timezone

        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        db.record_price("BTC", 62800.0, old_ts)
        pct = derive_change_pct("BTC", 60818.0, feed_fallback=None)
        assert pct is not None and pct < 0
        db.close_db()

    def test_change_pct_feed_fallback_when_no_history(self, tmp_path, monkeypatch):
        _isolated_service(tmp_path, monkeypatch)
        from store import db
        pct = derive_change_pct("BTC", 60818.0, feed_fallback=-3.14)
        assert pct == pytest.approx(-3.14, abs=0.01)
        db.close_db()

    def test_change_pct_none_when_no_history_no_fallback(self, tmp_path, monkeypatch):
        _isolated_service(tmp_path, monkeypatch)
        from store import db
        pct = derive_change_pct("BTC", 60818.0, feed_fallback=None)
        assert pct is None
        db.close_db()

    def test_change_pct_no_divide_by_zero(self, tmp_path, monkeypatch):
        _isolated_service(tmp_path, monkeypatch)
        from store import db
        from datetime import datetime, timedelta, timezone
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        db.record_price("BTC", 0.0, old_ts)
        result = derive_change_pct("BTC", 60818.0, feed_fallback=None)
        assert result is None or result == 0  # never raises ZeroDivisionError
        db.close_db()

    def test_eval_alerts_above_hit(self):
        quotes = [AssetQuote(symbol="BTC", name="BTC", assetClass="crypto",
                             price=71000.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        rules = [AlertRule(id="r1", symbol="BTC", op="above", threshold=70000.0)]
        triggers = eval_alerts(quotes, rules)
        assert len(triggers) == 1 and triggers[0].state == "hit"

    def test_eval_alerts_above_far(self):
        quotes = [AssetQuote(symbol="BTC", name="BTC", assetClass="crypto",
                             price=60000.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        rules = [AlertRule(id="r1", symbol="BTC", op="above", threshold=70000.0)]
        triggers = eval_alerts(quotes, rules)
        assert triggers[0].state == "far"

    def test_eval_alerts_near_within_5pct(self):
        """price=67000, threshold=70000 → |distancePct|=(3000/67000)*100≈4.5% → near."""
        quotes = [AssetQuote(symbol="BTC", name="BTC", assetClass="crypto",
                             price=67000.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        rules = [AlertRule(id="r1", symbol="BTC", op="above", threshold=70000.0)]
        triggers = eval_alerts(quotes, rules)
        assert triggers[0].state == "near"

    def test_eval_alerts_below_hit(self):
        quotes = [AssetQuote(symbol="BTC", name="BTC", assetClass="crypto",
                             price=58000.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        rules = [AlertRule(id="r1", symbol="BTC", op="below", threshold=60000.0)]
        triggers = eval_alerts(quotes, rules)
        assert triggers[0].state == "hit"

    def test_eval_alerts_distance_pct_formula(self):
        """distancePct = (threshold - price) / price * 100."""
        quotes = [AssetQuote(symbol="BTC", name="BTC", assetClass="crypto",
                             price=60000.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        rules = [AlertRule(id="r1", symbol="BTC", op="above", threshold=70000.0)]
        triggers = eval_alerts(quotes, rules)
        expected = (70000.0 - 60000.0) / 60000.0 * 100  # ≈16.67
        assert triggers[0].distancePct == pytest.approx(expected, abs=0.01)

    def test_eval_alerts_unknown_symbol_skipped(self):
        quotes = [AssetQuote(symbol="ETH", name="ETH", assetClass="crypto",
                             price=3500.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        rules = [AlertRule(id="r1", symbol="BTC", op="above", threshold=70000.0)]
        assert eval_alerts(quotes, rules) == []

    def test_eval_alerts_empty_rules(self):
        quotes = [AssetQuote(symbol="BTC", name="BTC", assetClass="crypto",
                             price=60000.0, changePct=None, currency="USD",
                             ts="2026-06-06T10:00:00+00:00", source="coingecko")]
        assert eval_alerts(quotes, []) == []

    # --- add_rule UPSERT ---
    def test_add_rule_upsert_same_symbol_op(self, tmp_path, monkeypatch):
        """POST BTC/above 4000, then BTC/above 4500 → list_rules returns EXACTLY 1 rule,
        threshold=4500. This is the key UX correctness test (no duplicates)."""
        _isolated_service(tmp_path, monkeypatch)
        from store import db

        r1 = add_rule("BTC", "above", 4000.0)
        r2 = add_rule("BTC", "above", 4500.0)  # upsert — same symbol+op

        rules = list_rules()
        btc_above = [r for r in rules if r.symbol == "BTC" and r.op == "above"]
        assert len(btc_above) == 1, \
            f"upsert must produce exactly 1 rule for BTC/above, got {len(btc_above)}"
        assert btc_above[0].threshold == 4500.0, \
            f"upsert must update threshold to 4500, got {btc_above[0].threshold}"
        # id must be preserved across upsert
        assert r2.id == r1.id, "upsert must keep the original rule id"
        db.close_db()

    def test_add_rule_different_ops_create_separate_rules(self, tmp_path, monkeypatch):
        """BTC/above and BTC/below are two distinct rules — upsert doesn't merge them."""
        _isolated_service(tmp_path, monkeypatch)
        from store import db

        add_rule("BTC", "above", 70000.0)
        add_rule("BTC", "below", 50000.0)
        rules = list_rules()
        btc_rules = [r for r in rules if r.symbol == "BTC"]
        assert len(btc_rules) == 2
        db.close_db()

    def test_delete_rule_by_id(self, tmp_path, monkeypatch):
        """delete_rule(id) returns True and rule is gone from list_rules."""
        _isolated_service(tmp_path, monkeypatch)
        from store import db

        r = add_rule("ETH", "above", 4000.0)
        removed = delete_rule(r.id)
        assert removed is True
        assert not any(x.id == r.id for x in list_rules())
        db.close_db()

    def test_delete_rule_unknown_id_returns_false(self, tmp_path, monkeypatch):
        """delete_rule with unknown id returns False, no crash."""
        _isolated_service(tmp_path, monkeypatch)
        from store import db
        result = delete_rule("nonexistent-id-xyz")
        assert result is False
        db.close_db()


# ---------------------------------------------------------------------------
# Section D — DB persistence (Sprint-13 lesson: query the row, trust nothing else)
# ---------------------------------------------------------------------------

class TestDBPersistence:
    """D — record_price row-exists after INSERT."""

    def test_record_price_row_exists(self, tmp_path, monkeypatch):
        from core.config import settings
        from store import db
        monkeypatch.setattr(settings, "db_path", tmp_path / "t.db")
        monkeypatch.setattr(db, "DB_PATH", None)
        db.close_db()
        db.init_db(str(tmp_path / "t.db"))

        row_id = db.record_price("BTC", 60818.0, "2026-06-06T10:00:00+00:00",
                                  currency="USD", source="coingecko")
        assert row_id > 0
        row = db.get_conn().execute(
            "SELECT asset, price FROM price_history WHERE id=?", (row_id,)
        ).fetchone()
        assert row is not None, "record_price must insert a real row"
        assert row[0] == "BTC"
        assert float(row[1]) == pytest.approx(60818.0)
        db.close_db()

    def test_record_price_multiple_assets(self, tmp_path, monkeypatch):
        from core.config import settings
        from store import db
        monkeypatch.setattr(settings, "db_path", tmp_path / "t2.db")
        monkeypatch.setattr(db, "DB_PATH", None)
        db.close_db()
        db.init_db(str(tmp_path / "t2.db"))

        db.record_price("BTC", 60818.0, "2026-06-06T10:00:00+00:00")
        db.record_price("ETH", 3500.0,  "2026-06-06T10:00:00+00:00")
        conn = db.get_conn()
        btc = conn.execute("SELECT price FROM price_history WHERE asset=?", ("BTC",)).fetchone()
        eth = conn.execute("SELECT price FROM price_history WHERE asset=?", ("ETH",)).fetchone()
        assert btc and float(btc[0]) == pytest.approx(60818.0)
        assert eth and float(eth[0]) == pytest.approx(3500.0)
        db.close_db()

    def test_latest_price_most_recent(self, tmp_path, monkeypatch):
        from core.config import settings
        from store import db
        monkeypatch.setattr(settings, "db_path", tmp_path / "t3.db")
        monkeypatch.setattr(db, "DB_PATH", None)
        db.close_db()
        db.init_db(str(tmp_path / "t3.db"))

        db.record_price("BTC", 59000.0, "2026-06-05T10:00:00+00:00")
        db.record_price("BTC", 60818.0, "2026-06-06T10:00:00+00:00")
        row = db.latest_price("BTC")
        assert row is not None
        assert float(row["price"]) == pytest.approx(60818.0), \
            "latest_price must return the most recent row"
        db.close_db()

    def test_latest_price_none_for_unknown(self, tmp_path, monkeypatch):
        from core.config import settings
        from store import db
        monkeypatch.setattr(settings, "db_path", tmp_path / "t4.db")
        monkeypatch.setattr(db, "DB_PATH", None)
        db.close_db()
        db.init_db(str(tmp_path / "t4.db"))
        assert db.latest_price("NONEXISTENT_ASSET_XYZ") is None
        db.close_db()


# ---------------------------------------------------------------------------
# Section E — API endpoints (TestClient)
# ---------------------------------------------------------------------------

try:
    from fastapi.testclient import TestClient  # noqa: F401
    _fastapi_ok = True
except ImportError:
    _fastapi_ok = False

_api = pytest.mark.skipif(not _fastapi_ok, reason="fastapi not available")


def _market_router_available() -> bool:
    try:
        import modules.market as m
        return hasattr(m, "MODULE") or hasattr(m.router if hasattr(m, "router") else object(), "MODULE")
    except ImportError:
        return False


def _make_client(tmp_path, monkeypatch):
    from core.config import settings
    from store import db
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "db_path", tmp_path / "store" / "test.db")
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    monkeypatch.setattr(db, "DB_PATH", None)
    db.close_db()
    import main as m
    importlib.reload(m)
    app = m.create_app()
    return TestClient(app)


def _check_router():
    try:
        from modules.market.router import MODULE  # noqa: F401
        return True
    except ImportError:
        return False


class TestMarketAPI:
    """E — router endpoints."""

    @_api
    def test_get_market_envelope(self, tmp_path, monkeypatch):
        if not _check_router():
            pytest.skip("market router not yet mounted")
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            r = c.get("/market")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "quotes"   in body["data"]
        assert "triggers" in body["data"]
        assert "macro"    in body["data"]

    @_api
    def test_get_market_quotes_fields(self, tmp_path, monkeypatch):
        if not _check_router():
            pytest.skip("market router not yet mounted")
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            quotes = c.get("/market").json()["data"]["quotes"]
        assert len(quotes) > 0
        for q in quotes:
            assert "symbol"     in q
            assert "price"      in q
            assert "changePct"  in q
            assert "assetClass" in q

    @_api
    def test_get_market_history_list(self, tmp_path, monkeypatch):
        """GET /market/history/BTC: 200 list when series exists; seed a price first."""
        if not _check_router():
            pytest.skip("market router not yet mounted")
        # Seed a price row so history returns data (empty DB → 404 by design)
        from store import db as db_mod
        from core.config import settings
        monkeypatch.setattr(db_mod, "DB_PATH", None)
        db_mod.close_db()
        db_mod.init_db(str(tmp_path / "store" / "test.db"))
        db_mod.record_price("BTC", 60818.0, "2026-06-06T10:00:00+00:00")
        db_mod.close_db()

        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            r = c.get("/market/history/BTC")
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        # data is {"points": [...]} (see router get_history)
        data = body["data"]
        points = data if isinstance(data, list) else data.get("points", data)
        assert isinstance(points, list)
        assert len(points) >= 1

    @_api
    def test_get_market_history_unknown_404(self, tmp_path, monkeypatch):
        if not _check_router():
            pytest.skip("market router not yet mounted")
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            r = c.get("/market/history/BOGUS_ASSET_XYZ_UNKNOWN")
        assert r.status_code == 404

    @_api
    def test_post_alert_upsert_one_rule(self, tmp_path, monkeypatch):
        """POST BTC/above 4000 then BTC/above 4500 → GET /market/alerts returns 1 rule, threshold=4500."""
        if not _check_router():
            pytest.skip("market router not yet mounted")
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            c.post("/market/alerts", json={"symbol": "BTC", "op": "above", "threshold": 4000.0})
            c.post("/market/alerts", json={"symbol": "BTC", "op": "above", "threshold": 4500.0})
            r = c.get("/market/alerts")
        assert r.status_code == 200
        rules = r.json()["data"]
        btc_above = [x for x in rules if x["symbol"] == "BTC" and x["op"] == "above"]
        assert len(btc_above) == 1, f"upsert must yield 1 BTC/above rule, got {len(btc_above)}"
        assert btc_above[0]["threshold"] == pytest.approx(4500.0)

    @_api
    def test_delete_alert_by_id(self, tmp_path, monkeypatch):
        """POST → get id → DELETE /{id} → 200; second DELETE same id → 404."""
        if not _check_router():
            pytest.skip("market router not yet mounted")
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            r1 = c.post("/market/alerts", json={"symbol": "ETH", "op": "above", "threshold": 4000.0})
        rule_id = r1.json()["data"]["id"]
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            r_del = c.delete(f"/market/alerts/{rule_id}")
        assert r_del.status_code == 200
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            r_del2 = c.delete(f"/market/alerts/{rule_id}")
        assert r_del2.status_code == 404

    @_api
    def test_feed_down_200_with_warning(self, tmp_path, monkeypatch):
        """CoinGecko down → 200 + warning, not 500."""
        if not _check_router():
            pytest.skip("market router not yet mounted")
        import httpx as hx
        with patch("modules.market.reader.httpx.get",
                   side_effect=hx.RequestError("timeout", request=MagicMock())):
            c = _make_client(tmp_path, monkeypatch)
            r = c.get("/market")
        assert r.status_code != 500
        body = r.json()
        assert body["success"] is True
        assert body.get("warning") is not None


# ---------------------------------------------------------------------------
# Section F — Routine discovery
# ---------------------------------------------------------------------------

class TestRoutineDiscovery:
    """F — market-poll in /health after module mounts."""

    @_api
    def test_market_poll_in_health(self, tmp_path, monkeypatch):
        if not _check_router():
            pytest.skip("market router not yet mounted")
        with patch("modules.market.reader.httpx.get", return_value=_fake_resp(FAKE_CG)):
            c = _make_client(tmp_path, monkeypatch)
            r = c.get("/health")
        body = r.json()
        assert "market" in body["data"]["modules"]
        assert "market-poll" in body["data"]["routines"]
