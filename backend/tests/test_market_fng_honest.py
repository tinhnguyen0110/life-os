"""tests/test_market_fng_honest.py — FNG-HONEST (#44+#54): market F&G reads the SINGLE macro store.

The honest-mirror breach this fixes: market_overview showed a hardcoded "38" while decision/guardian/
life_brief cite the REAL macro store (~live). Now market.macro_signals() reads macro.store.latest(
"fear_greed"/"btc_dominance") — the SAME source — so they can't contradict.

THE distinguishing (a hardcoded/collapsed impl FAILS these): seed a known store value → market F&G
EQUALS it (value + source), AND a None store → honest "n/a" (NOT a fabricated number), AND source
reflects truth (live vs mock).
"""

from __future__ import annotations

import pytest

from modules.macro import store as macro_store
from modules.market import service as mkt


@pytest.fixture
def macro_db(isolated_paths):
    macro_store.init_macro_tables()
    return isolated_paths


def _signal(signals, name):
    return next(s for s in signals if s.name == name)


# --------------------------------------------------------------------------- #
# F&G reads the real store (single source) — the EQUAL distinguishing          #
# --------------------------------------------------------------------------- #
def test_fng_reads_store_value_and_source(macro_db):
    """Seed fear_greed=23 source=live → market F&G value=="23", source=="live", asOf==the ts,
    status=="fear" (23 ≤ 44; extreme-fear folds into "fear" — the collapsed enum). A hardcoded
    "38" impl FAILS the value assert (the distinguishing: store says 23, not 38)."""
    macro_store.record_point("fear_greed", 23.0, "2026-06-21T00:00:00+00:00", source="live")
    fng = _signal(mkt.macro_signals(), "Fear & Greed")
    assert fng.value == "23"
    assert fng.source == "live"
    assert fng.asOf == "2026-06-21T00:00:00+00:00"
    assert fng.status == "fear"  # 23 → fear band (extreme-fear collapsed into fear)


def test_fng_equals_macro_store_latest(macro_db):
    """THE single-source distinguishing: market F&G value == the macro store's latest fear_greed
    (EQUAL — not a coincidentally-similar hardcode). Cross-surface byte-agreement."""
    macro_store.record_point("fear_greed", 61.0, "2026-06-21T01:00:00+00:00", source="live")
    fng = _signal(mkt.macro_signals(), "Fear & Greed")
    store_row = macro_store.latest("fear_greed")
    assert fng.value == str(int(store_row["value"]))  # market shows EXACTLY the store value
    assert fng.source == store_row["source"] and fng.asOf == store_row["ts"]
    assert fng.status == "greed"  # 61 → greed band


def test_btc_dominance_reads_store(macro_db):
    macro_store.record_point("btc_dominance", 54.3, "2026-06-21T02:00:00+00:00", source="live")
    btc = _signal(mkt.macro_signals(), "BTC Dominance")
    assert btc.value == "54%" and btc.source == "live"  # f'{54.3:.0f}%'
    assert btc.asOf == "2026-06-21T02:00:00+00:00"


# --------------------------------------------------------------------------- #
# honest-mirror — a None store → "n/a", NOT a fabricated number                  #
# --------------------------------------------------------------------------- #
def test_fng_none_store_is_honest_na_not_a_number(macro_db):
    """No fear_greed point in the store → value=="n/a", source=="mock", asOf is None — NEVER a
    fabricated number (the DXY-HONEST precedent). The old hardcode "38" was exactly this lie."""
    fng = _signal(mkt.macro_signals(), "Fear & Greed")  # nothing seeded
    assert fng.value == "n/a" and fng.status == "n/a" and fng.source == "mock" and fng.asOf is None


def test_btc_dominance_none_store_is_honest_na(macro_db):
    btc = _signal(mkt.macro_signals(), "BTC Dominance")
    assert btc.value == "n/a" and btc.source == "mock" and btc.asOf is None


# --------------------------------------------------------------------------- #
# Brent — no feed → mock value, honestly source-marked                           #
# --------------------------------------------------------------------------- #
def test_brent_is_mock_marked(macro_db):
    brent = _signal(mkt.macro_signals(), "Brent Oil")
    assert brent.source == "mock"  # honest: no free feed → mock-marked, not pretend-live


# --------------------------------------------------------------------------- #
# the F&G band cut-offs — COLLAPSED to {fear,neutral,greed} (decide-and-log)     #
# extreme-fear+fear→fear · neutral · greed+extreme-greed→greed (≤44 / 45-55 / ≥56)#
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value,band", [
    (0, "fear"), (24, "fear"),           # extreme-fear region folds into "fear"
    (25, "fear"), (44, "fear"),
    (45, "neutral"), (55, "neutral"),
    (56, "greed"), (75, "greed"),
    (76, "greed"), (100, "greed"),       # extreme-greed region folds into "greed"
], ids=lambda x: str(x))
def test_fng_status_bands(value, band):
    assert mkt._fng_status(value) == band


def test_fng_status_only_three_values():
    """The collapsed enum: _fng_status NEVER returns 'extreme ...' (status ∈ {fear,neutral,greed}) —
    keeps the existing MacroSignal.status enum (no consumer breaks)."""
    seen = {mkt._fng_status(v) for v in range(0, 101)}
    assert seen == {"fear", "neutral", "greed"}


# --------------------------------------------------------------------------- #
# source reflects truth — market mirrors the store's REAL source verbatim        #
# --------------------------------------------------------------------------- #
def test_source_reflects_store_truth(macro_db):
    """market mirrors the store's source VERBATIM — never upgrades/fakes it. NB: the macro store NEVER
    persists a mock point (DXY-REAL never-persist-mock — record_point early-returns on source='mock'),
    so a stored point is ALWAYS real-sourced; market surfaces that exact source (here 'alternative.me',
    the real F&G feed). The only way market shows source='mock' is the EMPTY-store n/a case (tested
    separately) — it can't show a mock NUMBER, which is the whole honest-mirror point."""
    macro_store.record_point("fear_greed", 40.0, "2026-06-21T03:00:00+00:00", source="alternative.me")
    fng = _signal(mkt.macro_signals(), "Fear & Greed")
    assert fng.value == "40" and fng.source == "alternative.me"  # mirrors the REAL source verbatim
    # and a mock point is never even in the store to surface (the never-persist-mock invariant)
    macro_store.record_point("fear_greed", 99.0, "2026-06-21T04:00:00+00:00", source="mock")
    fng2 = _signal(mkt.macro_signals(), "Fear & Greed")
    assert fng2.value == "40", "a mock point is NOT persisted → market still shows the last REAL point"
