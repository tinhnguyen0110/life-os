/**
 * home.screen.test.tsx — frontend-owned S1 Home tests (separate from the tester's
 * pre-scaffold home.test.tsx). Mocks the NAMED source fns (getFinance/getProjects/
 * getMarket) the useHome hook calls — NOT the lower-level apiGet (module-closure
 * gotcha: a partial apiGet mock doesn't intercept the named fns' internal calls).
 */
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const getFinance = vi.fn();
const getProjects = vi.fn();
const getMarket = vi.fn();
const getClaudeUsage = vi.fn();
const getActivity = vi.fn();
const getBrief = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getFinance: () => getFinance(),
    getProjects: () => getProjects(),
    getMarket: () => getMarket(),
    getClaudeUsage: () => getClaudeUsage(),
    getActivity: (...a: unknown[]) => getActivity(...a),
    getBrief: () => getBrief(),
  };
});

import HomePage from "../page";

const USAGE = { success: true, data: { model: "claude-opus", used: 37727, cap: 200000, pct: 18.9, remaining: 162273, resetIn: null, weekly: null, pct5h: null, resetWeek: null, ctxPct: null, ctxUsed: null, ctxMax: null, ctxModel: null, quotaSource: "stub", series: [], today: 37727, avgPerDay: 1000, peak: { date: "2026-06-06", label: "T6", tokens: 5000 }, byModel: [], costUSD: 39145, byProject: [], tokenSource: "stats-cache", asOf: "2026-06-06", stale: false, source: "stats-cache" } };

const ACTIVITY = { success: true, data: { runs: [{ id: 51, routineId: "market-poll", routineName: "Market Poll", status: "ok", detail: "polled 5", startedAt: "2026-06-06T14:10:00Z", finishedAt: "2026-06-06T14:10:00Z", durationMs: 405 }], count: 1, runsToday: 1, okCount: 1, warnCount: 0, errorCount: 0, successRate: 100, avgDurationMs: 405, byRoutine: [] } };

const BRIEF = { success: true, data: { generatedAt: "2026-06-06T15:32:30Z", asOf: "2026-04-17", source: "template", summary: { netWorth: 63121, projectsActive: 3, claudePct: 18.9, alertsToday: 2 }, priorities: [{ n: 1, text: "crewly đứng 69 ngày", source: "projects", severity: "warn" }], stale: true, warnings: [] } };

afterEach(() => {
  getFinance.mockReset();
  getProjects.mockReset();
  getMarket.mockReset();
  getClaudeUsage.mockReset();
  getActivity.mockReset();
  getBrief.mockReset();
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
  // HomeActivityTile + HomeBriefTile self-fetch /activity + /brief (per-tile
  // fail-open) — default them OK so unrelated tiles never error/console-noise.
  beforeEach(() => { getActivity.mockResolvedValue(ACTIVITY); getBrief.mockResolvedValue(BRIEF); });

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

  it("ALL Home stubs are now LIVE tiles (Brief was the LAST stub — none remain)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getClaudeUsage.mockResolvedValueOnce(USAGE);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-brief-tile")).toBeInTheDocument());
    // every coming-soon stub is GONE (Brief, Activity, Claude all swapped to live tiles)
    expect(screen.queryByTestId("home-brief-stub")).toBeNull();
    expect(screen.queryByTestId("home-activity-stub")).toBeNull();
    expect(screen.queryByTestId("home-claude-stub")).toBeNull();
    expect(screen.getByTestId("home-activity-tile")).toBeInTheDocument();
  });

  it("Brief tile is now LIVE: shows top priority from /brief + 'template' (per-tile fail-open)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getBrief.mockReset();
    getBrief.mockResolvedValueOnce(BRIEF);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-brief-tile")).toHaveTextContent("crewly đứng 69 ngày"));
    expect(screen.getByTestId("home-brief-tile")).toHaveTextContent("template");
  });

  it("FAIL-OPEN: brief down → brief tile errors, rest of Home renders", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getBrief.mockReset();
    getBrief.mockRejectedValueOnce(new (ApiError as any)(500, "brief down"));
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-brief-error")).toBeInTheDocument());
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
  });

  it("Activity tile is now LIVE: shows recent run (routine name) from /activity (per-tile fail-open)", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getActivity.mockReset();
    getActivity.mockResolvedValueOnce(ACTIVITY);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-activity-tile")).toHaveTextContent("Market Poll"));
  });

  it("FAIL-OPEN: activity down → activity tile errors, rest of Home renders", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getActivity.mockReset();
    getActivity.mockRejectedValueOnce(new (ApiError as any)(500, "activity down"));
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-activity-error")).toBeInTheDocument());
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
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

  it("Claude tile shows BOTH 5h + 7d quota WITH reset countdowns when snapshot is live", async () => {
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    getClaudeUsage.mockResolvedValueOnce({
      ...USAGE,
      data: { ...USAGE.data, quotaSource: "snapshot", pct5h: 2, weekly: 6, resetIn: "2h 45m", resetWeek: "5d 20h" },
    });
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-claude-quota")).toBeInTheDocument());
    const q = screen.getByTestId("home-claude-quota");
    expect(q).toHaveTextContent("5h"); expect(q).toHaveTextContent("2%");
    expect(q).toHaveTextContent("2h 45m");   // 5h reset countdown
    expect(q).toHaveTextContent("7d"); expect(q).toHaveTextContent("6%");
    expect(q).toHaveTextContent("5d 20h");   // 7d reset countdown
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

  // #66 FE: the Home tile is the 2nd pnlTotal-pct surface — the honest −72.5% must
  // carry its scope here too, so it isn't misread as a whole-portfolio loss.
  it("home-pnl-total: pnlScope present → the −72.5% shows its scope caption (not bare)", async () => {
    const FIN_SCOPED = { success: true, data: {
      totalValue: 10645, change: { abs: 0, pct: null }, holdings: [], series: [1, 2],
      allocations: [{ channel: "crypto", value: 10645, pct: 100, target: 38, drift: 62, pnl: { cost: 850, current: 233, abs: -617, pct: -72.5 } }],
      pnlTotal: { cost: 850.55, current: 233.52, abs: -617.03, pct: -72.54 },
      pnlScope: { basis: "known-cost-only", coveragePct: 2.2, note: "P&L on the ~2.2% of the book (6 holdings) that have a cost basis; the ~98% no-basis is excluded" },
      dryPowder: 0,
    } };
    getFinance.mockResolvedValueOnce(FIN_SCOPED);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-pnl-total")).toBeInTheDocument());
    // the honest abs+pct still shown
    expect(screen.getByTestId("home-pnl-total")).toHaveTextContent("−$617");
    expect(screen.getByTestId("home-pnl-total")).toHaveTextContent("−72.5%");
    // ...with the SCOPE caption (so −72.5% can't be read as whole-portfolio) + note tooltip
    const scope = screen.getByTestId("home-pnl-scope");
    expect(scope).toHaveTextContent("~2.2% danh mục có giá vốn");
    expect(scope).toHaveAttribute("title", expect.stringContaining("cost basis"));
  });

  it("home-pnl-total: pnlScope ABSENT → null-safe (no scope caption, no crash)", async () => {
    // FIN has no pnlScope → the row renders, the caption does not.
    getFinance.mockResolvedValueOnce(FIN);
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<HomePage />);
    await waitFor(() => expect(screen.getByTestId("home-pnl-total")).toBeInTheDocument());
    expect(screen.queryByTestId("home-pnl-scope")).toBeNull();
  });
});

// #72-FE — the day-change tile must be HONEST about a flat/$0 or no-data day: a $0
// change is NEUTRAL (▬, faint), NOT a green ▲ "+$0" (which presents flat as a gain).
describe("S1 Home — day-change honesty (#72-FE)", () => {
  beforeEach(() => { getActivity.mockResolvedValue(ACTIVITY); getBrief.mockResolvedValue(BRIEF); });

  const withChange = (change: unknown) => ({ ...FIN, data: { ...FIN.data, change } });

  async function renderDelta(change: unknown) {
    getFinance.mockResolvedValueOnce(withChange(change));
    getProjects.mockResolvedValueOnce(PROJ);
    getMarket.mockResolvedValueOnce(MKT);
    render(<HomePage />);
    return screen.findByTestId("home-daychange");
  }

  it("FLAT day ($0 change) → NEUTRAL ▬ + faint (NOT green ▲, NOT '+$0')", async () => {
    const el = await renderDelta({ abs: 0, pct: null });
    expect(el).toHaveTextContent("▬");
    expect(el).toHaveTextContent("$0");
    expect(el.textContent).not.toContain("▲"); // the bug: flat shown as green up
    expect(el.textContent).not.toContain("+$0");
    expect(el.className).toContain("faint");
    expect(el.className).not.toContain("pos");
  });

  it("POSITIVE day → green ▲ + pos", async () => {
    const el = await renderDelta({ abs: 1200, pct: 1.2 });
    expect(el).toHaveTextContent("▲");
    expect(el).toHaveTextContent("+$1,200");
    expect(el.className).toContain("pos");
  });

  it("NEGATIVE day → red ▼ + neg (the distinguishing case)", async () => {
    const el = await renderDelta({ abs: -800, pct: -0.8 });
    expect(el).toHaveTextContent("▼");
    expect(el.className).toContain("neg");
    expect(el.className).not.toContain("pos");
  });

  it("NO-DATA day (change null) → ▬ + '—', honest-null (no fake arrow/number)", async () => {
    const el = await renderDelta(null);
    expect(el).toHaveTextContent("▬");
    expect(el).toHaveTextContent("—");
    expect(el.textContent).not.toContain("▲");
    expect(el.className).toContain("faint");
  });
});
