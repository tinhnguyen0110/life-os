/**
 * FE-4 — useMarketOverview hook + pure helpers (corrCellStyle / fmtCorr).
 * Covers: compare + correlation independent fetch, <2-symbol → correlation NOT
 * fired (corrNeedsMore + no 422), per-panel error isolation, heatmap color math
 * (null→grey n/a, +→green, −→red), correlation formatting.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useMarketOverview, corrCellStyle, fmtCorr } from "../useMarketOverview";

afterEach(() => vi.restoreAllMocks());

const COMPARE = {
  success: true,
  data: { window_hours: 720, asOf: "x", comparison: [
    { symbol: "BTC", changePct: 31.2, volatility: 0.86, rsi: 56.3, trend: "up", points: 2143 },
    { symbol: "ETH", changePct: 10.5, volatility: 0.19, rsi: 55.4, trend: "down", points: 2141 },
  ] },
  warning: "BTC: filtered 6 anomalous price point(s)",
};
const CORR = {
  success: true,
  data: { symbols: ["BTC", "ETH"], matrix: { BTC: { BTC: 1.0, ETH: 0.76 }, ETH: { BTC: 0.76, ETH: 1.0 } }, window_hours: 720, asOf: "x" },
  warning: null,
};

/** Route-aware fetch mock: compare vs correlation get different bodies. */
function mockRoutes(opts: { compare?: any; corr?: any; compareThrow?: boolean; corrThrow?: boolean } = {}) {
  global.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes("/market/compare")) {
      if (opts.compareThrow) return Promise.resolve({ ok: false, status: 500, json: async () => ({ detail: "boom" }) });
      return Promise.resolve({ ok: true, status: 200, json: async () => (opts.compare ?? COMPARE) });
    }
    if (url.includes("/market/correlation")) {
      if (opts.corrThrow) return Promise.resolve({ ok: false, status: 422, json: async () => ({ detail: "need ≥2 distinct symbols" }) });
      return Promise.resolve({ ok: true, status: 200, json: async () => (opts.corr ?? CORR) });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => ({ success: true, data: {} }) });
  }) as never;
}

function Probe({ symbols }: { symbols: string[] }) {
  const { compareStatus, corrStatus, corrNeedsMore, compare, correlation, compareErr } = useMarketOverview(symbols);
  return (
    <div>
      <span data-testid="cmp-status">{compareStatus}</span>
      <span data-testid="corr-status">{corrStatus}</span>
      <span data-testid="needmore">{String(corrNeedsMore)}</span>
      <span data-testid="cmp-count">{compare?.comparison.length ?? 0}</span>
      <span data-testid="corr-syms">{correlation?.symbols.join(",") ?? ""}</span>
      <span data-testid="cmp-err">{compareErr}</span>
    </div>
  );
}

describe("useMarketOverview", () => {
  it("fetches compare + correlation independently for ≥2 symbols", async () => {
    mockRoutes();
    render(<Probe symbols={["BTC", "ETH"]} />);
    await waitFor(() => expect(screen.getByTestId("cmp-status")).toHaveTextContent("ready"));
    await waitFor(() => expect(screen.getByTestId("corr-status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("cmp-count")).toHaveTextContent("2");
    expect(screen.getByTestId("corr-syms")).toHaveTextContent("BTC,ETH");
  });

  it("DEFENSIVE: <2 symbols → correlation NOT fired (corrNeedsMore, no 422)", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => COMPARE });
    global.fetch = spy as never;
    render(<Probe symbols={["BTC"]} />);
    await waitFor(() => expect(screen.getByTestId("needmore")).toHaveTextContent("true"));
    expect(screen.getByTestId("corr-status")).toHaveTextContent("idle");
    // no correlation request was made (only compare)
    const urls = spy.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/market/correlation"))).toBe(false);
  });

  it("DEFENSIVE: compare error does NOT block correlation (panel isolation)", async () => {
    mockRoutes({ compareThrow: true });
    render(<Probe symbols={["BTC", "ETH"]} />);
    await waitFor(() => expect(screen.getByTestId("cmp-status")).toHaveTextContent("error"));
    // correlation still succeeds
    await waitFor(() => expect(screen.getByTestId("corr-status")).toHaveTextContent("ready"));
  });

  it("DEFENSIVE: correlation error does NOT block compare", async () => {
    mockRoutes({ corrThrow: true });
    render(<Probe symbols={["BTC", "ETH"]} />);
    await waitFor(() => expect(screen.getByTestId("cmp-status")).toHaveTextContent("ready"));
    await waitFor(() => expect(screen.getByTestId("corr-status")).toHaveTextContent("error"));
    expect(screen.getByTestId("cmp-count")).toHaveTextContent("2");
  });

  it("de-dupes + uppercases symbols", async () => {
    mockRoutes();
    render(<Probe symbols={["btc", "BTC", "eth"]} />);
    await waitFor(() => expect(screen.getByTestId("needmore")).toHaveTextContent("false")); // btc+eth = 2 distinct
  });

  it("DEFENSIVE: a malformed compare body (no `comparison` array) coerces to [] (no crash)", async () => {
    // regression: a body shaped unexpectedly (e.g. the wrong endpoint's payload)
    // must not throw on `.comparison.length` — coerce to empty + render empty-state.
    mockRoutes({ compare: { success: true, data: { window_hours: 720, asOf: "x" /* comparison MISSING */ } } });
    render(<Probe symbols={["BTC", "ETH"]} />);
    await waitFor(() => expect(screen.getByTestId("cmp-status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("cmp-count")).toHaveTextContent("0"); // coerced to []
  });

  it("DEFENSIVE: a malformed correlation body (no `symbols`) coerces safely", async () => {
    mockRoutes({ corr: { success: true, data: { matrix: {}, window_hours: 720, asOf: "x" /* symbols MISSING */ } } });
    render(<Probe symbols={["BTC", "ETH"]} />);
    await waitFor(() => expect(screen.getByTestId("corr-status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("corr-syms")).toHaveTextContent(""); // [] → empty
  });
});

describe("corrCellStyle (heatmap color)", () => {
  it("null / non-finite → neutral grey, isNA true (never tinted)", () => {
    expect(corrCellStyle(null).isNA).toBe(true);
    expect(corrCellStyle(undefined).isNA).toBe(true);
    expect(corrCellStyle(NaN).isNA).toBe(true);
    expect(corrCellStyle(null).background).toBe("var(--bg-2)");
  });
  it("positive r → green tint, isNA false", () => {
    const s = corrCellStyle(0.8);
    expect(s.isNA).toBe(false);
    expect(s.background).toContain("52, 211, 153"); // green rgb
  });
  it("negative r → red tint", () => {
    expect(corrCellStyle(-0.5).background).toContain("248, 113, 113"); // red rgb
  });
  it("stronger |r| → higher alpha (more vivid)", () => {
    const weak = corrCellStyle(0.1).background;
    const strong = corrCellStyle(0.95).background;
    const aWeak = parseFloat(weak.match(/,\s*([\d.]+)\)/)![1]);
    const aStrong = parseFloat(strong.match(/,\s*([\d.]+)\)/)![1]);
    expect(aStrong).toBeGreaterThan(aWeak);
  });
  it("clamps out-of-range r", () => {
    expect(corrCellStyle(5).isNA).toBe(false); // treated as 1.0, still green
    expect(corrCellStyle(-9).background).toContain("248, 113, 113");
  });
});

describe("fmtCorr", () => {
  it("null → n/a", () => { expect(fmtCorr(null)).toBe("n/a"); });
  it("number → 2 decimals", () => { expect(fmtCorr(0.7639)).toBe("0.76"); });
  it("NaN → n/a", () => { expect(fmtCorr(NaN)).toBe("n/a"); });
});
