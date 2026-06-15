import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MarketChart } from "../MarketChart";
import type { OhlcCandle, UseMarketChart, ChartRange } from "@/lib/useMarketChart";

// Mock the hook so the component test is deterministic (no fetch). We expose a
// mutable state object the tests configure per-case.
const hookState: { current: Partial<UseMarketChart> } = { current: {} };
const setRange = vi.fn();
const reload = vi.fn();
vi.mock("@/lib/useMarketChart", async () => {
  const actual = await vi.importActual<typeof import("@/lib/useMarketChart")>("@/lib/useMarketChart");
  return {
    ...actual,
    useMarketChart: () => ({
      data: null, status: "ready", errMsg: "", warning: null, closes: [],
      range: "7d" as ChartRange, setRange, reload, ...hookState.current,
    }),
  };
});

// FE-2A: mock the indicators hook too — default returns no data (overlays absent).
const indState: { current: any } = { current: { data: null, status: "idle", errMsg: "", reload: vi.fn() } };
vi.mock("@/lib/useMarketIndicators", () => ({
  useMarketIndicators: () => indState.current,
}));

const CANDLE = (over: Partial<OhlcCandle>): OhlcCandle => ({
  ts: "2026-06-15T02:00:00+00:00", open: 100, high: 110, low: 95, close: 105, ticks: 8, ...over,
});

function withClosesData(closes: number[], extra: Partial<UseMarketChart> = {}) {
  hookState.current = {
    closes,
    data: { symbol: "BTC", interval: 60, candles: closes.map((c, i) => CANDLE({ close: c, ts: `2026-06-1${i}T02:00:00+00:00` })) },
    ...extra,
  };
}

describe("MarketChart", () => {
  beforeEach(() => {
    hookState.current = {}; setRange.mockClear(); reload.mockClear();
    indState.current = { data: null, status: "idle", errMsg: "", reload: vi.fn() };
  });
  afterEach(cleanup);

  it("no symbol → prompt to pick", () => {
    render(<MarketChart symbol={null} />);
    expect(screen.getByTestId("mchart-nosymbol")).toBeTruthy();
  });

  it("loading state", () => {
    hookState.current = { status: "loading" };
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-loading")).toBeTruthy();
  });

  it("error state shows retry", () => {
    hookState.current = { status: "error", errMsg: "down" };
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-error")).toHaveTextContent("down");
  });

  it("ready + empty closes → empty-state (no broken svg)", () => {
    hookState.current = { status: "ready", closes: [] };
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-empty")).toBeTruthy();
    expect(screen.queryByTestId("mchart-svg")).toBeNull();
  });

  it("renders the line + area path with data", () => {
    withClosesData([100, 105, 102, 108]);
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-svg")).toBeTruthy();
    expect(screen.getByTestId("mchart-line")).toBeTruthy();
    expect(screen.getByTestId("mchart-area")).toBeTruthy();
  });

  it("shows last price + delta (green when up)", () => {
    withClosesData([100, 110]); // +10%
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-last")).toHaveTextContent("110");
    const delta = screen.getByTestId("mchart-delta");
    expect(delta).toHaveTextContent("10.00%");
    expect(delta.className).toContain("pos");
  });

  it("delta is negative (red) when the series falls", () => {
    withClosesData([100, 90]); // -10%
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-delta").className).toContain("neg");
  });

  it("hover shows a tooltip with price + ts + crosshair", () => {
    withClosesData([100, 105, 102]);
    render(<MarketChart symbol="BTC" />);
    const svg = screen.getByTestId("mchart-svg");
    // jsdom getBoundingClientRect is 0×0 → px=0 → index 0 (first candle, close 100)
    fireEvent.pointerMove(svg, { clientX: 0, clientY: 10 });
    expect(screen.getByTestId("mchart-tooltip")).toBeTruthy();
    expect(screen.getByTestId("mchart-tooltip")).toHaveTextContent("100");
    expect(screen.getByTestId("mchart-crosshair")).toBeTruthy();
    // leaving clears it
    fireEvent.pointerLeave(svg);
    expect(screen.queryByTestId("mchart-tooltip")).toBeNull();
  });

  it("range toggle calls setRange and marks the active range", async () => {
    const user = userEvent.setup();
    withClosesData([100, 105], { range: "7d" });
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-range-7d").getAttribute("aria-pressed")).toBe("true");
    await user.click(screen.getByTestId("mchart-range-30d"));
    expect(setRange).toHaveBeenCalledWith("30d");
  });

  it("surfaces the honest derived-OHLC warning", () => {
    withClosesData([100, 105], { warning: "OHLC is derived from the close-tick series" });
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-warning")).toHaveTextContent("derived");
  });

  it("shows axis endpoints + point count", () => {
    withClosesData([100, 105, 102]);
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-axis-first")).toBeTruthy();
    expect(screen.getByTestId("mchart-axis-last")).toBeTruthy();
  });

  // ── FE-2A: indicator overlays ──────────────────────────────────────────────
  function withIndicators(over: any) {
    indState.current = {
      status: "ready", errMsg: "", reload: vi.fn(),
      data: {
        symbol: "BTC", points: 4, asOf: "x",
        indicators: {
          sma: { period: 20, latest: 104, warning: null, series: [null, 101, 103, 104] },
          ema: { period: 20, latest: 105, warning: null, series: [null, 102, 104, 105] },
          bollinger: { period: 20, numStd: 2, latestUpper: 110, latestMiddle: 104, latestLower: 98, warning: null, upper: [null, 108, 110, 111], middle: [null, 102, 104, 105], lower: [null, 96, 98, 99] },
          ...over,
        },
      },
    };
  }

  it("overlay toggle row renders with data (all OFF by default → no overlay drawn)", () => {
    withClosesData([100, 105, 102, 108]);
    render(<MarketChart symbol="BTC" />);
    expect(screen.getByTestId("mchart-overlays")).toBeTruthy();
    expect(screen.getByTestId("mchart-ov-sma").getAttribute("aria-pressed")).toBe("false");
    // nothing drawn while OFF
    expect(screen.queryByTestId("mchart-sma")).toBeNull();
    expect(screen.queryByTestId("mchart-ema")).toBeNull();
    expect(screen.queryByTestId("mchart-bb")).toBeNull();
  });

  it("toggling SMA on draws the SMA overlay polyline", async () => {
    const user = userEvent.setup();
    withClosesData([100, 105, 102, 108]);
    withIndicators({});
    render(<MarketChart symbol="BTC" />);
    await user.click(screen.getByTestId("mchart-ov-sma"));
    expect(screen.getByTestId("mchart-ov-sma").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("mchart-sma")).toBeTruthy();
  });

  it("toggling Bollinger on draws the three band lines", async () => {
    const user = userEvent.setup();
    withClosesData([100, 105, 102, 108]);
    withIndicators({});
    render(<MarketChart symbol="BTC" />);
    await user.click(screen.getByTestId("mchart-ov-bollinger"));
    expect(screen.getByTestId("mchart-bb")).toBeTruthy();
    expect(screen.getByTestId("mchart-bb-upper")).toBeTruthy();
    expect(screen.getByTestId("mchart-bb-lower")).toBeTruthy();
    expect(screen.getByTestId("mchart-bb-mid")).toBeTruthy();
  });

  it("DEFENSIVE: an ON overlay with insufficient points hides gracefully + hints", async () => {
    const user = userEvent.setup();
    withClosesData([100, 105, 102, 108]);
    // SMA series all-null (window too short for the period) → not drawable
    withIndicators({ sma: { period: 20, latest: null, warning: "series (4) shorter than period (20)", series: [null, null, null, null] } });
    render(<MarketChart symbol="BTC" />);
    await user.click(screen.getByTestId("mchart-ov-sma"));
    // toggle is ON but NO polyline drawn (no rubbish), and a "không đủ điểm" hint shows
    expect(screen.queryByTestId("mchart-sma")).toBeNull();
    expect(screen.getByTestId("mchart-ov-sma")).toHaveTextContent("không đủ điểm");
  });

  it("overlays absent entirely when no indicator data yet (fetch pending)", () => {
    withClosesData([100, 105, 102, 108]);
    indState.current = { data: null, status: "loading", errMsg: "", reload: vi.fn() };
    render(<MarketChart symbol="BTC" />);
    // row still renders; toggling would fetch — but nothing drawn without data
    expect(screen.getByTestId("mchart-overlays")).toBeTruthy();
    expect(screen.queryByTestId("mchart-sma")).toBeNull();
  });
});
