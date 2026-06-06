/**
 * home.screen.test.tsx — frontend-owned S1 Home tests (separate from the tester's
 * pre-scaffold home.test.tsx). Mocks the NAMED source fns (getFinance/getProjects/
 * getMarket) the useHome hook calls — NOT the lower-level apiGet (module-closure
 * gotcha: a partial apiGet mock doesn't intercept the named fns' internal calls).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const getFinance = vi.fn();
const getProjects = vi.fn();
const getMarket = vi.fn();
const getClaudeUsage = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getFinance: () => getFinance(),
    getProjects: () => getProjects(),
    getMarket: () => getMarket(),
    getClaudeUsage: () => getClaudeUsage(),
  };
});

import HomePage from "../page";

const USAGE = { success: true, data: { model: "claude-opus", used: 37727, cap: 200000, pct: 18.9, remaining: 162273, resetIn: null, weekly: null, series: [], today: 37727, avgPerDay: 1000, peak: { date: "2026-06-06", label: "T6", tokens: 5000 }, byModel: [], costUSD: 39145, byProject: null, asOf: "2026-06-06", stale: false, source: "stats-cache" } };

afterEach(() => {
  getFinance.mockReset();
  getProjects.mockReset();
  getMarket.mockReset();
  getClaudeUsage.mockReset();
});

const FIN = { success: true, data: {
  totalValue: 63168, change: { abs: 0, pct: null }, holdings: [], series: [1, 2, 3],
  allocations: [
    { channel: "crypto", value: 60696, pct: 96, target: 38, drift: 58, pnl: { cost: 40000, current: 60696, abs: 20696, pct: 51.7 } },
    { channel: "etf", value: 2470, pct: 4, target: 24, drift: -20, pnl: { cost: 2480, current: 2470, abs: -10, pct: -0.4 } },
  ],
  pnlTotal: { cost: 42480, current: 63168, abs: 20688, pct: 48.7 }, dryPowder: 0,
} };
const PROJ = { success: true, data: { projects: [
  { id: "p1", name: "OutboundOS", desc: null, health: "act", progress: 72, users: 3, last: null, lastDays: 1, next: "ship", repo: "/r", metrics: { commits: 10, branch: "main", lang: "TS", testPass: null, stars: null }, routines: [], lastAuto: null },
], summary: { act: 1, slow: 0, stall: 0, dead: 0, total: 1 } } };
const MKT = { success: true, data: {
  quotes: [{ symbol: "BTC", name: "Bitcoin", assetClass: "crypto", price: 60678, changePct: -3, currency: "USD", ts: "2026-06-06T12:00:00Z", source: "coingecko" }],
  triggers: [], macro: [], alertHistory: [],
} };

describe("S1 Home Command Center (frontend-owned)", () => {
  it("all tiles render when all 3 endpoints succeed", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-networth")).toBeInTheDocument());
    expect(screen.getByText("$63,168")).toBeInTheDocument();
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
    // alerts tile is the market-derived live tile (empty alertHistory → empty-state, no crash)
    expect(screen.getByTestId("home-alerts")).toBeInTheDocument();
  });

  it("Brief + Activity remain coming-soon stubs (Claude is now LIVE, not a stub)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getClaudeUsage.mockResolvedValueOnce(USAGE);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-brief-stub")).toBeInTheDocument());
    expect(screen.getByTestId("home-brief-stub")).toHaveTextContent(/Sắp có/);
    expect(screen.getByTestId("home-activity-stub")).toHaveTextContent(/Sắp có/);
    expect(screen.getByTestId("home-activity-stub")).not.toHaveTextContent(/\d/);
    // Claude stub is GONE (swapped to live tile)
    expect(screen.queryByTestId("home-claude-stub")).toBeNull();
  });

  it("Claude tile is now LIVE: shows real pct from /claude-usage (per-tile fail-open)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getClaudeUsage.mockResolvedValueOnce(USAGE);
    render(<HomePage />);
    // wait for the live pct to load (tile renders "…" first, then the gauge)
    await waitFor(() => expect(screen.getByTestId("home-claude-tile")).toHaveTextContent("18.9%"));
  });

  it("FAIL-OPEN: Claude usage down → Claude tile errors, rest of Home renders", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getClaudeUsage.mockRejectedValueOnce(new (ApiError as any)(500, "usage down"));
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-claude-error")).toBeInTheDocument());
    // rest of Home unaffected (independent fetch)
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
  });

  it("FAIL-OPEN: market down → market tile errors, finance+projects render, warning names it", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockRejectedValueOnce(new (ApiError as any)(500, "down"));
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-screen")).toBeInTheDocument());
    expect(screen.getByText("$63,168")).toBeInTheDocument();
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
    expect(screen.getByTestId("home-warning")).toHaveTextContent("Thị trường");
    expect(screen.getAllByTestId("tile-error").length).toBeGreaterThanOrEqual(1);
  });

  it("FAIL-OPEN: finance down → finance tiles error, projects+market survive", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockRejectedValueOnce(new (ApiError as any)(0, "x"));
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-warning")).toBeInTheDocument());
    expect(screen.getByTestId("home-warning")).toHaveTextContent("Tài chính");
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
  });

  // TEETH-TEST (team-lead): a fulfilled-but-malformed finance response (undefined
  // body) must render the finance tile's ERROR state + warning naming "Tài chính",
  // others survive, NO unhandled rejection. RED vs the old unguarded f.value.data;
  // GREEN after the useHome resolve() guard.
  it("finance resolves undefined (malformed 200) → finance tile error, projects survive, warning names it, no crash", async () => {
    getFinance.mockResolvedValueOnce(undefined);
    getProjects.mockResolvedValue(PROJ);
    getMarket.mockResolvedValue(MKT);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-warning")).toBeInTheDocument());
    expect(screen.getByTestId("home-warning")).toHaveTextContent("Tài chính");
    // finance tiles show the inline error; projects still rendered
    expect(screen.getAllByTestId("tile-error").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
  });

  it("renders P&L per channel from finance verbatim (render-only)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-pnl")).toBeInTheDocument());
    expect(screen.getByTestId("home-pnl")).toHaveTextContent("+$20,696");
    expect(screen.getByTestId("home-pnl")).toHaveTextContent("−$10");
  });
});
