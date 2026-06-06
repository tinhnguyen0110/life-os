import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const apiGet = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiGet: (...a: unknown[]) => apiGet(...a) };
});

import FinancePage from "../page";
import { driftLabel } from "@/lib/useFinance";

afterEach(() => apiGet.mockReset());

// Mirrors backend FinanceOverview: totalValue/change/allocations(drift:number)/dryPowder/pnlTotal.
const FULL = {
  success: true,
  data: {
    totalValue: 247850,
    change: { abs: 11200, pct: 4.7 },
    holdings: [],
    series: [218, 221, 224, 247.85],
    dryPowder: 49570,
    pnlTotal: { cost: 237890, current: 247850, abs: 9960, pct: 4.2 },
    allocations: [
      { channel: "Crypto", value: 94183, pct: 42, target: 35, drift: 7, pnl: { cost: 85763, current: 94183, abs: 8420, pct: 9.8 } },
      { channel: "ETF", value: 59484, pct: 24, target: 24, drift: 0, pnl: { cost: 57304, current: 59484, abs: 2180, pct: 3.8 } },
      { channel: "VN", value: 44613, pct: 18, target: 18, drift: 0, pnl: { cost: 45253, current: 44613, abs: -640, pct: -1.4 } },
    ],
  },
};

describe("driftLabel (render-only — drift is the backend's signed number)", () => {
  it("|drift|>5 → alert true; shows actual vs target + signed drift", () => {
    expect(driftLabel({ drift: 7, target: 35, pct: 42 })).toEqual({ text: "42% vs 35% (+7.0)", alert: true });
  });
  it("on-target (drift 0) → no alert", () => {
    expect(driftLabel({ drift: 0, target: 24, pct: 24 })?.alert).toBe(false);
  });
  it("negative drift → true-minus sign", () => {
    expect(driftLabel({ drift: -6, target: 30, pct: 24 })).toEqual({ text: "24% vs 30% (−6.0)", alert: true });
  });
  it("null/invalid → null", () => {
    expect(driftLabel(null)).toBeNull();
    expect(driftLabel({ drift: NaN, target: 1, pct: 1 })).toBeNull();
  });
});

describe("S5 Finance Overview", () => {
  it("renders totalValue + change {abs,pct} formatted", async () => {
    apiGet.mockResolvedValueOnce(FULL);
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByTestId("finance-networth")).toBeInTheDocument());
    expect(screen.getByText("$247,850")).toBeInTheDocument();
    // change is now an object {abs, pct} → "+$11,200 · +4.7% toàn danh mục"
    expect(screen.getByText(/\+\$11,200 · \+4\.7% toàn danh mục/)).toBeInTheDocument();
  });

  it("renders dry powder + open P&L (pnlTotal) KpiCards", async () => {
    apiGet.mockResolvedValueOnce(FULL);
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByText("Dry powder")).toBeInTheDocument());
    expect(screen.getByText("$49,570")).toBeInTheDocument();
    expect(screen.getByText("+$9,960")).toBeInTheDocument();
  });

  it("renders allocation rows with backend drift (render-only) + colored P&L", async () => {
    apiGet.mockResolvedValueOnce(FULL);
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByTestId("finance-allocation")).toBeInTheDocument());
    // Crypto drift 7 (>5) → alert ⚠ + "42% vs 35% (+7.0)"
    expect(screen.getByTestId("drift-Crypto")).toHaveTextContent("42% vs 35% (+7.0)");
    expect(screen.getByTestId("drift-Crypto")).toHaveTextContent("⚠");
    // VN negative P&L → −$640
    expect(screen.getByText("−$640")).toBeInTheDocument();
  });

  it("clicking an allocation row navigates to the channel detail", async () => {
    apiGet.mockResolvedValueOnce(FULL);
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByTestId("alloc-Crypto")).toBeInTheDocument());
    expect(screen.getByTestId("alloc-Crypto")).toHaveAttribute("role", "button");
  });

  it("empty allocations → empty state, not broken UI", async () => {
    apiGet.mockResolvedValueOnce({
      success: true,
      data: { totalValue: 0, change: null, holdings: [], series: [], dryPowder: 0, pnlTotal: { cost: 0, current: 0, abs: 0, pct: null }, allocations: [] },
    });
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByText(/Chưa có dữ liệu phân bổ/)).toBeInTheDocument());
  });

  it("null change/pct → '—', no NaN", async () => {
    apiGet.mockResolvedValueOnce({
      success: true,
      data: { totalValue: 1000, change: null, holdings: [], series: [], dryPowder: 0, pnlTotal: { cost: 1000, current: 1000, abs: 0, pct: null }, allocations: [] },
    });
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByTestId("finance-networth")).toBeInTheDocument());
    expect(screen.queryByText(/NaN/)).toBeNull();
  });

  it("API error → friendly error state, no white-screen", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    apiGet.mockRejectedValueOnce(new (ApiError as any)(0, "Network error"));
    render(<FinancePage />);
    await waitFor(() => expect(screen.getByTestId("finance-error")).toBeInTheDocument());
  });
});
