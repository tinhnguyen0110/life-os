import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MarketOverview } from "../MarketOverview";
import type { UseMarketOverview } from "@/lib/useMarketOverview";

// Mock the hook; expose mutable state per case. Keep the real pure helpers
// (corrCellStyle/fmtCorr) so the heatmap renders for real.
const hookState: { current: Partial<UseMarketOverview> } = { current: {} };
const reload = vi.fn();
vi.mock("@/lib/useMarketOverview", async () => {
  const actual = await vi.importActual<typeof import("@/lib/useMarketOverview")>("@/lib/useMarketOverview");
  return {
    ...actual,
    useMarketOverview: () => ({
      compare: null, compareStatus: "ready", compareErr: "", compareWarning: null,
      correlation: null, corrStatus: "ready", corrErr: "", corrWarning: null, corrNeedsMore: false,
      reload, ...hookState.current,
    }),
  };
});

const CMP = {
  window_hours: 720, asOf: "x", comparison: [
    { symbol: "BTC", changePct: 31.2, volatility: 0.86, rsi: 56.3, trend: "up" as const, points: 2143 },
    { symbol: "ETH", changePct: 10.5, volatility: 0.19, rsi: 55.4, trend: "down" as const, points: 2141 },
    { symbol: "SOL", changePct: 14.7, volatility: null, rsi: 53.3, trend: "up" as const, points: 2141 },
  ],
};
const CORR = {
  symbols: ["BTC", "ETH", "SOL"],
  matrix: {
    BTC: { BTC: 1.0, ETH: 0.76, SOL: 0.84 },
    ETH: { BTC: 0.76, ETH: 1.0, SOL: null }, // null cell → n/a
    SOL: { BTC: 0.84, ETH: null, SOL: 1.0 },
  },
  window_hours: 720, asOf: "x",
};

describe("MarketOverview", () => {
  beforeEach(() => { hookState.current = {}; reload.mockClear(); });
  afterEach(cleanup);

  it("renders the three panels", () => {
    hookState.current = { compare: CMP, correlation: CORR };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    expect(screen.getByTestId("mov-compare")).toBeTruthy();
    expect(screen.getByTestId("mov-correlation")).toBeTruthy();
    expect(screen.getByTestId("mov-relstrength")).toBeTruthy();
  });

  it("compare table renders a row per symbol", () => {
    hookState.current = { compare: CMP };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    expect(screen.getByTestId("mov-row-BTC")).toBeTruthy();
    expect(screen.getByTestId("mov-row-ETH")).toBeTruthy();
    expect(screen.getByTestId("mov-row-SOL")).toBeTruthy();
  });

  it("missing metric renders honest '—' (no NaN)", () => {
    hookState.current = { compare: CMP };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    // SOL.volatility is null → "—"
    const solRow = screen.getByTestId("mov-row-SOL");
    expect(within(solRow).getByText("—")).toBeTruthy();
  });

  it("default sort is changePct desc (BTC 31.2 first)", () => {
    hookState.current = { compare: CMP };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    const rows = screen.getAllByTestId(/^mov-row-/);
    expect(rows[0]).toHaveAttribute("data-testid", "mov-row-BTC");
  });

  it("clicking a sort header re-sorts (RSI asc → SOL 53.3 first)", async () => {
    const user = userEvent.setup();
    hookState.current = { compare: CMP };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    await user.click(screen.getByTestId("mov-sort-rsi")); // first click on a new key → rsi desc
    await user.click(screen.getByTestId("mov-sort-rsi")); // toggle to asc
    const rows = screen.getAllByTestId(/^mov-row-/);
    expect(rows[0]).toHaveAttribute("data-testid", "mov-row-SOL"); // lowest RSI first
  });

  it("correlation heatmap renders cells; null cell shows 'n/a' (not mis-tinted)", () => {
    hookState.current = { correlation: CORR };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    expect(screen.getByTestId("mov-heatmap")).toBeTruthy();
    // diagonal = 1.00
    expect(screen.getByTestId("mov-cell-BTC-BTC")).toHaveTextContent("1.00");
    // null cell (ETH↔SOL) → n/a
    const naCell = screen.getByTestId("mov-cell-ETH-SOL");
    expect(naCell).toHaveTextContent("n/a");
    expect(naCell.className).toContain("na");
  });

  it("DEFENSIVE: <2 symbols → correlation hidden with a 'cần ≥2 mã' hint (heatmap absent)", () => {
    hookState.current = { corrNeedsMore: true, corrStatus: "idle", correlation: null };
    render(<MarketOverview symbols={["BTC"]} />);
    expect(screen.getByTestId("mov-corr-needmore")).toBeTruthy();
    expect(screen.queryByTestId("mov-heatmap")).toBeNull();
  });

  it("DEFENSIVE: compare error shows retry, correlation panel unaffected", () => {
    hookState.current = { compareStatus: "error", compareErr: "down", correlation: CORR, corrStatus: "ready" };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    expect(screen.getByTestId("mov-compare-error")).toHaveTextContent("down");
    // correlation still rendered
    expect(screen.getByTestId("mov-heatmap")).toBeTruthy();
  });

  it("relative strength derives from compare (ETH/SOL vs BTC, weaker since BTC led)", () => {
    hookState.current = { compare: CMP };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    const list = screen.getByTestId("mov-rs-list");
    // ETH (10.5) and SOL (14.7) both < BTC (31.2) → weaker; BTC itself excluded
    expect(screen.getByTestId("mov-rs-ETH")).toBeTruthy();
    expect(screen.getByTestId("mov-rs-SOL")).toBeTruthy();
    expect(within(list).queryByTestId("mov-rs-BTC")).toBeNull();
    expect(screen.getByTestId("mov-rs-ETH")).toHaveTextContent("yếu hơn");
  });

  it("surfaces the compare anomaly warning", () => {
    hookState.current = { compare: CMP, compareWarning: "filtered 6 anomalous price point(s)" };
    render(<MarketOverview symbols={["BTC", "ETH", "SOL"]} />);
    expect(screen.getByTestId("mov-compare-warning")).toHaveTextContent("anomalous");
  });

  it("compare loading state", () => {
    hookState.current = { compareStatus: "loading", compare: null };
    render(<MarketOverview symbols={["BTC", "ETH"]} />);
    expect(screen.getByTestId("mov-compare-loading")).toBeTruthy();
  });
});
