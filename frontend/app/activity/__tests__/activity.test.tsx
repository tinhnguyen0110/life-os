import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// mock the NAMED api fn the hook calls (getActivity) — partial-mock keeps ApiError real.
const getActivity = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getActivity: (...a: unknown[]) => getActivity(...a) };
});

import ActivityPage from "../page";

afterEach(() => { getActivity.mockReset(); });

const RUN = (over = {}) => ({
  id: 51, routineId: "market-poll", routineName: "Market Poll", status: "ok",
  detail: "polled: persisted=5 fired=0", startedAt: "2026-06-06T14:10:00Z",
  finishedAt: "2026-06-06T14:10:00Z", durationMs: 405, ...over,
});
const FEED = (over = {}) => ({
  success: true,
  data: {
    runs: [RUN()], count: 1, runsToday: 1, okCount: 1, warnCount: 0, errorCount: 0,
    successRate: 100, avgDurationMs: 405, byRoutine: [{ routine: "market-poll", routineName: "Market Poll", count: 1, okCount: 1, warnCount: 0, errorCount: 0, lastRun: "2026-06-06T14:10:00Z" }],
    ...over,
  },
});

describe("S14 Activity — render + stats", () => {
  it("renders 3 stat cards: run-count / success+breakdown / avg-dur", async () => {
    getActivity.mockResolvedValueOnce(FEED({ count: 52, okCount: 42, warnCount: 10, errorCount: 0, successRate: 80.8, avgDurationMs: 284 }));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-stats")).toBeInTheDocument());
    expect(screen.getByTestId("activity-stats")).toHaveTextContent("52"); // count
    expect(screen.getByTestId("activity-stats")).toHaveTextContent("80.8%"); // successRate render-only
    expect(screen.getByTestId("activity-breakdown")).toHaveTextContent("42 ok · 10 warn · 0 lỗi");
  });

  it("successRate null (count==0) → '—', NOT 0% (honest empty)", async () => {
    getActivity.mockResolvedValueOnce(FEED({ runs: [], count: 0, okCount: 0, successRate: null, avgDurationMs: null, byRoutine: [] }));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-stats")).toBeInTheDocument());
    expect(screen.getByTestId("activity-stats")).toHaveTextContent("—");
    expect(screen.getByTestId("activity-stats")).not.toHaveTextContent("0.0%");
  });

  it("feed row: status chip ✓ + routine name + detail + duration", async () => {
    getActivity.mockResolvedValueOnce(FEED());
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("feed-row-51")).toBeInTheDocument());
    const row = screen.getByTestId("feed-row-51");
    expect(row).toHaveTextContent("✓");
    expect(row).toHaveTextContent("Market Poll");
    expect(row).toHaveTextContent("polled: persisted=5 fired=0");
    expect(row).toHaveTextContent("405ms");
  });

  it("warn=⚠ / error=✗ status chips render distinctly", async () => {
    getActivity.mockResolvedValueOnce(FEED({ runs: [
      RUN({ id: 1, status: "warn", routineName: "Warn R" }),
      RUN({ id: 2, status: "error", routineName: "Err R" }),
    ] }));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("feed-row-1")).toBeInTheDocument());
    expect(screen.getByTestId("feed-row-1")).toHaveTextContent("⚠");
    expect(screen.getByTestId("feed-row-2")).toHaveTextContent("✗");
  });
});

describe("S14 Activity — cap message", () => {
  it("count > runs.length (>100 window) → 'hiển thị N gần nhất / tổng M'", async () => {
    const runs = Array.from({ length: 100 }, (_, i) => RUN({ id: i + 1 }));
    getActivity.mockResolvedValueOnce(FEED({ runs, count: 134 }));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-cap")).toBeInTheDocument());
    expect(screen.getByTestId("activity-cap")).toHaveTextContent("hiển thị 100 gần nhất / tổng 134");
  });

  it("count == runs.length (no cap) → plain 'N run', no cap message", async () => {
    getActivity.mockResolvedValueOnce(FEED({ count: 1 }));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-cap")).toBeInTheDocument());
    expect(screen.getByTestId("activity-cap")).toHaveTextContent("1 run");
    expect(screen.getByTestId("activity-cap")).not.toHaveTextContent("gần nhất");
  });
});

describe("S14 Activity — interactions", () => {
  it("click row → expands full detail (fr-out visible)", async () => {
    getActivity.mockResolvedValueOnce(FEED());
    const user = userEvent.setup();
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("feed-row-51")).toBeInTheDocument());
    expect(screen.getByTestId("feed-row-51")).toHaveAttribute("data-open", "false");
    await user.click(screen.getByTestId("feed-row-51"));
    await waitFor(() => expect(screen.getByTestId("feed-row-51")).toHaveAttribute("data-open", "true"));
    // detail panel carries the fuller log (routine id + finished + detail)
    expect(screen.getByTestId("feed-out-51")).toHaveTextContent("market-poll");
  });

  it("status filter tab → re-fetches SERVER-side with status param", async () => {
    getActivity.mockResolvedValue(FEED());
    const user = userEvent.setup();
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-tabs")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-err"));
    await waitFor(() => expect(getActivity).toHaveBeenCalledWith(expect.objectContaining({ status: "error" })));
  });

  it("range segment → re-fetches with range=week", async () => {
    getActivity.mockResolvedValue(FEED());
    const user = userEvent.setup();
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-range")).toBeInTheDocument());
    await user.click(within(screen.getByTestId("activity-range")).getByText("Tuần"));
    await waitFor(() => expect(getActivity).toHaveBeenCalledWith(expect.objectContaining({ range: "week" })));
  });
});

describe("S14 Activity — states", () => {
  it("empty runs → friendly empty message (no fake rows)", async () => {
    getActivity.mockResolvedValueOnce(FEED({ runs: [], count: 0 }));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-empty")).toBeInTheDocument());
  });

  it("GET error → friendly error + retry", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getActivity.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-error")).toBeInTheDocument());
    expect(screen.getByTestId("activity-error")).toHaveTextContent("down");
  });

  it("TEETH: malformed body (data==null) → error, NOT a blank render", async () => {
    getActivity.mockResolvedValueOnce({ success: true, data: null });
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-error")).toBeInTheDocument());
    expect(screen.getByTestId("activity-error")).toHaveTextContent("phản hồi không hợp lệ");
  });

  it("warning passthrough → banner shown", async () => {
    getActivity.mockResolvedValueOnce({ ...FEED(), warning: "run_log gần đầy" });
    render(<ActivityPage />);
    await waitFor(() => expect(screen.getByTestId("activity-warning")).toBeInTheDocument());
    expect(screen.getByTestId("activity-warning")).toHaveTextContent("run_log gần đầy");
  });
});
