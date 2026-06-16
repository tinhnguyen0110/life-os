import { describe, it, expect } from "vitest";
import { confidenceBand, layerLabel, deltaText } from "@/lib/useDecision";

describe("confidenceBand — honest-confidence bucketing (render-only on the BE value)", () => {
  it("low confidence (<0.4) → 'thấp' / low tone / neg class (de-emphasize, never green go)", () => {
    expect(confidenceBand(0.2)).toEqual({ label: "thấp", tone: "low", cls: "neg" });
    expect(confidenceBand(0.0)).toEqual({ label: "thấp", tone: "low", cls: "neg" });
  });
  it("mid confidence [0.4,0.7) → 'vừa' / mid tone", () => {
    expect(confidenceBand(0.4281)).toEqual({ label: "vừa", tone: "mid", cls: "mid" });
    expect(confidenceBand(0.69)).toEqual({ label: "vừa", tone: "mid", cls: "mid" });
  });
  it("high confidence (≥0.7) → 'cao' / high tone / pos", () => {
    expect(confidenceBand(0.7)).toEqual({ label: "cao", tone: "high", cls: "pos" });
    expect(confidenceBand(1.0)).toEqual({ label: "cao", tone: "high", cls: "pos" });
  });
  it("null/NaN → low tone '—' (no fabricated confidence)", () => {
    expect(confidenceBand(null)).toEqual({ label: "—", tone: "low", cls: "faint" });
    expect(confidenceBand(undefined)).toEqual({ label: "—", tone: "low", cls: "faint" });
    expect(confidenceBand(NaN)).toEqual({ label: "—", tone: "low", cls: "faint" });
  });
});

describe("layerLabel — display alias for a layer key", () => {
  it("maps known layer keys to readable labels", () => {
    expect(layerLabel("q_cycle")).toMatch(/cycle/i);
    expect(layerLabel("q_macro")).toMatch(/macro/i);
    expect(layerLabel("q_flow")).toMatch(/flow/i);
    expect(layerLabel("s_asset")).toMatch(/asset/i);
  });
  it("unknown key → passthrough", () => {
    expect(layerLabel("q_unknown")).toBe("q_unknown");
  });
});

describe("deltaText — vsStaticGoldenPath pp formatting (render-only on BE delta)", () => {
  it("positive → +Npp / pos", () => {
    expect(deltaText(3)).toEqual({ text: "+3pp", cls: "pos" });
  });
  it("negative → −Npp (true minus) / neg", () => {
    expect(deltaText(-2)).toEqual({ text: "−2pp", cls: "neg" });
  });
  it("zero → 0pp / faint (no false signal)", () => {
    expect(deltaText(0)).toEqual({ text: "0pp", cls: "faint" });
  });
  it("null/NaN → 0pp / faint", () => {
    expect(deltaText(null)).toEqual({ text: "0pp", cls: "faint" });
    expect(deltaText(NaN)).toEqual({ text: "0pp", cls: "faint" });
  });
});
