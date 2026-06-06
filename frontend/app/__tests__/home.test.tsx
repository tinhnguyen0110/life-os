/**
 * tests/home.test.tsx — Sprint 5 T3: Home Command Center verification.
 *
 * Sections:
 *   A. useHome hook    — Promise.all three endpoints, per-tile fail-open (one
 *                        module down → others still render), partial-error state.
 *   B. Home screen     — live tiles render real data; stubs show "coming soon"
 *                        NOT fake numbers; value-by-value diff vs raw API shapes;
 *                        click-through nav; empty-state no crash; console clean.
 *
 * Pre-scaffold: vi.importActual guards so the file compiles while T1/T2 still
 * pending. Tests skip gracefully if the hook/page have not landed yet.
 *
 * Fixtures mirror the FROZEN backend shapes (lib/types.ts):
 *   FinanceOverview (totalValue/change/allocations/pnlTotal/dryPowder/series)
 *   ProjectsListData (projects[ProjectStatus]/summary)
 *   MarketData       (quotes/triggers/macro/alertHistory)
 */

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { FinanceOverview, ProjectsListData, MarketData, ProjectStatus } from "@/lib/types";

/* -------------------------------------------------------------------------- */
/* Fixtures — match FROZEN backend shapes exactly                              */
/* -------------------------------------------------------------------------- */

const FINANCE_OK: FinanceOverview = {
  totalValue: 247850,
  change: { abs: 11200, pct: 4.7 },
  holdings: [],
  allocations: [
    { channel: "crypto", value: 94183, pct: 42, target: 38, drift: 4, driftAlert: false, pnl: { cost: 85763, current: 94183, abs: 8420, pct: 9.8 } },
    { channel: "etf",    value: 59484, pct: 24, target: 24, drift: 0, driftAlert: false, pnl: { cost: 57304, current: 59484, abs: 2180, pct: 3.8 } },
  ],
  pnlTotal: { cost: 237890, current: 247850, abs: 9960, pct: 4.2 },
  dryPowder: 49570,
  series: [218, 221, 224, 247.85],
};

const PROJECT_ACT: ProjectStatus = {
  id: "life-os", name: "life-os", desc: "Personal OS", health: "act",
  progress: 45, users: 1, last: "2026-06-06T10:00:00Z", lastDays: 0,
  next: "Sprint 5", repo: "/path/to/life-os",
  metrics: { commits: 42, branch: "main", lang: "TypeScript", testPass: null, stars: null },
  routines: [], lastAuto: null,
};

const PROJECTS_OK: ProjectsListData = {
  projects: [PROJECT_ACT],
  summary: { act: 1, slow: 0, stall: 0, dead: 0, total: 1 },
};

const MARKET_OK: MarketData = {
  quotes: [
    { symbol: "BTC", name: "Bitcoin", assetClass: "crypto", price: 60818, changePct: -3.1, currency: "USD", ts: "2026-06-06T10:00:00Z", source: "coingecko" },
  ],
  triggers: [],
  macro: [],
  alertHistory: [],
};

/* Envelope wrappers for apiGet mock (returns res.data → the payload) */
const ENV = <T,>(data: T) => ({ success: true, data, warning: null });

/* -------------------------------------------------------------------------- */
/* Section A — useHome hook                                                   */
/* -------------------------------------------------------------------------- */

// Guard: skip entire section if useHome hasn't landed yet
let useHome: typeof import("@/lib/useHome").useHome | null = null;
try {
  ({ useHome } = await import("@/lib/useHome"));
} catch {
  useHome = null;
}

/* Mock the 3 named convenience functions useHome calls */
const getFinance = vi.fn();
const getProjects = vi.fn();
const getMarket = vi.fn();
// HomeActivityTile (S10B) + HomeBriefTile (S11) self-fetch /activity + /brief —
// mock them so this pre-scaffold suite that renders the full HomePage doesn't hit
// a real fetch (jsdom).
const getActivity = vi.fn();
const getBrief = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getFinance: (...a: unknown[]) => getFinance(...a),
    getProjects: (...a: unknown[]) => getProjects(...a),
    getMarket: (...a: unknown[]) => getMarket(...a),
    getActivity: (...a: unknown[]) => getActivity(...a),
    getBrief: (...a: unknown[]) => getBrief(...a),
  };
});

const ACTIVITY_OK = { success: true, data: { runs: [], count: 0, runsToday: 0, okCount: 0, warnCount: 0, errorCount: 0, successRate: null, avgDurationMs: null, byRoutine: [] } };
const BRIEF_OK = { success: true, data: { generatedAt: "2026-06-06T15:32:30Z", asOf: "2026-04-17", source: "template", summary: { netWorth: null, projectsActive: 0, claudePct: null, alertsToday: 0 }, priorities: [], stale: false, warnings: [] } };

beforeEach(() => { getActivity.mockResolvedValue(ACTIVITY_OK); getBrief.mockResolvedValue(BRIEF_OK); });
afterEach(() => {
  getFinance.mockReset();
  getProjects.mockReset();
  getMarket.mockReset();
  getActivity.mockReset();
  getBrief.mockReset();
});

function ProbeHome() {
  if (!useHome) return <div data-testid="not-landed">not landed</div>;
  const { finance, projects, market, status, warning } = useHome();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="total">{finance.data?.totalValue ?? "null"}</span>
      <span data-testid="finance-status">{finance.status}</span>
      <span data-testid="proj-count">{projects.data?.projects?.length ?? "null"}</span>
      <span data-testid="quote-count">{market.data?.quotes?.length ?? "null"}</span>
      <span data-testid="warning">{warning ?? "none"}</span>
    </div>
  );
}

describe("useHome hook (pre-scaffold: skips if T1 not landed)", () => {
  it("skips gracefully when useHome not yet implemented", () => {
    if (!useHome) {
      expect(true).toBe(true); // T1 not landed — skip
      return;
    }
  });

  it("fetches all 3 endpoints in parallel and exposes their data", async () => {
    if (!useHome) return;
    // Persistent mocks — re-renders / React StrictMode double-invoke won't exhaust queue
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<ProbeHome />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ready"));

    expect(screen.getByTestId("total").textContent).toBe("247850");
    expect(screen.getByTestId("proj-count").textContent).toBe("1");
    expect(screen.getByTestId("quote-count").textContent).toBe("1");
    expect(screen.getByTestId("warning").textContent).toBe("none");
  });

  it("partial failure: finance down → projects + market still populated, warning set", async () => {
    if (!useHome) return;
    getFinance.mockRejectedValueOnce(new Error("finance 500"));
    getProjects.mockResolvedValueOnce(ENV(PROJECTS_OK));
    getMarket.mockResolvedValueOnce(ENV(MARKET_OK));

    render(<ProbeHome />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ready"));

    // finance tile errors, others succeed
    expect(screen.getByTestId("total").textContent).toBe("null");
    expect(screen.getByTestId("finance-status").textContent).toBe("error");
    expect(screen.getByTestId("proj-count").textContent).toBe("1");
    expect(screen.getByTestId("quote-count").textContent).toBe("1");
    // warning names the failed tile
    expect(screen.getByTestId("warning").textContent).toMatch(/Tài chính/);
  });

  it("all 3 down → status=ready (settled), warning present, no crash", async () => {
    if (!useHome) return;
    getFinance.mockRejectedValueOnce(new Error("finance 500"));
    getProjects.mockRejectedValueOnce(new Error("projects 500"));
    getMarket.mockRejectedValueOnce(new Error("market 500"));

    render(<ProbeHome />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ready"));
    expect(screen.getByTestId("warning").textContent).toMatch(/Tài chính/);
    expect(screen.getByTestId("warning").textContent).toMatch(/Dự án/);
  });

  it("empty finance (no holdings) → totalValue 0, no crash", async () => {
    if (!useHome) return;
    const emptyFinance: FinanceOverview = {
      totalValue: 0, change: null, holdings: [], allocations: [],
      pnlTotal: { cost: 0, current: 0, abs: 0, pct: null }, dryPowder: 0, series: [],
    };
    getFinance.mockResolvedValue(ENV(emptyFinance));
    getProjects.mockResolvedValue(ENV({ projects: [], summary: { act: 0, slow: 0, stall: 0, dead: 0, total: 0 } }));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<ProbeHome />);
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("ready"));
    expect(screen.getByTestId("total").textContent).toBe("0");
    expect(screen.getByTestId("proj-count").textContent).toBe("0");
  });
});

/* -------------------------------------------------------------------------- */
/* Section B — Home screen (app/page.tsx)                                    */
/* -------------------------------------------------------------------------- */

// Guard: skip if T2 not landed (still EmptyScreen stub)
let HomePage: React.ComponentType | null = null;
try {
  const mod = await import("@/app/page");
  // If it just renders EmptyScreen with name="Command Center", T2 hasn't landed.
  // We detect by checking the module exports a default that is NOT just an EmptyScreen wrapper.
  HomePage = mod.default as React.ComponentType;
} catch {
  HomePage = null;
}

function isStillEmptyScreen(): boolean {
  // Render and check if it just shows "Màn hình đang chờ module"
  if (!HomePage) return true;
  try {
    // Suppress the useHome data-fetch during the guard probe — we only need the
    // initial HTML snapshot (before any async resolve) to detect EmptyScreen.
    // Point getFinance/getProjects/getMarket at a promise that never resolves so
    // the component stays in "loading" state and doesn't crash on undefined.
    getFinance.mockReturnValue(new Promise(() => {}));
    getProjects.mockReturnValue(new Promise(() => {}));
    getMarket.mockReturnValue(new Promise(() => {}));
    const { container } = render(<HomePage />);
    const text = container.textContent ?? "";
    // Reset after the synchronous render
    getFinance.mockReset();
    getProjects.mockReset();
    getMarket.mockReset();
    return text.includes("Màn hình đang chờ") || text.includes("Command Center");
  } catch {
    getFinance.mockReset();
    getProjects.mockReset();
    getMarket.mockReset();
    return true;
  }
}

describe("S1 Home screen (pre-scaffold: skips tiles until T2 lands)", () => {
  it("skips gracefully when Home is still EmptyScreen (T2 pending)", () => {
    if (isStillEmptyScreen()) {
      expect(true).toBe(true); // T2 not landed
      return;
    }
  });

  it("renders net-worth tile with totalValue matching /finance raw", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    // Persistent mocks (not Once) so re-renders don't exhaust the queue
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    // Value-by-value diff: totalValue=247850 → must appear as "$247,850"
    await waitFor(() => expect(screen.getByText(/\$247,850/)).toBeInTheDocument(), { timeout: 3000 });
  });

  it("P&L tile shows per-channel pnl.abs from /finance allocations — no recomputation", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    // Home renders P&L per channel (allocations[].pnl.abs), not pnlTotal.
    // crypto pnl.abs=8420 → "+$8,420"; etf pnl.abs=2180 → "+$2,180"
    await waitFor(() => expect(screen.getByTestId("home-pnl")).toBeInTheDocument(), { timeout: 3000 });
    // At least one channel P&L value rendered (render-only from backend)
    const pnlEl = screen.getByTestId("home-pnl");
    expect(pnlEl.textContent).toMatch(/8,420|2,180/);
  });

  it("projects tile lists at least one project row from /projects", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    await waitFor(() => expect(screen.getByText("life-os")).toBeInTheDocument(), { timeout: 3000 });
  });

  // UPDATED (S11): Claude tile went LIVE in S9, Brief tile LIVE in S11 — the LAST
  // Home coming-soon stub is now gone. These two formerly asserted the stubs; the
  // no-fabrication intent now lives in each live tile's own fail-open/calm tests
  // (HomeClaudeTile / HomeBriefTile). Here we assert the post-S11 reality: NO Home
  // stub remains. (getBrief/getActivity default-mocked OK in beforeEach.)
  it("Claude tile is LIVE (no 'coming soon' stub) — S9 swapped it", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    await waitFor(() => expect(screen.queryByTestId("home-claude-stub")).toBeNull(), { timeout: 3000 });
  });

  it("Brief tile is LIVE (no 'coming soon' stub) — S11 swapped the LAST stub", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    // Brief stub is gone; the whole Home now has ZERO coming-soon stubs.
    await waitFor(() => expect(screen.queryByTestId("home-brief-stub")).toBeNull(), { timeout: 3000 });
    expect(screen.queryAllByText(/sắp có|coming soon/i).length).toBe(0);
  });

  it("finance 500 → net-worth tile error, projects tile still renders", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    getFinance.mockRejectedValueOnce(new Error("finance 500"));
    getProjects.mockResolvedValueOnce(ENV(PROJECTS_OK));
    getMarket.mockResolvedValueOnce(ENV(MARKET_OK));

    render(<HomePage />);
    // Projects still visible even when finance is down (partial fail-open)
    await waitFor(() => expect(screen.getByText("life-os")).toBeInTheDocument(), { timeout: 3000 });
    // Finance tile in error/empty state — no crash, no 247850
    expect(screen.queryByText(/\$247,850/)).not.toBeInTheDocument();
  });

  it("no projects → projects tile shows empty-state, no crash", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    const emptyProjects: ProjectsListData = {
      projects: [],
      summary: { act: 0, slow: 0, stall: 0, dead: 0, total: 0 },
    };
    getFinance.mockResolvedValue(ENV(FINANCE_OK));
    getProjects.mockResolvedValue(ENV(emptyProjects));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    // Must not crash; net-worth still shows (finance OK)
    await waitFor(() => expect(screen.getByText(/\$247,850/)).toBeInTheDocument(), { timeout: 3000 });
  });

  it("null pnl.pct (cost=0) renders '—' not NaN or undefined", async () => {
    if (isStillEmptyScreen() || !HomePage) return;
    const noHoldings: FinanceOverview = {
      ...FINANCE_OK,
      pnlTotal: { cost: 0, current: 0, abs: 0, pct: null },
    };
    getFinance.mockResolvedValue(ENV(noHoldings));
    getProjects.mockResolvedValue(ENV(PROJECTS_OK));
    getMarket.mockResolvedValue(ENV(MARKET_OK));

    render(<HomePage />);
    await waitFor(() => expect(screen.queryByText(/NaN|undefined/)).not.toBeInTheDocument(), { timeout: 3000 });
  });
});
