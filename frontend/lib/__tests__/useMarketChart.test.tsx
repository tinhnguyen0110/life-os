/**
 * FE-2 — useMarketChart hook tests (mocks global.fetch like useMarket.test).
 * Covers: loads OHLC for a symbol, exposes closes oldest→newest, surfaces the
 * honest warning, null symbol = no fetch, error state, range param drives the URL.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { useMarketChart, RANGE_PARAMS, type OhlcCandle } from "../useMarketChart";

afterEach(() => vi.restoreAllMocks());

const CANDLE = (over: Partial<OhlcCandle>): OhlcCandle => ({
  ts: "2026-06-15T02:00:00+00:00", open: 100, high: 110, low: 95, close: 105, ticks: 8, ...over,
});

function mockFetch(body: unknown, { ok = true, status = 200 } = {}) {
  global.fetch = vi.fn().mockResolvedValue({ ok, status, json: async () => body } as Response) as never;
}

function Probe({ symbol }: { symbol: string | null }) {
  const { status, closes, warning, errMsg, data, range, setRange } = useMarketChart(symbol);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="closes">{closes.join(",")}</span>
      <span data-testid="warning">{warning ?? ""}</span>
      <span data-testid="err">{errMsg}</span>
      <span data-testid="interval">{data?.interval ?? ""}</span>
      <span data-testid="range">{range}</span>
      <button data-testid="to-30d" onClick={() => setRange("30d")}>30d</button>
    </div>
  );
}

describe("useMarketChart", () => {
  it("loads OHLC and exposes closes oldest→newest", async () => {
    mockFetch({
      success: true,
      data: { symbol: "BTC", interval: 60, candles: [CANDLE({ close: 100 }), CANDLE({ close: 102 }), CANDLE({ close: 99 })] },
      warning: "OHLC is derived from the close-tick series",
    });
    render(<Probe symbol="BTC" />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("closes")).toHaveTextContent("100,102,99");
    expect(screen.getByTestId("interval")).toHaveTextContent("60");
  });

  it("surfaces the honest derived-OHLC warning", async () => {
    mockFetch({ success: true, data: { symbol: "BTC", interval: 60, candles: [CANDLE({})] }, warning: "not exchange candles" });
    render(<Probe symbol="BTC" />);
    await waitFor(() => expect(screen.getByTestId("warning")).toHaveTextContent("not exchange candles"));
  });

  it("null symbol → ready with no fetch (no chart yet)", async () => {
    const spy = vi.fn();
    global.fetch = spy as never;
    render(<Probe symbol={null} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("closes")).toHaveTextContent("");
    expect(spy).not.toHaveBeenCalled();
  });

  it("empty candle series is a valid ready state (no NaN, empty closes)", async () => {
    mockFetch({ success: true, data: { symbol: "BTC", interval: 60, candles: [] }, warning: null });
    render(<Probe symbol="BTC" />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("closes")).toHaveTextContent("");
  });

  it("error state on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED")) as never;
    render(<Probe symbol="BTC" />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"));
    expect(screen.getByTestId("err").textContent).toMatch(/Network error|ECONNREFUSED/);
  });

  it("changing range refetches with the new hours/interval in the URL", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ success: true, data: { symbol: "BTC", interval: 240, candles: [CANDLE({})] } }) });
    global.fetch = spy as never;
    render(<Probe symbol="BTC" />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    await act(async () => { screen.getByTestId("to-30d").click(); });
    await waitFor(() => expect(screen.getByTestId("range")).toHaveTextContent("30d"));
    const urls = spy.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes(`hours=${RANGE_PARAMS["30d"].hours}`) && u.includes(`interval=${RANGE_PARAMS["30d"].interval}`))).toBe(true);
  });
});
