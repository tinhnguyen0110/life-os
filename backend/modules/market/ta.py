"""modules/market/ta.py — pure technical-analysis indicators (Sprint TA).

Deterministic, dependency-free TA over a price series (list of close prices, oldest
→ newest, the shape ``market.service.history()`` returns). NO TA-Lib / numpy — every
formula is hand-implemented so it's testable against known reference values and has
no native-build dependency.

Design contract (every indicator):
- INPUT: ``values`` = list[float] close prices oldest→newest, + a ``period`` int.
- OUTPUT: a dataclass carrying the full ``series`` (aligned to input length, with
  ``None`` for the warm-up window where the indicator isn't defined yet) + ``latest``
  (the most recent defined value, or None) + a ``warning`` when the series is too
  short to compute anything.
- EDGE CASES (all handled, never raises): empty series, series shorter than period,
  None / NaN entries (filtered with a warning), period <= 0.

These are NEUTRAL technical signals only — NO buy/sell advice (see ``summarize``).

Reference formulas (the standard ones; chosen so tests can pin exact values):
- SMA   = mean of the trailing ``period`` values.
- EMA   = α·price + (1−α)·prev_ema, α = 2/(period+1), seeded with the SMA of the
          first ``period`` values (the conventional seed).
- RSI   = Wilder's RSI: RMA(gains)/RMA(losses) over ``period``; RMA seeded with the
          simple average of the first ``period`` deltas (Wilder 1978).
- MACD  = EMA(fast) − EMA(slow); signal = EMA(signal_period) of the MACD line;
          histogram = MACD − signal.
- BBands= middle = SMA(period); upper/lower = middle ± k·population-stddev(period).
- ATR   = Wilder's ATR of the True Range; TR = max(high−low, |high−prevClose|,
          |low−prevClose|). Close-only series → TR degrades to |close−prevClose|.
- vol   = volume trend = SMA(short) vs SMA(long) of volume → up/down/flat + ratio.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- #
# result containers                                                             #
# --------------------------------------------------------------------------- #
@dataclass
class IndicatorResult:
    """A single-series indicator (SMA/EMA/RSI/ATR/...).

    ``series`` is input-length-aligned: positions before the indicator is defined
    are ``None``. ``latest`` is the last non-None value (None if never defined)."""

    name: str
    period: int
    series: list[Optional[float]]
    latest: Optional[float]
    warning: Optional[str] = None


@dataclass
class MACDResult:
    name: str = "macd"
    fast: int = 12
    slow: int = 26
    signal_period: int = 9
    macd: list[Optional[float]] = field(default_factory=list)
    signal: list[Optional[float]] = field(default_factory=list)
    histogram: list[Optional[float]] = field(default_factory=list)
    latest_macd: Optional[float] = None
    latest_signal: Optional[float] = None
    latest_histogram: Optional[float] = None
    warning: Optional[str] = None


@dataclass
class BollingerResult:
    name: str = "bollinger"
    period: int = 20
    num_std: float = 2.0
    middle: list[Optional[float]] = field(default_factory=list)
    upper: list[Optional[float]] = field(default_factory=list)
    lower: list[Optional[float]] = field(default_factory=list)
    latest_middle: Optional[float] = None
    latest_upper: Optional[float] = None
    latest_lower: Optional[float] = None
    warning: Optional[str] = None


# --------------------------------------------------------------------------- #
# input sanitation — shared by every indicator (NaN-safe, never raises)         #
# --------------------------------------------------------------------------- #
def _clean(values: list) -> tuple[list[float], Optional[str]]:
    """Drop None / NaN / non-numeric entries, preserving order. Returns
    ``(cleaned, warning)`` — warning names how many entries were dropped (or None)."""
    if not values:
        return [], "empty series"
    cleaned: list[float] = []
    dropped = 0
    for v in values:
        if v is None:
            dropped += 1
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            dropped += 1
            continue
        if math.isnan(f) or math.isinf(f):
            dropped += 1
            continue
        cleaned.append(f)
    warn = f"dropped {dropped} invalid (None/NaN) point(s)" if dropped else None
    return cleaned, warn


def _round(x: Optional[float], nd: int = 6) -> Optional[float]:
    return None if x is None else round(x, nd)


def _median(xs: list[float]) -> float:
    """Median of a NON-EMPTY list (caller guarantees len ≥ 1)."""
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


# --------------------------------------------------------------------------- #
# outlier guard — robust filter for stray/corrupt price points (Sprint 28)      #
# --------------------------------------------------------------------------- #
# Live price_history can carry seed/test artifacts (e.g. a $0.5 row in a series
# whose real prices are ~$60,000) that make changePct / correlation explode. We do
# NOT mutate the DB — instead the analytics READ path filters these points before
# computing. The test is ROBUST + GENERIC (no hardcoded price/coin):
#   - work in LOG space (prices are positive + multiplicatively distributed, so a
#     $0.5 among $60k is ~11.7 log-units from the median while a coin doubling is
#     only 0.69 — log space separates "wrong by orders of magnitude" from "moved").
#   - flag a point whose log-distance from the median exceeds ``k`` robust MADs
#     (median-absolute-deviation, the breakdown-robust spread estimate).
#   - a RATIO FLOOR (``min_ratio``) guarantees we only ever drop points that are
#     also at least an order of magnitude off the median (≥ ~10× or ≤ ~1/10). This
#     is what prevents false positives on a low-volatility series whose MAD is tiny:
#     a 5% wobble is many MADs out numerically but nowhere near 10× the median, so
#     it is KEPT. Only genuine order-of-magnitude artifacts get removed.
# A flat series (MAD 0) is never flagged (every point equals the median → ratio 1).
OUTLIER_MAD_K = 6.0       # log-distance must exceed this many MADs to be a candidate
OUTLIER_MIN_RATIO = 8.0   # AND be ≥8× or ≤1/8 the median — guards against false positives


def sanitize_series(values: list, *, k: float = OUTLIER_MAD_K,
                    min_ratio: float = OUTLIER_MIN_RATIO) -> tuple[list[float], Optional[str]]:
    """Drop None/NaN (via _clean) THEN remove gross price outliers, robustly + generically.

    A point is an outlier ONLY if BOTH hold (so we never over-filter):
      1) its log-distance from the median exceeds ``k`` robust MADs, AND
      2) it is ≥ ``min_ratio``× or ≤ 1/``min_ratio`` the median price.
    Condition (2) is an absolute order-of-magnitude floor — a clean or merely
    volatile series (no point an order of magnitude off the median) is returned
    UNCHANGED (no false positives). A flat series is never flagged. Non-positive
    prices (≤0) can't be log-scaled and are always treated as outliers (a real
    crypto price is > 0). Returns ``(kept, warning)`` — warning names how many
    points were filtered (None if none were)."""
    clean, _ = _clean(values)
    n = len(clean)
    if n < 4:
        # too few points to robustly estimate a median/MAD — keep as-is (the
        # downstream math already degrades honestly to None on thin series).
        return clean, None

    positives = [v for v in clean if v > 0]
    if len(positives) < 4:
        return clean, None  # can't log-scale enough points → don't guess
    logs = [math.log(v) for v in positives]
    med_log = _median(logs)
    abs_dev = [abs(lg - med_log) for lg in logs]
    mad = _median(abs_dev)
    med_price = math.exp(med_log)

    kept: list[float] = []
    dropped = 0
    for v in clean:
        if v <= 0:
            dropped += 1  # non-positive price is never a valid crypto close
            continue
        ratio = v / med_price if med_price > 0 else 1.0
        order_of_mag_off = ratio >= min_ratio or ratio <= 1.0 / min_ratio
        if mad > 0:
            log_dist = abs(math.log(v) - med_log)
            mad_off = log_dist > k * mad
        else:
            # MAD 0 = the bulk of points are identical; only flag a point that is
            # ALSO an order of magnitude off (so a near-flat series isn't gutted).
            mad_off = order_of_mag_off
        if mad_off and order_of_mag_off:
            dropped += 1
            continue
        kept.append(v)

    if dropped == 0:
        return clean, None
    # never return fewer than is useful by accident — if everything got dropped
    # (pathological), fall back to the cleaned series + a warning instead of [].
    if not kept:
        return clean, (f"detected {dropped} anomalous point(s) but all points "
                       "looked anomalous — kept series unfiltered for safety")
    return kept, (f"filtered {dropped} anomalous price point(s) "
                  f"(≫/≪ {min_ratio:g}× the median ~{round(med_price, 2)}) before computing")


# --------------------------------------------------------------------------- #
# SMA                                                                           #
# --------------------------------------------------------------------------- #
def sma(values: list, period: int = 20) -> IndicatorResult:
    """Simple moving average over the trailing ``period`` closes."""
    clean, warn = _clean(values)
    if period <= 0:
        return IndicatorResult("sma", period, [], None, "period must be > 0")
    series: list[Optional[float]] = [None] * len(clean)
    if len(clean) < period:
        w = warn or f"series ({len(clean)}) shorter than period ({period})"
        return IndicatorResult("sma", period, series, None, w)
    running = sum(clean[:period])
    series[period - 1] = running / period
    for i in range(period, len(clean)):
        running += clean[i] - clean[i - period]
        series[i] = running / period
    out = [_round(v) for v in series]
    return IndicatorResult("sma", period, out, out[-1], warn)


# --------------------------------------------------------------------------- #
# EMA                                                                           #
# --------------------------------------------------------------------------- #
def _ema_series(clean: list[float], period: int) -> list[Optional[float]]:
    """EMA aligned to ``clean`` length: None until index period-1, where it is
    seeded with the SMA of the first ``period`` values, then recurses."""
    n = len(clean)
    series: list[Optional[float]] = [None] * n
    if period <= 0 or n < period:
        return series
    alpha = 2.0 / (period + 1)
    prev = sum(clean[:period]) / period  # SMA seed (conventional)
    series[period - 1] = prev
    for i in range(period, n):
        prev = alpha * clean[i] + (1 - alpha) * prev
        series[i] = prev
    return series


def ema(values: list, period: int = 20) -> IndicatorResult:
    """Exponential moving average, α=2/(period+1), SMA-seeded."""
    clean, warn = _clean(values)
    if period <= 0:
        return IndicatorResult("ema", period, [], None, "period must be > 0")
    if len(clean) < period:
        w = warn or f"series ({len(clean)}) shorter than period ({period})"
        return IndicatorResult("ema", period, [None] * len(clean), None, w)
    series = _ema_series(clean, period)
    out = [_round(v) for v in series]
    latest = next((v for v in reversed(out) if v is not None), None)
    return IndicatorResult("ema", period, out, latest, warn)


# --------------------------------------------------------------------------- #
# RSI (Wilder)                                                                  #
# --------------------------------------------------------------------------- #
def rsi(values: list, period: int = 14) -> IndicatorResult:
    """Wilder's RSI. Needs ``period``+1 points (period deltas). RMA-smoothed gains/
    losses; a zero average-loss → RSI 100 (no down moves)."""
    clean, warn = _clean(values)
    if period <= 0:
        return IndicatorResult("rsi", period, [], None, "period must be > 0")
    n = len(clean)
    series: list[Optional[float]] = [None] * n
    if n < period + 1:
        w = warn or f"series ({n}) shorter than period+1 ({period + 1})"
        return IndicatorResult("rsi", period, series, None, w)

    deltas = [clean[i] - clean[i - 1] for i in range(1, n)]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    # Wilder seed: simple average of the first ``period`` gains/losses.
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi_from(g: float, l: float) -> float:
        if l == 0:
            return 100.0
        rs = g / l
        return 100.0 - (100.0 / (1.0 + rs))

    # first RSI lands at index ``period`` (0-based over clean prices).
    series[period] = _rsi_from(avg_gain, avg_loss)
    for i in range(period + 1, n):
        g, l = gains[i - 1], losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        series[i] = _rsi_from(avg_gain, avg_loss)

    out = [_round(v, 4) for v in series]
    return IndicatorResult("rsi", period, out, out[-1], warn)


# --------------------------------------------------------------------------- #
# MACD                                                                          #
# --------------------------------------------------------------------------- #
def macd(values: list, fast: int = 12, slow: int = 26, signal_period: int = 9) -> MACDResult:
    """MACD = EMA(fast) − EMA(slow); signal = EMA(signal_period) of the MACD line;
    histogram = MACD − signal. The MACD line is only defined where BOTH EMAs are."""
    clean, warn = _clean(values)
    if min(fast, slow, signal_period) <= 0 or fast >= slow:
        return MACDResult(fast=fast, slow=slow, signal_period=signal_period,
                          warning="need 0 < fast < slow and signal_period > 0")
    n = len(clean)
    if n < slow:
        w = warn or f"series ({n}) shorter than slow period ({slow})"
        return MACDResult(fast=fast, slow=slow, signal_period=signal_period,
                          macd=[None] * n, signal=[None] * n, histogram=[None] * n,
                          warning=w)

    ema_fast = _ema_series(clean, fast)
    ema_slow = _ema_series(clean, slow)
    macd_line: list[Optional[float]] = []
    for i in range(n):
        f, sl = ema_fast[i], ema_slow[i]
        macd_line.append(f - sl if (f is not None and sl is not None) else None)

    # signal = EMA of the macd line over its DEFINED tail (compact, then re-aligned).
    defined: list[tuple[int, float]] = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    signal_line: list[Optional[float]] = [None] * n
    if len(defined) >= signal_period:
        compact = [v for _i, v in defined]
        sig_compact = _ema_series(compact, signal_period)
        for (orig_i, _v), sig in zip(defined, sig_compact):
            signal_line[orig_i] = sig

    histogram: list[Optional[float]] = []
    for i in range(n):
        ml, sg = macd_line[i], signal_line[i]
        histogram.append(ml - sg if (ml is not None and sg is not None) else None)

    macd_out = [_round(v) for v in macd_line]
    signal_out = [_round(v) for v in signal_line]
    hist_out = [_round(v) for v in histogram]
    last_m = next((v for v in reversed(macd_out) if v is not None), None)
    last_s = next((v for v in reversed(signal_out) if v is not None), None)
    last_h = next((v for v in reversed(hist_out) if v is not None), None)
    return MACDResult(fast=fast, slow=slow, signal_period=signal_period,
                      macd=macd_out, signal=signal_out, histogram=hist_out,
                      latest_macd=last_m, latest_signal=last_s, latest_histogram=last_h,
                      warning=warn)


# --------------------------------------------------------------------------- #
# Bollinger Bands                                                               #
# --------------------------------------------------------------------------- #
def bollinger(values: list, period: int = 20, num_std: float = 2.0) -> BollingerResult:
    """middle = SMA(period); upper/lower = middle ± num_std · population-stddev over
    the same trailing window."""
    clean, warn = _clean(values)
    n = len(clean)
    if period <= 0:
        return BollingerResult(period=period, num_std=num_std, warning="period must be > 0")
    middle: list[Optional[float]] = [None] * n
    upper: list[Optional[float]] = [None] * n
    lower: list[Optional[float]] = [None] * n
    if n < period:
        w = warn or f"series ({n}) shorter than period ({period})"
        return BollingerResult(period=period, num_std=num_std,
                               middle=middle, upper=upper, lower=lower, warning=w)
    for i in range(period - 1, n):
        window = clean[i - period + 1: i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period  # population variance
        sd = math.sqrt(var)
        middle[i] = mean
        upper[i] = mean + num_std * sd
        lower[i] = mean - num_std * sd
    mid = [_round(v) for v in middle]
    up = [_round(v) for v in upper]
    lo = [_round(v) for v in lower]
    return BollingerResult(period=period, num_std=num_std, middle=mid, upper=up, lower=lo,
                           latest_middle=mid[-1], latest_upper=up[-1], latest_lower=lo[-1],
                           warning=warn)


# --------------------------------------------------------------------------- #
# ATR (Wilder) — OHLC if available, else close-to-close                         #
# --------------------------------------------------------------------------- #
def atr(highs: Optional[list] = None, lows: Optional[list] = None,
        closes: Optional[list] = None, period: int = 14) -> IndicatorResult:
    """Wilder's Average True Range. With high/low/close → full TR. With ONLY closes
    (price_history is close-only) → TR degrades to |close − prevClose| (a close-to-
    close volatility proxy; flagged in the warning)."""
    if period <= 0:
        return IndicatorResult("atr", period, [], None, "period must be > 0")

    close_only = highs is None or lows is None
    base_warn: Optional[str] = None
    warn: Optional[str] = None
    if close_only:
        if closes is None:
            return IndicatorResult("atr", period, [], None, "need closes (and ideally highs/lows)")
        c, warn = _clean(closes)
        h = l = c
        base_warn = "close-only series → ATR uses |close−prevClose| (no true high/low)"
    else:
        h, wh = _clean(highs or [])
        l, wl = _clean(lows or [])
        c, wc = _clean(closes or [])
        warn = wh or wl or wc
        m = min(len(h), len(l), len(c))
        h, l, c = h[:m], l[:m], c[:m]  # align (defensive on ragged input)

    n = len(c)
    series: list[Optional[float]] = [None] * n
    if n < period + 1:
        w = base_warn or warn or f"series ({n}) shorter than period+1 ({period + 1})"
        return IndicatorResult("atr", period, series, None, w)

    # True Range, index 1..n-1 (needs a prev close).
    tr: list[float] = []
    for i in range(1, n):
        prev_c = c[i - 1]
        tr.append(max(h[i] - l[i], abs(h[i] - prev_c), abs(l[i] - prev_c)))

    # Wilder seed: simple mean of the first ``period`` TRs → lands at index ``period``.
    atr_val = sum(tr[:period]) / period
    series[period] = atr_val
    for i in range(period + 1, n):
        atr_val = (atr_val * (period - 1) + tr[i - 1]) / period
        series[i] = atr_val

    out = [_round(v) for v in series]
    final_warn: Optional[str] = base_warn or warn
    return IndicatorResult("atr", period, out, out[-1], final_warn)


# --------------------------------------------------------------------------- #
# volume trend                                                                  #
# --------------------------------------------------------------------------- #
def volume_trend(volumes: list, short: int = 5, long: int = 20) -> IndicatorResult:
    """Volume trend = SMA(short) vs SMA(long). ``latest`` = short/long ratio (>1 →
    volume rising vs its longer baseline, <1 → falling). The ``warning`` carries the
    direction label up/down/flat. Both SMAs must be defined at the last point."""
    clean, warn = _clean(volumes)
    if short <= 0 or long <= 0 or short >= long:
        return IndicatorResult("volume_trend", long, [], None, "need 0 < short < long")
    n = len(clean)
    if n < long:
        w = warn or f"series ({n}) shorter than long period ({long})"
        return IndicatorResult("volume_trend", long, [None] * n, None, w)
    sma_short = sma(clean, short).series
    sma_long = sma(clean, long).series
    ratio_series: list[Optional[float]] = []
    for i in range(n):
        ss, sl = sma_short[i], sma_long[i]
        ratio_series.append(ss / sl if (ss is not None and sl is not None and sl != 0) else None)
    out = [_round(v) for v in ratio_series]
    latest = out[-1]
    if latest is None:
        return IndicatorResult("volume_trend", long, out, None, warn)
    direction = "up" if latest > 1.05 else ("down" if latest < 0.95 else "flat")
    label = f"volume trend {direction} (short/long ratio {latest})"
    return IndicatorResult("volume_trend", long, out, latest, warn or label)


# --------------------------------------------------------------------------- #
# summary — combined NEUTRAL technical signals (NO buy/sell advice)             #
# --------------------------------------------------------------------------- #
def summarize(closes: list, *, rsi_period: int = 14, sma_fast: int = 50,
              sma_slow: int = 200, bb_period: int = 20) -> dict:
    """Roll up the indicators + emit NEUTRAL technical signals (NOT advice):

      - rsi_signal: overbought (RSI≥70) | oversold (RSI≤30) | neutral
      - cross_signal: golden_cross (fast SMA crossed ABOVE slow this step) |
                      death_cross (fast crossed BELOW slow) | fast_above | fast_below |
                      none (insufficient data)
      - bb_signal: above_upper | below_lower | inside (price vs latest Bollinger band)
      - trend: up | down | flat (latest fast-SMA slope sign)

    These are deterministic TECHNICAL observations. They are explicitly NOT a
    recommendation to buy or sell — the consumer decides. ``signals_only`` is True
    to make that contract machine-readable."""
    clean, warn = _clean(closes)
    rsi_r = rsi(clean, rsi_period)
    sma_f = sma(clean, sma_fast)
    sma_s = sma(clean, sma_slow)
    bb = bollinger(clean, bb_period)

    # rsi signal
    rsi_signal = "neutral"
    if rsi_r.latest is not None:
        if rsi_r.latest >= 70:
            rsi_signal = "overbought"
        elif rsi_r.latest <= 30:
            rsi_signal = "oversold"

    # cross signal — compare the last TWO points where both SMAs are defined.
    cross_signal = "none"
    sf, ss = sma_f.series, sma_s.series
    pairs: list[tuple[float, float]] = []
    for i in range(len(clean)):
        a, b = sf[i], ss[i]
        if a is not None and b is not None:
            pairs.append((a, b))
    if len(pairs) >= 2:
        (pf, ps), (cf, cs) = pairs[-2], pairs[-1]
        prev_above, now_above = pf > ps, cf > cs
        if not prev_above and now_above:
            cross_signal = "golden_cross"
        elif prev_above and not now_above:
            cross_signal = "death_cross"
        else:
            cross_signal = "fast_above" if now_above else "fast_below"
    elif len(pairs) == 1:
        cross_signal = "fast_above" if pairs[0][0] > pairs[0][1] else "fast_below"

    # bollinger position of the latest close
    bb_signal = "inside"
    if clean and bb.latest_upper is not None and bb.latest_lower is not None:
        last = clean[-1]
        if last > bb.latest_upper:
            bb_signal = "above_upper"
        elif last < bb.latest_lower:
            bb_signal = "below_lower"

    # trend = sign of the latest fast-SMA slope (last two defined fast-SMA points)
    trend = "flat"
    fast_defined = [v for v in sf if v is not None]
    if len(fast_defined) >= 2:
        d = fast_defined[-1] - fast_defined[-2]
        trend = "up" if d > 0 else ("down" if d < 0 else "flat")

    return {
        "signals_only": True,  # NEUTRAL technical signals — NOT buy/sell advice
        "latest": {
            "rsi": rsi_r.latest,
            "sma_fast": sma_f.latest,
            "sma_slow": sma_s.latest,
            "bb_upper": bb.latest_upper,
            "bb_middle": bb.latest_middle,
            "bb_lower": bb.latest_lower,
            "close": clean[-1] if clean else None,
        },
        "signals": {
            "rsi": rsi_signal,
            "cross": cross_signal,
            "bollinger": bb_signal,
            "trend": trend,
        },
        "warning": warn,
    }


# --------------------------------------------------------------------------- #
# Multi-symbol — Pearson correlation + comparison (pure math, NEUTRAL)           #
# --------------------------------------------------------------------------- #
def pearson(a: list, b: list) -> Optional[float]:
    """Pearson correlation of two series (cleaned + tail-aligned to equal length).

    Returns a value in [-1, 1], or None when it's undefined: <2 overlapping points,
    or either aligned series is constant (zero variance → correlation undefined, NOT
    0). Perfectly co-moving → 1.0; perfectly inverse → -1.0."""
    ca, _ = _clean(a)
    cb, _ = _clean(b)
    m = min(len(ca), len(cb))
    if m < 2:
        return None
    # align to the most-recent ``m`` points of each (tail-align).
    x, y = ca[-m:], cb[-m:]
    mean_x = sum(x) / m
    mean_y = sum(y) / m
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(m))
    var_x = sum((v - mean_x) ** 2 for v in x)
    var_y = sum((v - mean_y) ** 2 for v in y)
    if var_x == 0 or var_y == 0:  # a flat series has no correlation to anything
        return None
    r = cov / math.sqrt(var_x * var_y)
    # clamp tiny FP overshoot into [-1, 1].
    return round(max(-1.0, min(1.0, r)), 4)


def correlation_matrix(series_by_symbol: dict[str, list]) -> dict:
    """Pairwise Pearson correlation matrix over the given symbol→series map.

    Returns ``{symbols:[...], matrix:{a:{b: r|None}}, warnings:[...]}``. Diagonal is
    1.0 (a symbol vs itself, when it has ≥2 points). A pair with no overlap / a flat
    series → None (honest, never fabricated). Symbols with <2 points are kept but warn."""
    symbols = list(series_by_symbol.keys())
    warnings: list[str] = []
    cleaned: dict[str, list[float]] = {}
    for s in symbols:
        c, _ = _clean(series_by_symbol[s])
        cleaned[s] = c
        if len(c) < 2:
            warnings.append(f"{s}: <2 data points — correlations involving it are None")

    matrix: dict[str, dict[str, Optional[float]]] = {}
    for a in symbols:
        matrix[a] = {}
        for b in symbols:
            if a == b:
                matrix[a][b] = 1.0 if len(cleaned[a]) >= 2 else None
            else:
                matrix[a][b] = pearson(cleaned[a], cleaned[b])
    return {"symbols": symbols, "matrix": matrix, "warnings": warnings}


def _pct_change(values: list[float]) -> Optional[float]:
    """% change first→last of a series. None if <2 points or the first is 0."""
    if len(values) < 2 or values[0] == 0:
        return None
    return round((values[-1] - values[0]) / values[0] * 100.0, 4)


def _volatility(values: list[float]) -> Optional[float]:
    """Sample-stddev of period-over-period % returns (the standard volatility proxy).
    None if <3 points (need ≥2 returns for a sample stddev)."""
    if len(values) < 3:
        return None
    rets = [(values[i] - values[i - 1]) / values[i - 1] * 100.0
            for i in range(1, len(values)) if values[i - 1] != 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(var ** 0.5, 4)


def compare_metrics(closes: list) -> dict:
    """One symbol's comparison metrics (for ranking N symbols side-by-side):
    ``{changePct, volatility, rsi, trend, points}``. Each is None when the series is
    too short to compute it — honest partials, never fabricated. NEUTRAL — no advice."""
    clean, warn = _clean(closes)
    change = _pct_change(clean)
    vol = _volatility(clean)
    rsi_r = rsi(clean, 14)
    summ = summarize(clean) if clean else None
    return {
        "changePct": change,
        "volatility": vol,
        "rsi": rsi_r.latest,
        "trend": (summ["signals"]["trend"] if summ else "flat"),
        "points": len(clean),
        "warning": warn,
    }


def relative_strength(closes: list, benchmark: list) -> dict:
    """Relative strength of a symbol vs a benchmark series: the RATIO series
    (symbol/benchmark) + its trend + the ratio's % change over the window. A RISING
    ratio = the symbol is OUTPERFORMING the benchmark (NEUTRAL observation, NOT a
    recommendation). Returns ``{ratioChangePct, ratioTrend, latestRatio, warning}``;
    None fields when there's insufficient overlapping data."""
    cs, _ = _clean(closes)
    cb, _ = _clean(benchmark)
    m = min(len(cs), len(cb))
    if m < 2:
        return {"ratioChangePct": None, "ratioTrend": "flat", "latestRatio": None,
                "warning": f"need ≥2 overlapping points (have {m})"}
    x, y = cs[-m:], cb[-m:]
    ratio = [x[i] / y[i] for i in range(m) if y[i] != 0]
    if len(ratio) < 2:
        return {"ratioChangePct": None, "ratioTrend": "flat", "latestRatio": None,
                "warning": "benchmark has zero/insufficient prices"}
    change = _pct_change(ratio)
    trend = "up" if ratio[-1] > ratio[0] else ("down" if ratio[-1] < ratio[0] else "flat")
    return {
        "ratioChangePct": change,
        "ratioTrend": trend,  # up = outperforming benchmark (neutral)
        "latestRatio": round(ratio[-1], 6),
        "warning": None,
    }
