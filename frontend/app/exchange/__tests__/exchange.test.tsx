import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";

/* Mock the api layer — OkxTab calls getExchange (+ syncExchange) via the named helpers. */
const getExchange = vi.fn();
const syncExchange = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getExchange: (...a: unknown[]) => getExchange(...a),
    syncExchange: (...a: unknown[]) => syncExchange(...a),
  };
});

import ExchangePage from "../page";

afterEach(() => { getExchange.mockReset(); syncExchange.mockReset(); });

/* LIVE-shaped fixture (curled on :8686): per-coin cost-basis on .balances[].
   PEPE has a real basis (-57.9%); USDT/ETH are basis-less (all three null → "—"). */
const OVERVIEW = (over = {}) => ({
  success: true,
  data: {
    totalUsdValue: 10644.26,
    configured: true,
    syncedAt: "2026-06-16T06:17:05Z",
    positions: [],
    balances: [
      { symbol: "USDT", available: 10416.98, frozen: 0, total: 10416.98, usdValue: 10411.14, accAvgPx: null, spotUpl: null, spotUplRatio: null },
      { symbol: "PEPE", available: 28518412, frozen: 0, total: 28518412, usdValue: 84.07, accAvgPx: 7.02e-6, spotUpl: -115.75, spotUplRatio: -0.5786 },
      { symbol: "ICP", available: 33.07, frozen: 0, total: 33.07, usdValue: 80.36, accAvgPx: 3.03, spotUpl: -19.9, spotUplRatio: -0.1989 },
    ],
    ...over,
  },
});

describe("Exchange — per-coin cost-basis P&L column (R1, render-only, null-safe)", () => {
  it("a coin WITH basis shows its spotUpl + spotUplRatio (PEPE ≈ −57.9%, negative tone)", async () => {
    getExchange.mockResolvedValueOnce(OVERVIEW());
    render(<ExchangePage />);
    await waitFor(() => expect(screen.getByTestId("balance-row-PEPE")).toBeInTheDocument());
    const cell = screen.getByTestId("balance-pnl-PEPE");
    expect(cell).toHaveTextContent("−$116"); // fmtSign(-115.75) → −$116 (rounded)
    expect(cell).toHaveTextContent("−57.9%"); // spotUplRatio -0.5786 ×100
    expect(cell.className).toContain("neg");
  });

  it("a no-basis coin (USDT) shows '—' for cost P&L — NEVER a fabricated 0/%", async () => {
    getExchange.mockResolvedValueOnce(OVERVIEW());
    render(<ExchangePage />);
    await waitFor(() => expect(screen.getByTestId("balance-row-USDT")).toBeInTheDocument());
    const cell = screen.getByTestId("balance-pnl-USDT");
    expect(cell).toHaveTextContent("—");
    // not a fabricated zero or percent
    expect(cell).not.toHaveTextContent("$0");
    expect(cell).not.toHaveTextContent("0.0%");
    expect(cell.className).toContain("faint");
  });

  it("renders the P&L column header + a value for each balance row", async () => {
    getExchange.mockResolvedValueOnce(OVERVIEW());
    render(<ExchangePage />);
    await waitFor(() => expect(screen.getByTestId("balance-row-ICP")).toBeInTheDocument());
    // header present
    expect(screen.getByText(/P&L \(giá vốn\)/i)).toBeInTheDocument();
    // ICP -19.9%
    expect(screen.getByTestId("balance-pnl-ICP")).toHaveTextContent("−19.9%");
  });

  it("the rendered % equals the backend spotUplRatio (render-only, no recompute)", async () => {
    // a divergent fixture: spotUpl and spotUplRatio are INDEPENDENT backend numbers —
    // assert we render spotUplRatio×100, not a recomputed spotUpl/usdValue.
    getExchange.mockResolvedValueOnce(OVERVIEW({
      balances: [{ symbol: "ZZZ", available: 1, frozen: 0, total: 1, usdValue: 50, accAvgPx: 100, spotUpl: -50, spotUplRatio: -0.5 }],
    }));
    render(<ExchangePage />);
    await waitFor(() => expect(screen.getByTestId("balance-pnl-ZZZ")).toBeInTheDocument());
    const cell = screen.getByTestId("balance-pnl-ZZZ");
    expect(cell).toHaveTextContent("−$50");
    expect(cell).toHaveTextContent("−50.0%"); // -0.5 ratio → -50.0%, the backend's number
  });
});
