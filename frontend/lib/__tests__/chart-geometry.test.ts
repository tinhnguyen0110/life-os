/**
 * FE-2 — chart-geometry pure math tests.
 * Covers buildScale (incl. flat-series band + headroom pad), xAt/yAt (incl.
 * inverted Y + single/flat guards), linePoints/areaPath (incl. empty), indexAtX
 * (nearest + clamp + empty). No DOM — deterministic.
 */
import { describe, it, expect } from "vitest";
import {
  buildScale,
  xAt,
  yAt,
  linePoints,
  areaPath,
  indexAtX,
  resampleSeries,
  linePointsSparse,
  hasAnyValue,
  extendScaleRange,
} from "@/lib/chart-geometry";

describe("buildScale", () => {
  it("empty series → safe default scale (no NaN)", () => {
    const s = buildScale([], 100, 50);
    expect(s).toEqual({ w: 100, h: 50, min: 0, max: 1, n: 0 });
  });
  it("min<max → padded band containing the data", () => {
    const s = buildScale([10, 20], 100, 50, 0);
    expect(s.min).toBe(10);
    expect(s.max).toBe(20);
    expect(s.n).toBe(2);
  });
  it("flat series → widened band so a line is drawable (min<max)", () => {
    const s = buildScale([5, 5, 5], 100, 50);
    expect(s.min).toBeLessThan(s.max);
  });
  it("applies headroom pad", () => {
    const s = buildScale([0, 100], 100, 50, 0.1);
    expect(s.min).toBeCloseTo(-10);
    expect(s.max).toBeCloseTo(110);
  });
});

describe("xAt", () => {
  const s = buildScale([1, 2, 3, 4, 5], 100, 50, 0);
  it("first point at x=0, last at x=w", () => {
    expect(xAt(0, s)).toBe(0);
    expect(xAt(4, s)).toBe(100);
  });
  it("evenly spaced", () => {
    expect(xAt(2, s)).toBeCloseTo(50);
  });
  it("single point → centered", () => {
    const one = buildScale([7], 100, 50);
    expect(xAt(0, one)).toBe(50);
  });
});

describe("yAt (inverted)", () => {
  const s = buildScale([0, 10], 100, 50, 0);
  it("max value → top (y=0), min → bottom (y=h)", () => {
    expect(yAt(10, s)).toBeCloseTo(0);
    expect(yAt(0, s)).toBeCloseTo(50);
  });
  it("higher price is higher on screen (smaller y)", () => {
    expect(yAt(8, s)).toBeLessThan(yAt(2, s));
  });
  it("flat band → vertical middle (no div-by-zero)", () => {
    const flat = { w: 100, h: 50, min: 5, max: 5, n: 2 };
    expect(yAt(5, flat)).toBe(25);
  });
});

describe("linePoints / areaPath", () => {
  const s = buildScale([1, 3, 2], 100, 60, 0);
  it("linePoints emits one coord per value", () => {
    const pts = linePoints([1, 3, 2], s).split(" ");
    expect(pts).toHaveLength(3);
  });
  it("empty series → empty string", () => {
    expect(linePoints([], s)).toBe("");
    expect(areaPath([], s)).toBe("");
  });
  it("areaPath is a closed path (starts with M, ends with Z)", () => {
    const p = areaPath([1, 3, 2], s);
    expect(p.startsWith("M")).toBe(true);
    expect(p.endsWith("Z")).toBe(true);
  });
  it("single point area closes at the centered x", () => {
    const one = buildScale([7], 100, 60);
    const p = areaPath([7], one);
    expect(p).toContain("50.00,60.00"); // baseline at center
  });
});

describe("indexAtX (hover lookup)", () => {
  const s = buildScale([1, 2, 3, 4, 5], 100, 50, 0); // x: 0,25,50,75,100
  it("snaps to the nearest index", () => {
    expect(indexAtX(0, s)).toBe(0);
    expect(indexAtX(26, s)).toBe(1);
    expect(indexAtX(51, s)).toBe(2);
    expect(indexAtX(100, s)).toBe(4);
  });
  it("clamps below 0 and above w", () => {
    expect(indexAtX(-50, s)).toBe(0);
    expect(indexAtX(9999, s)).toBe(4);
  });
  it("empty → -1, single → 0", () => {
    expect(indexAtX(10, buildScale([], 100, 50))).toBe(-1);
    expect(indexAtX(10, buildScale([9], 100, 50))).toBe(0);
  });
  it("NaN px (zero-width rect / not laid out) → first point, never NaN", () => {
    expect(indexAtX(NaN, s)).toBe(0);
  });
  it("zero-width scale → first point", () => {
    expect(indexAtX(10, { w: 0, h: 50, min: 0, max: 1, n: 5 })).toBe(0);
  });
});

// ── FE-2A: indicator-overlay helpers ─────────────────────────────────────────

describe("resampleSeries", () => {
  it("empty src / targetLen<1 → []", () => {
    expect(resampleSeries([], 5)).toEqual([]);
    expect(resampleSeries([1, 2, 3], 0)).toEqual([]);
  });
  it("targetLen 1 → newest value", () => {
    expect(resampleSeries([1, 2, 9], 1)).toEqual([9]);
  });
  it("downsamples a long series proportionally (first + last preserved)", () => {
    const src = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    const out = resampleSeries(src, 3); // i=0→0, i=1→round(0.5*9)=5, i=2→9
    expect(out).toEqual([0, 5, 9]);
  });
  it("upsamples a short series (repeats by nearest)", () => {
    const out = resampleSeries([10, 20], 4); // 0→10, .33*1→0→10, .66*1→1→20, 1→20
    expect(out).toEqual([10, 10, 20, 20]);
  });
  it("preserves null warm-up gaps", () => {
    const out = resampleSeries([null, null, 5, 6], 4);
    expect(out[0]).toBeNull();
    expect(out[out.length - 1]).toBe(6);
  });
  it("coerces non-finite to null", () => {
    const out = resampleSeries([NaN as unknown as number, 1, 2], 3);
    expect(out[0]).toBeNull();
  });
});

describe("linePointsSparse", () => {
  const sc = buildScale([1, 2, 3, 4], 100, 60, 0);
  it("skips null gaps, connects only defined points", () => {
    const pts = linePointsSparse([null, 2, null, 4], sc).split(" ").filter(Boolean);
    expect(pts).toHaveLength(2); // only indices 1 and 3
  });
  it("all-null / empty → empty string", () => {
    expect(linePointsSparse([null, null], sc)).toBe("");
    expect(linePointsSparse([], sc)).toBe("");
  });
  it("indices align to scale x positions", () => {
    const pts = linePointsSparse([1, 2, 3, 4], sc);
    expect(pts.startsWith("0.00,")).toBe(true); // first point at x=0
  });
});

describe("hasAnyValue", () => {
  it("true when at least one finite number", () => {
    expect(hasAnyValue([null, null, 5])).toBe(true);
  });
  it("false for all-null / empty / nullish", () => {
    expect(hasAnyValue([null, null])).toBe(false);
    expect(hasAnyValue([])).toBe(false);
    expect(hasAnyValue(null)).toBe(false);
    expect(hasAnyValue(undefined)).toBe(false);
  });
  it("false when only NaN/Infinity present", () => {
    expect(hasAnyValue([NaN, Infinity as unknown as number])).toBe(false);
  });
});

describe("extendScaleRange", () => {
  it("does NOT change n (x-axis stays the base point count)", () => {
    const base = buildScale([100, 105, 102], 720, 240); // n=3
    const out = extendScaleRange(base, [80, 130]);
    expect(out.n).toBe(3); // CRITICAL: overlay values must not inflate n
  });
  it("widens min/max to include extras beyond the base range", () => {
    const base = buildScale([100, 110], 720, 240, 0); // min~100, max~110
    const out = extendScaleRange(base, [80, 130], 0);
    expect(out.min).toBeLessThanOrEqual(80);
    expect(out.max).toBeGreaterThanOrEqual(130);
  });
  it("no-op when extras are all null/non-finite", () => {
    const base = buildScale([100, 110], 720, 240);
    expect(extendScaleRange(base, [null, NaN as unknown as number])).toBe(base);
  });
  it("keeps w/h unchanged", () => {
    const base = buildScale([100, 110], 720, 240);
    const out = extendScaleRange(base, [200]);
    expect(out.w).toBe(720);
    expect(out.h).toBe(240);
  });
});
