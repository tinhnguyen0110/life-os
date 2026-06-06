import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// Mock the named function the component calls directly (getChannelDetail), not
// the lower-level apiGet — partial-mocking apiGet doesn't intercept the internal
// call inside getChannelDetail (module-closure reference).
const getChannelDetail = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getChannelDetail: (...a: unknown[]) => getChannelDetail(...a) };
});

import PortfolioDetailPage from "../page";

// No local afterEach — the global vitest.setup.ts does cleanup() + clearAllMocks()
// after each test. Each test sets its own mockResolvedValueOnce before render, so
// the one-shot is consumed in-test; a second reset here would be redundant and was
// flagged as a potential one-shot-queue race. Rely on the global cleanup only.

// Mirrors live /finance/{channel}: alloc(+driftAlert) + priced holdings + ladder.
const CRYPTO = {
  success: true,
  data: {
    channel: "crypto",
    alloc: {
      channel: "crypto", value: 60678, pct: 96.09, target: 38, drift: 58.09, driftAlert: true,
      pnl: { cost: 40000, current: 60678, abs: 20678, pct: 51.7 },
    },
    holdings: [
      {
        holding: { channel: "crypto", symbol: "BTC", qty: 1, avgCost: 40000, source: "manual", asOf: "2026-06-06T11:19:04Z" },
        price: 60678, source: "last-known", value: 60678, pnl: { cost: 40000, current: 60678, abs: 20678, pct: 51.7 },
      },
    ],
    ladder: { channel: "crypto", referencePrice: 50000, currentPrice: 60678, rungsIn: 0, nextRung: { pct: -10, triggerPrice: 45000 }, distancePct: 25.84 },
  },
};

describe("S6 Portfolio / channel detail", () => {
  it("renders the position summary (alloc + drift render-only + pnl)", async () => {
    getChannelDetail.mockResolvedValueOnce(CRYPTO);
    render(<PortfolioDetailPage params={{ id: "crypto" }} />);
    await waitFor(() => expect(screen.getByTestId("pf-screen")).toBeInTheDocument());
    // $60,678 appears in multiple places (channel value, holding value, ladder current) — that's fine
    expect(screen.getAllByText("$60,678").length).toBeGreaterThanOrEqual(1);
    // drift shown verbatim (58.09 → "lệch +58.1 ⚠"), NOT recomputed
    expect(screen.getByText(/mục tiêu 38% · lệch \+58\.1 ⚠/)).toBeInTheDocument();
    expect(screen.getByText("+$20,678")).toBeInTheDocument();
  });

  it("renders ladder state (reference/current/next-rung + distance, render-only)", async () => {
    getChannelDetail.mockResolvedValueOnce(CRYPTO);
    render(<PortfolioDetailPage params={{ id: "crypto" }} />);
    await waitFor(() => expect(screen.getByTestId("pf-ladder")).toBeInTheDocument());
    expect(screen.getByTestId("pf-nextrung")).toHaveTextContent("$45,000");
    expect(screen.getByTestId("pf-nextrung")).toHaveTextContent("còn cách 25.8%");
  });

  it("renders the priced holdings table with P&L", async () => {
    getChannelDetail.mockResolvedValueOnce(CRYPTO);
    render(<PortfolioDetailPage params={{ id: "crypto" }} />);
    await waitFor(() => expect(screen.getByText("BTC")).toBeInTheDocument());
    expect(screen.getByText(/\+\$20,678 \(\+51\.7%\)/)).toBeInTheDocument();
  });

  it("404 unknown channel → not-found state, not crash", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getChannelDetail.mockRejectedValueOnce(new (ApiError as any)(404, "channel 'zzz' not found"));
    render(<PortfolioDetailPage params={{ id: "zzz" }} />);
    await waitFor(() => expect(screen.getByTestId("pf-notfound")).toBeInTheDocument());
  });

  it("ladder=null → 'chưa cấu hình', no crash", async () => {
    getChannelDetail.mockResolvedValueOnce({
      success: true,
      data: { ...CRYPTO.data, ladder: null },
    });
    render(<PortfolioDetailPage params={{ id: "crypto" }} />);
    await waitFor(() => expect(screen.getByText(/Chưa cấu hình ladder/)).toBeInTheDocument());
  });

  it("API error (non-404) → error state with retry", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getChannelDetail.mockRejectedValueOnce(new (ApiError as any)(0, "Network error"));
    render(<PortfolioDetailPage params={{ id: "crypto" }} />);
    await waitFor(() => expect(screen.getByTestId("pf-error")).toBeInTheDocument());
  });
});
