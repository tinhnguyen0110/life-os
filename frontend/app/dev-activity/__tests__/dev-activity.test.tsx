import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #123 DEVACT redesign — YOU-ONLY (no you-vs-team / no team-context), default sort =
   lastActive-desc, a GitHub-style contribution heatmap (days=365), the underline sub-nav
   is in app/projects (tested there). Kept: honest-empty-you + warnings + loading skeleton
   + error + KPI strip + sortable by-repo table + scan. Mocks the NAMED api fns
   (mock-named-getter-not-apiget). Steady-state = mockResolvedValue (unhandled-errors-not-
   green). Asserts scoped to testids. The UI moved to <DevActivityView> (#120). */
const getDevActivity = vi.fn();
const scanDevActivity = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getDevActivity: (...a: unknown[]) => getDevActivity(...a),
    scanDevActivity: (...a: unknown[]) => scanDevActivity(...a),
  };
});

import { DevActivityView as DevActivityPage } from "@/components/DevActivityView";

afterEach(() => {
  getDevActivity.mockReset();
  scanDevActivity.mockReset();
});

const REPODAY = (over = {}) => ({
  date: "2026-06-22", repo: "life-os", source: "you", commits: 5, locAdded: 1500, locDeleted: 80,
  firstTs: "00:37", lastTs: "14:52", activeSpan: "14h 15m", ...over,
});
const DAY = (over = {}) => ({ date: "2026-06-22", repos: [REPODAY()], totalCommits: 0, activeRepos: 0, ...over });

const OV = (over = {}) => ({
  success: true,
  data: {
    rangeDays: 365,
    byDay: [DAY()],
    byRepo: [],
    otherRepos: [],
    summary: { totalCommits: 0, activeDays: 0, activeRepos: 0, locAdded: 0, locDeleted: 0, topRepos: [] },
    scannedRepos: 8,
    warnings: ["DEV_TRACING_EMAILS not set — your commits tag 'other'"],
    ...over,
  },
});

describe("#123 Dev Activity — honest 'you' empty + warnings + range", () => {
  it("EMAILS unset (totalCommits 0) → empty-state-for-you + DEV_TRACING_EMAILS hint (NOT blank/crash)", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-activity-screen")).toBeInTheDocument());
    const empty = screen.getByTestId("dev-empty-you");
    expect(empty).toHaveTextContent(/Chưa có commit nào được gán cho bạn/);
    expect(empty).toHaveTextContent("DEV_TRACING_EMAILS");
  });

  it("renders the API warnings verbatim (honest)", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-warnings")).toBeInTheDocument());
    expect(screen.getByTestId("warn-0")).toHaveTextContent(/DEV_TRACING_EMAILS not set/);
  });

  it("defaults to a 1-year (days=365) load; the range filter offers 30/90/180/1-năm", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-activity-screen")).toBeInTheDocument());
    expect(getDevActivity).toHaveBeenCalledWith(365); // default = 1 year
    expect(screen.getByTestId("range-365")).toHaveTextContent("1 năm");
    expect(screen.getByTestId("range-30")).toBeInTheDocument();
    expect(screen.getByTestId("range-90")).toBeInTheDocument();
    expect(screen.getByTestId("range-180")).toBeInTheDocument();
  });

  it("loading: shows a SKELETON (not a blank line) while the slow git scan runs (#71 lesson)", () => {
    getDevActivity.mockReturnValue(new Promise(() => {}));
    render(<DevActivityPage />);
    const loading = screen.getByTestId("dev-loading");
    expect(loading).toHaveAttribute("aria-busy", "true");
    expect(loading.querySelectorAll(".sk-line").length).toBeGreaterThan(0);
    expect(loading).toHaveTextContent(/Đang quét git/);
  });

  it("error state", async () => {
    getDevActivity.mockRejectedValue(new Error("git blew up"));
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-error")).toHaveTextContent("git blew up"));
  });
});

describe("#123 Dev Activity — YOU-ONLY (no team-context, no you-vs-team)", () => {
  const POPULATED = OV({
    byDay: [DAY({ date: "2026-06-22", totalCommits: 5, activeRepos: 1, repos: [REPODAY({ source: "you", commits: 5 })] })],
    byRepo: [{ repo: "life-os", commits: 12, locAdded: 3000, locDeleted: 200, activeDays: 4, lastActive: "2026-06-22" }],
    otherRepos: [REPODAY({ repo: "team-x", source: "other", commits: 99 })],
    summary: { totalCommits: 12, activeDays: 4, activeRepos: 1, locAdded: 3000, locDeleted: 200, topRepos: [] },
    warnings: [],
  });

  it("does NOT render the team-context panel or the you-vs-team ratio (DROPPED in #123)", async () => {
    getDevActivity.mockResolvedValue(POPULATED);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-summary")).toBeInTheDocument());
    expect(screen.queryByTestId("dev-team-context")).toBeNull(); // team-context GONE
    expect(screen.queryByTestId("dev-yvo")).toBeNull();          // you-vs-team GONE
    expect(screen.queryByTestId("yvo-bar")).toBeNull();
    // and a team-only repo never appears (otherRepos not rendered)
    expect(screen.queryByTestId("repo-row-team-x")).toBeNull();
  });

  it("KPI strip shows YOUR commits headline + LOC labeled secondary (kept)", async () => {
    getDevActivity.mockResolvedValue(POPULATED);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-summary")).toBeInTheDocument());
    expect(screen.getByTestId("dev-summary")).toHaveTextContent("12"); // totalCommits
    expect(screen.getByTestId("dev-loc")).toHaveTextContent(/3/);      // +3.0k
    expect(screen.getByTestId("dev-summary")).toHaveTextContent(/tham khảo/);
  });

  it("by-repo renders ONLY your repos (kept) — sortable table", async () => {
    getDevActivity.mockResolvedValue(POPULATED);
    render(<DevActivityPage />);
    const row = await screen.findByTestId("repo-row-life-os");
    expect(row).toHaveTextContent("12");
    expect(screen.getByTestId("dev-repo-table")).toBeInTheDocument();
  });
});

describe("#123 Dev Activity — default sort = lastActive-desc (most-recent first)", () => {
  const MULTI = OV({
    byRepo: [
      { repo: "old", commits: 99, locAdded: 1, locDeleted: 1, activeDays: 9, lastActive: "2026-01-01" },
      { repo: "newest", commits: 3, locAdded: 1, locDeleted: 1, activeDays: 1, lastActive: "2026-06-20" },
      { repo: "mid", commits: 50, locAdded: 1, locDeleted: 1, activeDays: 4, lastActive: "2026-04-10" },
      { repo: "never", commits: 7, locAdded: 1, locDeleted: 1, activeDays: 1, lastActive: null },
    ],
    summary: { totalCommits: 159, activeDays: 15, activeRepos: 4, locAdded: 4, locDeleted: 4, topRepos: [] },
    warnings: [],
  });

  it("default order is most-recently-active first; null lastActive sorts LAST (honest)", async () => {
    getDevActivity.mockResolvedValue(MULTI);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-repo-table")).toBeInTheDocument());
    const rows = screen.getAllByTestId(/^repo-row-/).map((r) => r.getAttribute("data-testid"));
    expect(rows).toEqual(["repo-row-newest", "repo-row-mid", "repo-row-old", "repo-row-never"]);
    // and the sorted column is lastActive by default
    expect(screen.getByTestId("sort-lastActive")).toHaveAttribute("aria-sort", "descending");
  });

  it("clicking a column re-sorts (commits desc)", async () => {
    getDevActivity.mockResolvedValue(MULTI);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-repo-table")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("sort-commits"));
    const rows = screen.getAllByTestId(/^repo-row-/).map((r) => r.getAttribute("data-testid"));
    expect(rows).toEqual(["repo-row-old", "repo-row-mid", "repo-row-never", "repo-row-newest"]);
  });
});

describe("#123 Dev Activity — GitHub-style contribution heatmap", () => {
  const WITH_DAYS = OV({
    byDay: [
      DAY({ date: "2026-06-22", totalCommits: 29 }),
      DAY({ date: "2026-06-21", totalCommits: 4 }),
      DAY({ date: "2026-06-19", totalCommits: 12 }),
    ],
    byRepo: [{ repo: "life-os", commits: 45, locAdded: 1, locDeleted: 1, activeDays: 3, lastActive: "2026-06-22" }],
    summary: { totalCommits: 45, activeDays: 3, activeRepos: 1, locAdded: 1, locDeleted: 1, topRepos: [] },
    warnings: [],
  });

  it("renders the GitHub grid (role=img), month labels, a legend (less→more)", async () => {
    getDevActivity.mockResolvedValue(WITH_DAYS);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("gh-grid")).toBeInTheDocument());
    expect(screen.getByTestId("gh-grid")).toHaveAttribute("role", "img");
    expect(screen.getByTestId("gh-months")).toBeInTheDocument();
    expect(screen.getByTestId("gh-legend")).toBeInTheDocument();
  });

  it("a day with commits → a banded green cell with a date+count tooltip; 0 → empty band", async () => {
    getDevActivity.mockResolvedValue(WITH_DAYS);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("gh-grid")).toBeInTheDocument());
    const peak = screen.getByTestId("gh-cell-2026-06-22");
    expect(peak.getAttribute("data-count")).toBe("29");
    expect(peak.getAttribute("data-band")).toBe("4");          // max → top band
    expect(peak.getAttribute("title")).toContain("29 commit"); // per-cell tooltip
    // an empty in-range day → band 0
    const empty = screen.getByTestId("gh-cell-2026-06-20");
    expect(empty.getAttribute("data-count")).toBe("0");
    expect(empty.getAttribute("data-band")).toBe("0");
  });

  it("no byDay data → honest heatmap-empty (no crash, no fabricated cells)", async () => {
    getDevActivity.mockResolvedValue(OV({ byDay: [], byRepo: [], summary: { totalCommits: 0, activeDays: 0, activeRepos: 0, locAdded: 0, locDeleted: 0, topRepos: [] } }));
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-heatmap-empty")).toBeInTheDocument());
  });
});

describe("#123 Dev Activity — analyst (YOUR stats kept) + scan", () => {
  const POP = OV({
    byDay: [
      DAY({ date: "2026-06-22", totalCommits: 6, repos: [REPODAY({ source: "you", commits: 6, firstTs: "00:10", lastTs: "02:30" })] }),
      DAY({ date: "2026-06-21", totalCommits: 4, repos: [REPODAY({ source: "you", commits: 4, firstTs: "00:40", lastTs: "01:00" })] }),
    ],
    byRepo: [{ repo: "a", commits: 10, locAdded: 2150, locDeleted: 515, activeDays: 4, lastActive: "2026-06-22" }],
    summary: { totalCommits: 75, activeDays: 4, activeRepos: 1, locAdded: 2150, locDeleted: 515, topRepos: [] },
    warnings: [],
  });

  it("analyst row renders YOUR derived numbers (cpd, net-LOC, span, peak) — kept", async () => {
    getDevActivity.mockResolvedValue(POP);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-analyst")).toBeInTheDocument());
    expect(screen.getByTestId("stat-cpd")).toHaveTextContent("18.8");   // 75/4
    expect(screen.getByTestId("stat-netloc")).toHaveTextContent(/\+1\.6k/); // 2150-515
    expect(screen.getByTestId("stat-peak")).toHaveTextContent("00:00");
  });

  it("scan: click → calls scanDevActivity, shows result summary, refetches", async () => {
    getDevActivity.mockResolvedValue(OV());
    scanDevActivity.mockResolvedValue({ success: true, data: { scannedRepos: 14, days: 365, rowsUpserted: 91, yourCommits: 0, warnings: [] } });
    render(<DevActivityPage />);
    await userEvent.setup().click(await screen.findByTestId("dev-scan"));
    await waitFor(() => expect(scanDevActivity).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("scan-ok")).toHaveTextContent(/14 repo/));
  });

  it("scan error → surfaced honestly (not silent)", async () => {
    getDevActivity.mockResolvedValue(OV());
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    scanDevActivity.mockRejectedValue(new ApiError(500, "scan failed", { hint: "check git access" }));
    render(<DevActivityPage />);
    await userEvent.setup().click(await screen.findByTestId("dev-scan"));
    await waitFor(() => expect(screen.getByTestId("scan-error")).toHaveTextContent(/scan failed/));
    expect(screen.getByTestId("scan-error")).toHaveTextContent(/check git access/);
  });
});
