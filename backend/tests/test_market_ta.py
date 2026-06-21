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


def test_rsi_flat_series_is_50_not_100():
    """RSI-FLAT-HONEST (#62) — THE distinguishing: a FLAT series (no movement → avg_gain==0 AND
    avg_loss==0) → RSI 50.0 NEUTRAL, NOT 100. The old bug folded flat into the avg_loss==0→100
    branch → fake "extreme overbought" on a series with ZERO momentum (honest-mirror breach). An
    impl that returns 100 (or anything ≠50) for a flat series FAILS this. No flat-series RSI test
    existed before — that gap hid the bug."""
    r = ta.rsi([100.0] * 20, 14)
    assert r.latest == 50.0, "flat series → neutral 50, not fake overbought 100"
    # every point in the seeded+smoothed series is the flat-neutral 50 (not just the latest)
    assert all(v == 50.0 for v in r.series if v is not None)


def test_rsi_all_up_still_100_after_flat_fix():
    """Regression: the flat fix does NOT touch the all-gains path (avg_loss==0, avg_gain>0 → 100)."""
    assert ta.rsi(list(range(1, 20)), 14).latest == 100.0


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


def test_summarize_flat_series_rsi_is_neutral_not_overbought():
    """RSI-FLAT-HONEST (#62) — the CONSUMER-FACING end-to-end proof: summarize() on a FLAT series →
    rsi signal "neutral", NOT "overbought". This is the breach the fix closes: pre-fix, flat/mock
    data flowed RSI 100 → summarize "overbought" → life_brief surfaced a fake overbought signal. A
    flat series has zero momentum → neutral is the honest read."""
    s = ta.summarize([100.0] * 12, sma_fast=2, sma_slow=4, rsi_period=3)
    assert s["signals"]["rsi"] == "neutral", "flat series → neutral RSI signal, not fake overbought"


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


# --------------------------------------------------------------------------- #
# indicator-alert eval (_eval_one_indicator) — the TA-condition rule engine     #
# --------------------------------------------------------------------------- #
from modules.market import service as _svc  # noqa: E402
from modules.market.schema import IndicatorAlertRule  # noqa: E402


def _rule(kind: str, value: float = 0.0, period: int = 14) -> IndicatorAlertRule:
    return IndicatorAlertRule(id="t", symbol="X", kind=kind, value=value, period=period)  # type: ignore[arg-type]


def test_eval_rsi_below_fires_on_downtrend():
    fired, detail = _svc._eval_one_indicator(_rule("rsi_below", 30, 3), list(range(20, 1, -1)))
    assert fired is True and "RSI" in detail and "≤" in detail


def test_eval_rsi_below_does_not_fire_on_uptrend():
    fired, _ = _svc._eval_one_indicator(_rule("rsi_below", 30, 3), list(range(1, 20)))
    assert fired is False  # RSI 100 > 30


def test_eval_rsi_above_fires_on_uptrend():
    fired, _ = _svc._eval_one_indicator(_rule("rsi_above", 70, 3), list(range(1, 20)))
    assert fired is True  # RSI 100 ≥ 70


def test_eval_price_cross_sma_above_fires_on_breakout():
    # close was at/below SMA, then jumps above at the last bar.
    fired, detail = _svc._eval_one_indicator(_rule("price_cross_sma_above", period=3), [10, 10, 10, 10, 20])
    assert fired is True and "crossed above" in detail


def test_eval_price_cross_sma_above_no_cross_when_already_above():
    # already above the whole time → not a fresh cross.
    fired, _ = _svc._eval_one_indicator(_rule("price_cross_sma_above", period=3), [10, 20, 30, 40, 50])
    assert fired is False


def test_eval_macd_cross_bull_fires_on_reversal():
    # long decline (macd below signal) then a sharp 2-bar spike flips macd above signal
    # at the final bar (verified: 2nd-last macd==signal, last macd>signal).
    series = [100.0 - i for i in range(40)] + [60.0, 75.0]
    fired, detail = _svc._eval_one_indicator(_rule("macd_cross_bull"), series)
    assert fired is True and "bull cross" in detail


def test_eval_insufficient_data_does_not_fire():
    # too few points for SMA → graceful (False + reason), never a crash.
    fired, detail = _svc._eval_one_indicator(_rule("price_cross_sma_above", period=20), [10, 11])
    assert fired is False and "needs" in detail


# --------------------------------------------------------------------------- #
# Multi-symbol — Pearson correlation + comparison (math pinned)                  #
# --------------------------------------------------------------------------- #
def test_pearson_perfect_positive_is_1():
    assert ta.pearson([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0
    assert ta.pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) == 1.0  # y=2x still 1.0


def test_pearson_perfect_negative_is_minus_1():
    assert ta.pearson([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0


def test_pearson_handcalc():
    # x=[1,2,3] y=[1,3,2]: mean 2,2. cov=(-1)(-1)+0+0=1. varx=2, vary=2. r=1/√4=0.5
    assert ta.pearson([1, 2, 3], [1, 3, 2]) == 0.5


def test_pearson_flat_series_is_none():
    # a constant series has zero variance → correlation UNDEFINED (None, not 0).
    assert ta.pearson([5, 5, 5, 5], [1, 2, 3, 4]) is None


def test_pearson_too_few_points_is_none():
    assert ta.pearson([1], [1]) is None
    assert ta.pearson([], [1, 2, 3]) is None


def test_pearson_tail_aligns_mismatched_lengths():
    # [1,2,3,4,5] vs [4,5] → aligns to last 2 of x = [4,5] vs [4,5] → 1.0
    assert ta.pearson([1, 2, 3, 4, 5], [4, 5]) == 1.0


def test_correlation_matrix_structure_and_values():
    m = ta.correlation_matrix({"A": [1, 2, 3, 4, 5], "B": [2, 4, 6, 8, 10], "C": [5, 4, 3, 2, 1]})
    assert m["symbols"] == ["A", "B", "C"]
    assert m["matrix"]["A"]["B"] == 1.0   # co-move
    assert m["matrix"]["A"]["C"] == -1.0  # inverse
    assert m["matrix"]["A"]["A"] == 1.0   # diagonal
    assert m["matrix"]["B"]["A"] == m["matrix"]["A"]["B"]  # symmetric


def test_correlation_matrix_short_series_warns_none():
    m = ta.correlation_matrix({"A": [1, 2, 3], "B": [5]})  # B has 1 point
    assert m["matrix"]["A"]["B"] is None
    assert m["matrix"]["B"]["B"] is None  # <2 points → diagonal None too
    assert any("B" in w for w in m["warnings"])


def test_compare_metrics_structure_and_handcalc():
    # [100,...,140] → change (140-100)/100 = 40%; vol present; rsi None (<15 pts);
    # trend 'flat' because summarize's SMA-50 trend needs ≥50 points (honest partial).
    c = ta.compare_metrics([100, 110, 99, 121, 130, 125, 140])
    assert c["changePct"] == 40.0
    assert c["volatility"] is not None
    assert c["rsi"] is None  # 7 < 15 points → RSI-14 undefined
    assert c["trend"] == "flat"  # short series → no SMA-50 trend yet
    assert c["points"] == 7


def test_compare_metrics_trend_up_with_enough_points():
    # a long RISING series → SMA-50 slope up → trend 'up' (proves trend works given data)
    c = ta.compare_metrics([float(i) for i in range(1, 80)])  # 79 rising points
    assert c["trend"] == "up" and c["rsi"] is not None


def test_compare_metrics_empty_is_honest_none():
    c = ta.compare_metrics([])
    assert c["changePct"] is None and c["volatility"] is None and c["rsi"] is None


def test_relative_strength_outperform_is_up():
    # symbol rises, benchmark flat → ratio rises → outperforming → 'up'
    rs = ta.relative_strength([100, 110, 120, 140], [100, 100, 100, 100])
    assert rs["ratioTrend"] == "up" and rs["ratioChangePct"] == 40.0


def test_relative_strength_underperform_is_down():
    rs = ta.relative_strength([100, 90, 80], [100, 100, 100])
    assert rs["ratioTrend"] == "down"


def test_relative_strength_insufficient_overlap():
    rs = ta.relative_strength([100], [100, 200])
    assert rs["latestRatio"] is None and "need ≥2" in rs["warning"]


# --------------------------------------------------------------------------- #
# outlier guard — sanitize_series (robust, generic, no hardcoded price)         #
# --------------------------------------------------------------------------- #
def test_sanitize_drops_stray_low_point_among_real_prices():
    # the ACTUAL bug: a $0.5 seed row inside a ~$60k BTC series. Generic MAD/ratio
    # math must drop it (it's ~120,000× below the median) — NOT hardcoded to $0.5.
    raw = [60000, 61000, 0.5, 62000, 61500, 60500, 63000, 62500]
    kept, warn = ta.sanitize_series(raw)
    assert 0.5 not in kept
    assert kept == [60000, 61000, 62000, 61500, 60500, 63000, 62500]
    assert warn is not None and "filtered 1" in warn


def test_sanitize_stray_point_fixes_pct_change():
    # before filtering, _pct_change over [0.5, ..., 63000] would be a ~12,600,000%
    # explosion; after the guard the change is the honest ~5% the real prices moved.
    raw = [0.5, 60000, 61000, 62000, 61500, 63000]
    kept, _ = ta.sanitize_series(raw)
    change = ta._pct_change(kept)
    assert change is not None and abs(change) < 100.0  # sane, not 12 million %


def test_sanitize_drops_stray_high_point():
    # a single absurd HIGH spike (fat-finger 100×) is also removed (ratio ≥ 8×).
    raw = [100, 102, 99, 101, 9_000_000, 103, 98, 100]
    kept, warn = ta.sanitize_series(raw)
    assert 9_000_000 not in kept and "filtered 1" in warn


def test_sanitize_clean_series_unchanged_no_false_positive():
    # a normal, even quite volatile, series (no point an order of magnitude off the
    # median) must be returned UNCHANGED with no warning — zero false positives.
    raw = [100, 130, 90, 145, 80, 150, 70, 160, 110, 95]
    kept, warn = ta.sanitize_series(raw)
    assert kept == [float(x) for x in raw] and warn is None


def test_sanitize_trending_2x_series_not_flagged():
    # a coin that legitimately doubles over the window: ratio to median ≈ 2 (< 8),
    # so NOTHING is filtered (we only catch order-of-magnitude artifacts, not trends).
    raw = [100, 110, 120, 135, 150, 165, 180, 195, 200]
    kept, warn = ta.sanitize_series(raw)
    assert kept == [float(x) for x in raw] and warn is None


def test_sanitize_flat_series_not_flagged():
    # every point equals the median (MAD 0, ratio 1) → never an outlier.
    kept, warn = ta.sanitize_series([500, 500, 500, 500, 500])
    assert kept == [500.0, 500.0, 500.0, 500.0, 500.0] and warn is None


def test_sanitize_near_flat_with_tiny_wobble_not_gutted():
    # MAD is tiny here, but no point is an order of magnitude off → ratio floor keeps
    # them all (the bug we guard against: MAD-only would wrongly drop the 501).
    kept, warn = ta.sanitize_series([500, 500, 500, 501, 500, 500])
    assert kept == [500.0, 500.0, 500.0, 501.0, 500.0, 500.0] and warn is None


def test_sanitize_short_series_kept_as_is():
    # <4 points → can't robustly estimate median/MAD → return cleaned, no filtering.
    kept, warn = ta.sanitize_series([0.5, 60000, 61000])
    assert kept == [0.5, 60000.0, 61000.0] and warn is None


def test_sanitize_nonpositive_price_dropped():
    # a 0 or negative price is never a valid crypto close → always removed.
    kept, warn = ta.sanitize_series([60000, 61000, 0, 62000, 61500, -5, 63000])
    assert 0 not in kept and -5 not in kept
    assert "filtered 2" in warn


def test_sanitize_too_few_positives_kept_as_is():
    # can't robustly log-scale fewer than 4 positive prices → keep cleaned, no claim
    # (don't guess on data we can't characterize). All-non-positive lands here.
    kept, warn = ta.sanitize_series([0, -1, -2, 0])
    assert kept == [0.0, -1.0, -2.0, 0.0] and warn is None


def test_sanitize_never_guts_series_to_empty():
    # INVARIANT: for any non-empty input with ≥1 valid point, the guard never returns
    # [] (gutting all data). Spot-check across mixed pathological shapes — the result
    # always retains at least one point (filter is additive-safe, never destructive).
    for raw in (
        [0.5, 0.5, 0.5, 0.5],            # all identical tiny (flat → none flagged)
        [60000, 0.5, 0.5, 0.5],          # majority tiny, one big
        [1e-9, 1e-9, 1e9, 1e9],          # two far-apart clusters
        [100, 100, 100, 0.0001],         # one micro outlier
    ):
        kept, _ = ta.sanitize_series(raw)
        assert len(kept) >= 1, f"sanitize gutted {raw} to empty"


def test_sanitize_then_correlation_robust_to_stray():
    # two series that co-move, but one has a stray $0.5 → after sanitize, both align
    # to their real points and correlate cleanly (the stray doesn't poison the matrix).
    a = ta.sanitize_series([100, 110, 0.5, 120, 130, 140, 150])[0]
    b = ta.sanitize_series([200, 220, 240, 260, 280, 300])[0]
    r = ta.pearson(a, b)
    assert r is not None and r > 0.9  # still strongly positive, not wrecked
