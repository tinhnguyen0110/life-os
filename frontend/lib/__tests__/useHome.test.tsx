import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// Mock the named source fns the hook calls (not apiGet — module-closure gotcha).
const getFinance = vi.fn();
const getProjects = vi.fn();
const getMarket = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getFinance: () => getFinance(),
    getProjects: () => getProjects(),
    getMarket: () => getMarket(),
  };
});

import { useHome } from "../useHome";

afterEach(() => {
  getFinance.mockReset();
  getProjects.mockReset();
  getMarket.mockReset();
});

const FIN = { success: true, data: { totalValue: 1000, change: null, holdings: [], allocations: [], pnlTotal: { cost: 0, current: 0, abs: 0, pct: null }, dryPowder: 0, series: [] } };
const PROJ = { success: true, data: { projects: [], summary: { act: 1, slow: 0, stall: 0, dead: 0, total: 1 } } };
const MKT = { success: true, data: { quotes: [{ symbol: "BTC", name: "Bitcoin", assetClass: "crypto", price: 60000, changePct: 1, currency: "USD", ts: "2026-06-06T12:00:00Z", source: "coingecko" }], triggers: [], macro: [], alertHistory: [] } };

function Probe() {
  const h = useHome();
  return (
    <div>
      <span data-testid="status">{h.status}</span>
      <span data-testid="warning">{h.warning ?? ""}</span>
      <span data-testid="fin">{h.finance.status}</span>
      <span data-testid="proj">{h.projects.status}</span>
      <span data-testid="mkt">{h.market.status}</span>
      <span data-testid="fin-total">{h.finance.data?.totalValue ?? "-"}</span>
    </div>
  );
}

describe("useHome — per-tile fail-open aggregator", () => {
  it("all 3 succeed → ready, no warning, each tile ready", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("warning")).toHaveTextContent("");
    expect(screen.getByTestId("fin")).toHaveTextContent("ready");
    expect(screen.getByTestId("proj")).toHaveTextContent("ready");
    expect(screen.getByTestId("mkt")).toHaveTextContent("ready");
    expect(screen.getByTestId("fin-total")).toHaveTextContent("1000");
  });

  it("FAIL-OPEN: market down → market tile errors, finance+projects still ready, warning names market", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockRejectedValueOnce(new (ApiError as any)(500, "boom"));
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    // overall still reaches ready — one tile down doesn't blank the screen
    expect(screen.getByTestId("fin")).toHaveTextContent("ready");
    expect(screen.getByTestId("proj")).toHaveTextContent("ready");
    expect(screen.getByTestId("mkt")).toHaveTextContent("error");
    expect(screen.getByTestId("warning")).toHaveTextContent("Thị trường");
    // the surviving tiles still carry their data
    expect(screen.getByTestId("fin-total")).toHaveTextContent("1000");
  });

  it("FAIL-OPEN: all 3 down → ready (not stuck loading), warning names all three", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockRejectedValueOnce(new (ApiError as any)(0, "x"));
    getProjects.mockRejectedValueOnce(new (ApiError as any)(0, "x"));
    getMarket.mockRejectedValueOnce(new (ApiError as any)(0, "x"));
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("fin")).toHaveTextContent("error");
    const w = screen.getByTestId("warning").textContent ?? "";
    expect(w).toContain("Tài chính");
    expect(w).toContain("Dự án");
    expect(w).toContain("Thị trường");
  });

  // TEETH-TEST: a fulfilled-but-malformed response (resolves undefined / no .data)
  // must degrade to that tile's ERROR state — NOT throw an unhandled rejection.
  // RED against the unguarded `f.value.data`; GREEN after the resolve() guard.
  it("fulfilled-but-undefined response → tile errors (no crash, truly fail-open)", async () => {
    getFinance.mockResolvedValueOnce(undefined); // 200-ish but body is undefined
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("fin")).toHaveTextContent("error");
    expect(screen.getByTestId("proj")).toHaveTextContent("ready"); // others survive
    expect(screen.getByTestId("warning")).toHaveTextContent("Tài chính");
  });

  it("fulfilled response with NO .data field → tile errors (malformed 200 body)", async () => {
    getFinance.mockResolvedValueOnce({ success: true }); // success but no data
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("fin")).toHaveTextContent("error");
    expect(screen.getByTestId("proj")).toHaveTextContent("ready");
  });

  it("one slow endpoint doesn't block the others reaching ready (allSettled)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    // market resolves later but still settles
    getMarket.mockImplementationOnce(() => new Promise((r) => setTimeout(() => r(MKT), 10)));
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("mkt")).toHaveTextContent("ready");
  });
});
