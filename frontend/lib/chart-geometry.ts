/* ============================================================
   chart-geometry (FE-2) — pure SVG-path math for the market price chart.
   No React, no DOM — deterministic, unit-testable. Hardened against empty /
   single-point / all-equal series (never emits NaN). Y is inverted (SVG origin
   top-left) so higher price = higher on screen.
   ============================================================ */

export interface ChartScale {
  w: number;
  h: number;
  min: number;
  max: number;
  /** number of points */
  n: number;
}

/** x pixel for point index i (0..n-1). Single point → centered. */
export function xAt(i: number, scale: ChartScale): number {
  const { w, n } = scale;
  if (n <= 1) return w / 2;
  return (i / (n - 1)) * w;
}

/** y pixel for a value (inverted; flat series → vertical middle). */
export function yAt(v: number, scale: ChartScale): number {
  const { h, min, max } = scale;
  const range = max - min;
  if (range <= 0) return h / 2;
  return h - ((v - min) / range) * h;
}

/** Build a ChartScale from a value series + canvas size, with a small headroom pad. */
export function buildScale(values: number[], w: number, h: number, padPct = 0.06): ChartScale {
  const n = values.length;
  if (n === 0) return { w, h, min: 0, max: 1, n: 0 };
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) { min -= 1; max += 1; } // flat series → give it a band
  const pad = (max - min) * padPct;
  return { w, h, min: min - pad, max: max + pad, n };
}

/** polyline "x,y x,y ..." for the close line. Empty → "". */
export function linePoints(values: number[], scale: ChartScale): string {
  if (values.length === 0) return "";
  return values
    .map((v, i) => `${xAt(i, scale).toFixed(2)},${yAt(v, scale).toFixed(2)}`)
    .join(" ");
}

/** Closed area path (line + baseline) for the gradient fill. Empty → "". */
export function areaPath(values: number[], scale: ChartScale): string {
  if (values.length === 0) return "";
  const { w, h } = scale;
  const pts = values.map((v, i) => `${xAt(i, scale).toFixed(2)},${yAt(v, scale).toFixed(2)}`);
  const firstX = values.length === 1 ? (w / 2).toFixed(2) : "0.00";
  const lastX = values.length === 1 ? (w / 2).toFixed(2) : w.toFixed(2);
  return `M${firstX},${h.toFixed(2)} L${pts.join(" L")} L${lastX},${h.toFixed(2)} Z`;
}

/**
 * Nearest point index for a pixel x (for hover). Clamps to [0, n-1]. Empty → -1.
 * Inverse of xAt: i ≈ round(px / w * (n-1)).
 */
export function indexAtX(px: number, scale: ChartScale): number {
  const { w, n } = scale;
  if (n === 0) return -1;
  if (n === 1) return 0;
  if (!Number.isFinite(px) || w <= 0) return 0; // NaN / zero-width → first point
  const i = Math.round((px / w) * (n - 1));
  return Math.max(0, Math.min(n - 1, i));
}

// ─────────────────────────────────────────────────────────────────────────────
// FE-2A additions (append-only — existing signatures above are unchanged).
// Indicator overlays come on a DIFFERENT-length series than the candle x-axis
// (e.g. 1673 raw price points vs 148 candles over the same window). These helpers
// resample a source series to a target length so overlays align with the chart.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Resample `src` (possibly with null warm-up gaps) to exactly `targetLen` points
 * by proportional index mapping: out[i] = src[round(i/(targetLen-1) * (m-1))].
 * Both series are assumed oldest→newest over the SAME time window. null entries
 * are preserved (a warm-up gap stays a gap). Empty src / targetLen<1 → [].
 */
export function resampleSeries(src: (number | null)[], targetLen: number): (number | null)[] {
  const m = src.length;
  if (m === 0 || targetLen < 1) return [];
  if (targetLen === 1) return [src[m - 1]]; // single target → newest value
  const out: (number | null)[] = [];
  for (let i = 0; i < targetLen; i++) {
    const j = Math.round((i / (targetLen - 1)) * (m - 1));
    const v = src[Math.max(0, Math.min(m - 1, j))];
    out.push(typeof v === "number" && Number.isFinite(v) ? v : null);
  }
  return out;
}

/**
 * polyline "x,y x,y ..." for a series that may contain null gaps (warm-up). null
 * points are SKIPPED — the result connects only the defined points (a continuous
 * indicator line that simply starts after its warm-up). Indices align to `scale`
 * (so the series must already be resampled to scale.n). All-null / empty → "".
 */
export function linePointsSparse(values: (number | null)[], scale: ChartScale): string {
  const pts: string[] = [];
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (typeof v === "number" && Number.isFinite(v)) {
      pts.push(`${xAt(i, scale).toFixed(2)},${yAt(v, scale).toFixed(2)}`);
    }
  }
  return pts.join(" ");
}

/** True if a series has at least one finite number (else the overlay is all warm-up/empty). */
export function hasAnyValue(values: (number | null)[] | null | undefined): boolean {
  return !!values && values.some((v) => typeof v === "number" && Number.isFinite(v));
}

/**
 * Widen a scale's y-range (min/max) to include `extra` values WITHOUT changing `n`
 * (the x-axis / point count stays the price series'). Use when overlays (e.g.
 * Bollinger bands) can exceed the base series' range but must share its x-spacing.
 * Re-applies the same headroom pad. null/non-finite extras are ignored.
 */
export function extendScaleRange(scale: ChartScale, extra: (number | null)[], padPct = 0.06): ChartScale {
  const finite = extra.filter((v): v is number => typeof v === "number" && Number.isFinite(v));
  if (finite.length === 0) return scale;
  // recover the un-padded base bounds, fold in extras, re-pad
  const candidates = [scale.min, scale.max, ...finite];
  let min = Math.min(...candidates);
  let max = Math.max(...candidates);
  if (min === max) { min -= 1; max += 1; }
  const pad = (max - min) * padPct;
  return { ...scale, min: min - pad, max: max + pad };
}
