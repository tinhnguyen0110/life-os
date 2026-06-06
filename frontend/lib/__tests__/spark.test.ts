import { describe, it, expect } from "vitest";
import { spark, gauge, donut } from "../spark";

describe("spark()", () => {
  it("emits an svg with a polyline of the right point count", () => {
    const svg = spark([1, 2, 3, 4], "#FF6A33");
    expect(svg).toContain("<svg");
    expect(svg).toContain("<polyline");
    // 4 points → 4 "x,y" pairs in the polyline points attr
    const pts = svg.match(/points="([^"]+)"/)?.[1].trim().split(" ");
    expect(pts).toHaveLength(4);
  });

  it("includes a gradient fill when fill=true, omits when false", () => {
    expect(spark([1, 2], "#fff", 100, 40, true)).toContain("linearGradient");
    expect(spark([1, 2], "#fff", 100, 40, false)).not.toContain("linearGradient");
  });

  it("produces unique gradient ids across calls (SSR-safe, deterministic)", () => {
    const a = spark([1, 2], "#fff");
    const b = spark([1, 2], "#fff");
    const idA = a.match(/id="(sg[^"]+)"/)?.[1];
    const idB = b.match(/id="(sg[^"]+)"/)?.[1];
    expect(idA).toBeTruthy();
    expect(idA).not.toBe(idB);
  });
});

describe("gauge()", () => {
  it("emits two circles (track + value arc)", () => {
    const svg = gauge(71, "#34E08A");
    expect((svg.match(/<circle/g) || []).length).toBe(2);
  });

  it("0% leaves the full circumference as dashoffset, 100% leaves ~0", () => {
    const zero = gauge(0, "#fff");
    const full = gauge(100, "#fff");
    const offZero = Number(zero.match(/stroke-dashoffset="([\d.]+)"/)?.[1]);
    const offFull = Number(full.match(/stroke-dashoffset="([\d.]+)"/)?.[1]);
    expect(offZero).toBeGreaterThan(offFull);
    expect(offFull).toBeCloseTo(0, 5);
  });
});

describe("donut()", () => {
  it("emits one ring circle per non-zero segment + the center hole", () => {
    const svg = donut([{ pct: 60, color: "#FF6A33" }, { pct: 40, color: "#4DA6FF" }]);
    // 2 segment rings + 1 hole circle = 3
    expect((svg.match(/<circle/g) || []).length).toBe(3);
    expect(svg).toContain("#FF6A33");
    expect(svg).toContain("#4DA6FF");
  });

  it("drops zero/negative-pct segments (no NaN, no dead ring)", () => {
    const svg = donut([{ pct: 100, color: "#fff" }, { pct: 0, color: "#000" }]);
    // 1 ring (the 0 dropped) + hole = 2
    expect((svg.match(/<circle/g) || []).length).toBe(2);
    expect(svg).not.toContain("NaN");
  });

  it("empty segments → just the hole circle (valid empty ring)", () => {
    const svg = donut([]);
    expect((svg.match(/<circle/g) || []).length).toBe(1);
    expect(svg).toContain("<svg");
  });
});
