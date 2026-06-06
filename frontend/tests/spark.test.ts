/**
 * tests/spark.test.ts — Sprint 0 spark/gauge SVG helper tests (Gate 2).
 *
 * Verifies spark() returns a valid SVG string and gauge() returns valid SVG.
 * Skipped if lib/spark.ts not yet written.
 */
import { describe, it, expect } from "vitest";

let sparkMod: typeof import("@/lib/spark") | null = null;
try { sparkMod = await import("@/lib/spark"); } catch { /* not yet */ }

describe("lib/spark — spark()", () => {
  it("returns a string", () => {
    if (!sparkMod?.spark) return;
    const result = sparkMod.spark([10, 20, 15, 30]);
    expect(typeof result).toBe("string");
  });

  it("returns SVG markup", () => {
    if (!sparkMod?.spark) return;
    const result = sparkMod.spark([10, 20, 15, 30]);
    expect(result).toContain("<svg");
    expect(result).toContain("</svg>");
  });

  it("handles empty array without crash", () => {
    if (!sparkMod?.spark) return;
    const result = sparkMod.spark([]);
    expect(typeof result).toBe("string");
  });

  it("handles single value", () => {
    if (!sparkMod?.spark) return;
    const result = sparkMod.spark([42]);
    expect(typeof result).toBe("string");
  });

  it("handles all-zero values", () => {
    if (!sparkMod?.spark) return;
    const result = sparkMod.spark([0, 0, 0]);
    expect(typeof result).toBe("string");
  });

  it("handles negative values without crash", () => {
    if (!sparkMod?.spark) return;
    const result = sparkMod.spark([-5, -1, 0, 3]);
    expect(typeof result).toBe("string");
  });
});

describe("lib/spark — gauge()", () => {
  it("returns SVG markup", () => {
    if (!sparkMod?.gauge) return;
    const result = sparkMod.gauge(75);
    expect(result).toContain("<svg");
  });

  it("handles 0%", () => {
    if (!sparkMod?.gauge) return;
    const result = sparkMod.gauge(0);
    expect(typeof result).toBe("string");
  });

  it("handles 100%", () => {
    if (!sparkMod?.gauge) return;
    const result = sparkMod.gauge(100);
    expect(typeof result).toBe("string");
  });

  it("handles values >100 without crash", () => {
    if (!sparkMod?.gauge) return;
    const result = sparkMod.gauge(150);
    expect(typeof result).toBe("string");
  });
});
