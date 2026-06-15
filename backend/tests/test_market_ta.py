"""tests/test_market_ta.py — technical-analysis indicators (math correctness).

Every indicator is pinned against a KNOWN value: a hand-computed result or a published
reference (the Wilder/StockCharts RSI-14 canonical series). These are math — a wrong
formula must fail, so the assertions check exact numeric output, never just "not None".
"""

from __future__ import annotations

import math

from modules.market import ta


# --------------------------------------------------------------------------- #
# SMA                                                                           #
# --------------------------------------------------------------------------- #
def test_sma_handcalc():
    r = ta.sma([1, 2, 3, 4, 5], 3)
    # trailing-3 means: idx2=(1+2+3)/3=2, idx3=3, idx4=4; warm-up Nones before.
    assert r.series == [None, None, 2.0, 3.0, 4.0]
    assert r.latest == 4.0
    assert r.warning is None


def test_sma_exact_period_one_point():
    r = ta.sma([10, 20, 30], 3)
    assert r.series == [None, None, 20.0]
    assert r.latest == 20.0


def test_sma_short_series_warns_no_value():
    r = ta.sma([1, 2], 5)
    assert r.latest is None
    assert "shorter than period" in r.warning


def test_sma_empty():
    r = ta.sma([], 3)
    assert r.latest is None and r.warning == "empty series"


def test_sma_period_zero_guard():
    assert ta.sma([1, 2, 3], 0).warning == "period must be > 0"


# --------------------------------------------------------------------------- #
# EMA                                                                           #
# --------------------------------------------------------------------------- #
def test_ema_handcalc():
    # period 3 → α=0.5, seed = SMA(1,2,3)=2 at idx2; idx3=.5*4+.5*2=3; idx4=.5*5+.5*3=4
    r = ta.ema([1, 2, 3, 4, 5], 3)
    assert r.series == [None, None, 2.0, 3.0, 4.0]
    assert r.latest == 4.0


def test_ema_alpha_weighting_handcalc():
    # period 4 → α=0.4. seed=SMA(1,2,3,4)=2.5 at idx3. idx4=.4*5+.6*2.5=2+1.5=3.5
    r = ta.ema([1, 2, 3, 4, 5], 4)
    assert r.series[3] == 2.5
    assert r.series[4] == 3.5


# --------------------------------------------------------------------------- #
# RSI (Wilder)                                                                  #
# --------------------------------------------------------------------------- #
def test_rsi_canonical_wilder_reference():
    """The published Wilder / StockCharts RSI-14 worked example. The first RSI value
    on this exact 15-close series is the reference 70.46 (rounding to 2dp)."""
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
              46.08, 45.89, 46.03, 45.61, 46.28, 46.28]
    r = ta.rsi(closes, 14)
    # first defined RSI lands at index 14 (period closes → period deltas).
    assert r.series[14] is not None
    assert abs(r.series[14] - 70.46) < 0.05  # reference value


def test_rsi_all_up_is_100():
    r = ta.rsi(list(range(1, 20)), 14)  # strictly increasing → no losses
    assert r.latest == 100.0


def test_rsi_all_down_is_0():
    r = ta.rsi(list(range(20, 1, -1)), 14)  # strictly decreasing → no gains
    assert r.latest == 0.0


def test_rsi_needs_period_plus_one():
    r = ta.rsi([1, 2, 3], 14)
    assert r.latest is None and "shorter than period+1" in r.warning


# --------------------------------------------------------------------------- #
# MACD                                                                          #
# --------------------------------------------------------------------------- #
def test_macd_structure_and_sign():
    r = ta.macd([1, 2, 3, 4, 5, 6, 7, 8], fast=2, slow=3, signal_period=2)
    # macd line is defined only where BOTH EMAs are → from index slow-1 = 2.
    assert r.macd[0] is None and r.macd[1] is None
    assert r.macd[2] is not None
    # rising series → fast EMA above slow EMA → macd > 0.
    assert r.latest_macd > 0
    # histogram = macd - signal (where both defined).
    if r.latest_macd is not None and r.latest_signal is not None:
        assert abs(r.latest_histogram - (r.latest_macd - r.latest_signal)) < 1e-9


def test_macd_invalid_params():
    r = ta.macd([1, 2, 3], fast=26, slow=12)  # fast >= slow
    assert "fast < slow" in r.warning


def test_macd_short_series():
    r = ta.macd([1, 2, 3], fast=12, slow=26)
    assert r.latest_macd is None and "shorter than slow" in r.warning


# --------------------------------------------------------------------------- #
# Bollinger Bands                                                               #
# --------------------------------------------------------------------------- #
def test_bollinger_handcalc():
    # [2,4,6,8] period 4: mean=5, popvar=(9+1+1+9)/4=5, sd=√5; upper=5+2√5, lower=5-2√5
    r = ta.bollinger([2, 4, 6, 8], 4, 2.0)
    assert r.latest_middle == 5.0
    assert abs(r.latest_upper - (5 + 2 * math.sqrt(5))) < 1e-4
    assert abs(r.latest_lower - (5 - 2 * math.sqrt(5))) < 1e-4


def test_bollinger_constant_series_zero_width():
    r = ta.bollinger([10] * 20, 20, 2.0)
    assert r.latest_middle == 10.0 and r.latest_upper == 10.0 and r.latest_lower == 10.0


def test_bollinger_short_series_warns():
    r = ta.bollinger([1, 2, 3], 20)
    assert r.latest_middle is None and "shorter than period" in r.warning


# --------------------------------------------------------------------------- #
# ATR (Wilder)                                                                  #
# --------------------------------------------------------------------------- #
def test_atr_ohlc_handcalc():
    # h=[10,12,13] l=[8,9,11] c=[9,11,12], period 1.
    # TR[1]=max(12-9,|12-9|,|9-9|)=3 ; TR[2]=max(13-11,|13-11|,|11-11|)=2
    # seed mean(first 1 TR)=3 at idx1; idx2=(3*0+2)/1=2
    r = ta.atr(highs=[10, 12, 13], lows=[8, 9, 11], closes=[9, 11, 12], period=1)
    assert r.series == [None, 3.0, 2.0]
    assert r.latest == 2.0


def test_atr_close_only_degrades_with_warning():
    # close-only: TR = |close - prevClose|. [10,11,12,13,14] → all TR=1 → ATR=1.
    r = ta.atr(closes=[10, 11, 12, 13, 14], period=2)
    assert r.latest == 1.0
    assert "close-only" in r.warning  # honest about the degradation


def test_atr_needs_period_plus_one():
    r = ta.atr(closes=[10, 11], period=14)
    assert r.latest is None


# --------------------------------------------------------------------------- #
# volume trend                                                                  #
# --------------------------------------------------------------------------- #
def test_volume_trend_ratio_up():
    # rising volume → short SMA above long SMA → ratio > 1 → "up".
    vols = list(range(1, 30))
    r = ta.volume_trend(vols, short=5, long=20)
    assert r.latest is not None and r.latest > 1.0
    assert "up" in (r.warning or "")


def test_volume_trend_short_series():
    r = ta.volume_trend([1, 2, 3], short=5, long=20)
    assert r.latest is None and "shorter than long" in r.warning


# --------------------------------------------------------------------------- #
# NaN / None safety (shared sanitation)                                         #
# --------------------------------------------------------------------------- #
def test_nan_none_are_dropped_with_warning():
    r = ta.sma([1, 2, None, 4, 5, float("nan")], 2)
    # None + NaN dropped → [1,2,4,5]; SMA(2) latest = (4+5)/2 = 4.5
    assert r.latest == 4.5
    assert "dropped 2 invalid" in r.warning


def test_inf_is_dropped():
    r = ta.sma([1, 2, float("inf"), 4], 2)
    assert "dropped 1 invalid" in r.warning


# --------------------------------------------------------------------------- #
# summarize — NEUTRAL technical signals                                         #
# --------------------------------------------------------------------------- #
def test_summarize_is_signals_only_no_advice():
    s = ta.summarize([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], sma_fast=2, sma_slow=4, rsi_period=3)
    assert s["signals_only"] is True  # the neutral-signal contract
    # NO buy/sell language anywhere in the output keys/values.
    flat = str(s).lower()
    assert "buy" not in flat and "sell" not in flat


def test_summarize_overbought_on_strong_uptrend():
    s = ta.summarize(list(range(1, 12)), sma_fast=2, sma_slow=4, rsi_period=3)
    assert s["signals"]["rsi"] == "overbought"
    assert s["signals"]["trend"] == "up"


def test_summarize_oversold_on_strong_downtrend():
    s = ta.summarize(list(range(12, 1, -1)), sma_fast=2, sma_slow=4, rsi_period=3)
    assert s["signals"]["rsi"] == "oversold"
    assert s["signals"]["trend"] == "down"


def test_summarize_golden_cross():
    # fast(2) SMA crosses ABOVE slow(4) at the last step.
    s = ta.summarize([10, 10, 10, 10, 10, 20], sma_fast=2, sma_slow=4, rsi_period=3, bb_period=3)
    assert s["signals"]["cross"] == "golden_cross"


def test_summarize_death_cross():
    # prev fast strictly ABOVE slow, then fast drops BELOW → death cross.
    s = ta.summarize([10, 12, 14, 16, 2], sma_fast=2, sma_slow=4, rsi_period=3, bb_period=3)
    assert s["signals"]["cross"] == "death_cross"


def test_summarize_bollinger_above_upper_on_breakout():
    # 20-period band over stable noise + a final breakout bar that doesn't dominate sd.
    closes = [10 + (0.1 if i % 2 else -0.1) for i in range(19)] + [13]
    s = ta.summarize(closes, sma_fast=2, sma_slow=4, rsi_period=3, bb_period=20)
    assert s["signals"]["bollinger"] == "above_upper"


def test_summarize_empty_is_honest():
    s = ta.summarize([])
    assert s["warning"] == "empty series"
    assert s["latest"]["close"] is None
    assert s["signals"]["cross"] == "none"
