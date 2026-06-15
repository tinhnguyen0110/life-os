/**
 * FE-2A — useMarketIndicators hook tests (mocks global.fetch).
 * Covers: fetches when enabled, idle when disabled / no symbol, surfaces series +
 * per-indicator warning, error state, URL carries the hours + full=true.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { useMarketIndicators } from "../useMarketIndicators";

afterEach(() => vi.restoreAllMocks());

const PAYLOAD = {
  success: true,
  data: {
    symbol: "BTC", points: 1673, asOf: "2026-06-15T02:00:00+00:00",
    indicators: {
      sma: { period: 20, latest: 65565, warning: null, series: [null, null, 60000, 65565] },
      ema: { period: 20, latest: 65541, warning: null, series: [null, 59000, 64000, 65541] },
      bollinger: { period: 20, numStd: 2, latestUpper: 66000, latestMiddle: 65000, latestLower: 64000, warning: null, upper: [null, 66000], middle: [null, 65000], lower: [null, 64000] },
    },
  },
  warning: null,
};

function mockFetch(body: unknown, { ok = true, status = 200 } = {}) {
  global.fetch = vi.fn().mockResolvedValue({ ok, status, json: async () => body } as Response) as never;
}

function Probe({ symbol, hours, enabled }: { symbol: string | null; hours: number; enabled: boolean }) {
  const { data, status, errMsg } = useMarketIndicators(symbol, hours, enabled);
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="sma-latest">{data?.indicators.sma?.latest ?? ""}</span>
      <span data-testid="bb-warn">{data?.indicators.bollinger?.warning ?? ""}</span>
      <span data-testid="err">{errMsg}</span>
    </div>
  );
}

describe("useMarketIndicators", () => {
  it("idle (no fetch) when disabled", async () => {
    const spy = vi.fn();
    global.fetch = spy as never;
    render(<Probe symbol="BTC" hours={168} enabled={false} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("idle"));
    expect(spy).not.toHaveBeenCalled();
  });

  it("idle when no symbol even if enabled", async () => {
    const spy = vi.fn();
    global.fetch = spy as never;
    render(<Probe symbol={null} hours={168} enabled={true} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("idle"));
    expect(spy).not.toHaveBeenCalled();
  });

  it("fetches + exposes indicator data when enabled", async () => {
    mockFetch(PAYLOAD);
    render(<Probe symbol="BTC" hours={168} enabled={true} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("sma-latest")).toHaveTextContent("65565");
  });

  it("surfaces a per-indicator warning (insufficient points)", async () => {
    mockFetch({
      success: true,
      data: { symbol: "BTC", points: 16, asOf: "x", indicators: { bollinger: { period: 20, numStd: 2, latestUpper: null, latestMiddle: null, latestLower: null, warning: "series (16) shorter than period (20)", upper: [], middle: [], lower: [] } } },
    });
    render(<Probe symbol="BTC" hours={2} enabled={true} />);
    await waitFor(() => expect(screen.getByTestId("bb-warn")).toHaveTextContent("shorter than period"));
  });

  it("error state on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED")) as never;
    render(<Probe symbol="BTC" hours={168} enabled={true} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"));
  });

  it("URL carries hours + full=true + the three indicators", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => PAYLOAD });
    global.fetch = spy as never;
    render(<Probe symbol="BTC" hours={720} enabled={true} />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    const url = String(spy.mock.calls[0][0]);
    expect(url).toContain("hours=720");
    expect(url).toContain("full=true");
    expect(url).toContain("indicators=sma,ema,bollinger");
  });
});
