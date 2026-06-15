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
