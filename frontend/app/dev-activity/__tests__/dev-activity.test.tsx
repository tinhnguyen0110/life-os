import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #63-P3 Dev Activity screen — render + honest-empty-"you" + warnings + heatmap +
   team-context + LOC-secondary + scan. Mocks the NAMED api fns (mock-named-getter-
   not-apiget). mockResolvedValue (not ...Once) for steady-state (refetch-after-scan
   won't exhaust → no unhandled rejection per unhandled-errors-not-green). Asserts
   scoped to testids (scope-no-fabrication-asserts-to-element). */
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

import DevActivityPage from "../page";

afterEach(() => {
  getDevActivity.mockReset();
  scanDevActivity.mockReset();
});

const REPODAY = (over = {}) => ({
  date: "2026-06-21", repo: "life-os", source: "other", commits: 49, locAdded: 1500, locDeleted: 80,
  firstTs: "00:37", lastTs: "14:52", activeSpan: "14h 15m", ...over,
});
const DAY = (over = {}) => ({ date: "2026-06-21", repos: [REPODAY()], totalCommits: 0, activeRepos: 0, ...over });

const OV = (over = {}) => ({
  success: true,
  data: {
    rangeDays: 90,
    byDay: [DAY()],
    byRepo: [],
    otherRepos: [REPODAY()],
    summary: { totalCommits: 0, activeDays: 0, activeRepos: 0, locAdded: 0, locDeleted: 0, topRepos: [] },
    scannedRepos: 8,
    warnings: ["DEV_TRACING_EMAILS not set — your commits tag 'other'"],
    ...over,
  },
});

describe("#63-P3 Dev Activity — honest 'you' empty + warnings + team context", () => {
  it("EMAILS unset (totalCommits 0) → empty-state-for-you + DEV_TRACING_EMAILS hint (NOT blank/crash)", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-activity-screen")).toBeInTheDocument());
    const empty = screen.getByTestId("dev-empty-you");
    expect(empty).toHaveTextContent(/Chưa có commit nào được gán cho bạn/);
    expect(empty).toHaveTextContent("DEV_TRACING_EMAILS"); // the hint
  });

  it("renders the API warnings verbatim (honest)", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-warnings")).toBeInTheDocument());
    expect(screen.getByTestId("warn-0")).toHaveTextContent(/DEV_TRACING_EMAILS not set/);
  });

  it("STILL shows otherRepos as Team context (not hidden when 'you' is empty)", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-team-context")).toBeInTheDocument());
    const team = screen.getByTestId("dev-team-context");
    expect(team).toHaveTextContent("Team context");
    expect(team).toHaveTextContent("other"); // the tag
    expect(screen.getByTestId("other-life-os")).toHaveTextContent(/49 commit/);
  });

  it("your-byrepo empty → honest 'no repos of yours' message (no fabricated bars)", async () => {
    getDevActivity.mockResolvedValue(OV());
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-byrepo-empty")).toBeInTheDocument());
  });

  it("loading: shows a SKELETON (not a blank line) while the slow git scan runs (#71 lesson)", () => {
    getDevActivity.mockReturnValue(new Promise(() => {})); // never resolves (the cold ~20s scan)
    render(<DevActivityPage />);
    const loading = screen.getByTestId("dev-loading");
    expect(loading).toHaveAttribute("aria-busy", "true");
    // skeleton shimmer lines present (layout appears, not a blank-hang)
    expect(loading.querySelectorAll(".sk-line").length).toBeGreaterThan(0);
    expect(loading).toHaveTextContent(/Đang quét git/); // honest "first scan is slow" note
  });

  it("loading + error states", async () => {
    getDevActivity.mockRejectedValue(new Error("git blew up"));
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-error")).toHaveTextContent("git blew up"));
  });
});

describe("#63-P3 Dev Activity — populated 'you'", () => {
  const POPULATED = OV({
    byDay: [DAY({ date: "2026-06-21", totalCommits: 5, activeRepos: 1, repos: [REPODAY({ source: "you", commits: 5 })] })],
    byRepo: [{ repo: "life-os", commits: 12, locAdded: 3000, locDeleted: 200, activeDays: 4, lastActive: "2026-06-21" }],
    summary: { totalCommits: 12, activeDays: 4, activeRepos: 1, locAdded: 3000, locDeleted: 200, topRepos: [] },
    warnings: [],
  });

  it("KPI strip shows YOUR commits as the headline (primary), LOC labeled secondary/informational", async () => {
    getDevActivity.mockResolvedValue(POPULATED);
    render(<DevActivityPage />);
    await waitFor(() => expect(screen.getByTestId("dev-summary")).toBeInTheDocument());
    expect(screen.getByTestId("dev-summary")).toHaveTextContent("12"); // totalCommits headline
    // LOC is present but labeled "tham khảo" (informational), NOT a score
    expect(screen.getByTestId("dev-loc")).toHaveTextContent(/3/); // +3.0k added
    expect(screen.getByTestId("dev-summary")).toHaveTextContent(/tham khảo/);
    // when 'you' has data, the empty-state is NOT shown
    expect(screen.queryByTestId("dev-empty-you")).toBeNull();
  });

  it("heatmap: a day with commits → colored cell (accent band); 0 → empty band (distinguishing)", async () => {
    getDevActivity.mockResolvedValue(POPULATED);
    render(<DevActivityPage />);
    const grid = await screen.findByTestId("dev-heatmap-grid");
    // grid is a labeled role=img (a11y)
    expect(grid).toHaveAttribute("role", "img");
    // the last cell (index 83) = the newest day (2026-06-21, 5 commits) → accent band
    const last = screen.getByTestId("dev-hc-83");
    expect(last.getAttribute("data-count")).toBe("5");
    expect(last.getAttribute("style")).toContain("color-mix"); // colored
    // an earlier empty cell → empty band
    const empty = screen.getByTestId("dev-hc-0");
    expect(empty.getAttribute("data-count")).toBe("0");
    expect(empty.getAttribute("style")).toContain("--bg-3");
  });

  it("by-repo distribution renders YOUR repos (the primary signal)", async () => {
    getDevActivity.mockResolvedValue(POPULATED);
    render(<DevActivityPage />);
    const row = await screen.findByTestId("repo-life-os");
    expect(row).toHaveTextContent(/12 commit/);
    expect(row).toHaveTextContent(/4 ngày/);
  });
});

describe("#63-P3 Dev Activity — scan trigger", () => {
  it("scan: click → calls scanDevActivity, shows the result summary, refetches", async () => {
    getDevActivity.mockResolvedValue(OV());
    scanDevActivity.mockResolvedValue({ success: true, data: { scannedRepos: 14, days: 90, rowsUpserted: 91, yourCommits: 0, warnings: [] } });
    const user = userEvent.setup();
    render(<DevActivityPage />);
    await user.click(await screen.findByTestId("dev-scan"));
    await waitFor(() => expect(scanDevActivity).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId("scan-ok")).toHaveTextContent(/14 repo/));
  });

  it("scan error → surfaced honestly (not silent)", async () => {
    getDevActivity.mockResolvedValue(OV());
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    scanDevActivity.mockRejectedValue(new ApiError(500, "scan failed", { hint: "check git access" }));
    const user = userEvent.setup();
    render(<DevActivityPage />);
    await user.click(await screen.findByTestId("dev-scan"));
    await waitFor(() => expect(screen.getByTestId("scan-error")).toHaveTextContent(/scan failed/));
    expect(screen.getByTestId("scan-error")).toHaveTextContent(/check git access/); // hint shown
  });
});
