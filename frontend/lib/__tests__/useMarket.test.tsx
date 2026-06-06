import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { quoteToTicker, useMarket } from "../useMarket";
import { TICKER_MOCK } from "../ticker-mock";
import type { AssetQuote } from "../types";

afterEach(() => vi.restoreAllMocks());

const Q = (over: Partial<AssetQuote>): AssetQuote => ({
  symbol: "BTC",
  name: "Bitcoin",
  assetClass: "crypto",
  price: 68240,
  changePct: 3.1,
  currency: "USD",
  ts: "2026-06-06T12:00:00Z",
  source: "coingecko",
  ...over,
});

describe("quoteToTicker (pure mapper, render-only formatting)", () => {
  it("formats price with thousands + signed % + pos dir for a gainer", () => {
    expect(quoteToTicker(Q({}))).toEqual({ sym: "BTC", px: "68,240", chg: "+3.1%", dir: "pos" });
  });

  it("negative changePct → neg dir", () => {
    const t = quoteToTicker(Q({ symbol: "VNINDEX", price: 1284, changePct: -0.6 }));
    expect(t.dir).toBe("neg");
    expect(t.chg).toBe("-0.6%");
  });

  it("null changePct → em-dash %, dir defaults pos, price still shown", () => {
    const t = quoteToTicker(Q({ changePct: null }));
    expect(t.chg).toBe("—");
    expect(t.dir).toBe("pos");
    expect(t.px).toBe("68,240");
  });
});

function Probe() {
  const { status, tickerItems, data } = useMarket();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="ticker-count">{tickerItems.length}</span>
      <span data-testid="quote-count">{data.quotes?.length ?? 0}</span>
      <span data-testid="first-sym">{tickerItems[0]?.sym}</span>
    </div>
  );
}

function mockFetchOnce(body: unknown, { ok = true, status = 200 } = {}) {
  global.fetch = vi.fn().mockResolvedValueOnce({
    ok,
    status,
    json: async () => body,
  } as Response) as unknown as typeof fetch;
}

describe("useMarket hook", () => {
  it("maps live quotes into ticker items when /market succeeds", async () => {
    mockFetchOnce({
      success: true,
      data: { quotes: [Q({}), Q({ symbol: "ETH", price: 3820, changePct: 5.2 })], triggers: [], macro: [], alertHistory: [] },
    });
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("quote-count")).toHaveTextContent("2");
    expect(screen.getByTestId("ticker-count")).toHaveTextContent("2");
    expect(screen.getByTestId("first-sym")).toHaveTextContent("BTC");
  });

  it("falls back to TICKER_MOCK on fetch error (tape never blanks)", async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(new Error("ECONNREFUSED")) as never;
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"));
    expect(screen.getByTestId("ticker-count")).toHaveTextContent(String(TICKER_MOCK.length));
  });

  it("falls back to mock when live quotes are empty", async () => {
    mockFetchOnce({ success: true, data: { quotes: [], triggers: [], macro: [], alertHistory: [] } });
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("ticker-count")).toHaveTextContent(String(TICKER_MOCK.length));
  });
});
