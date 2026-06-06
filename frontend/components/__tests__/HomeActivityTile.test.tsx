import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("@/lib/useNav", () => ({ useSafeRouter: () => ({ push: vi.fn() }) }));

const getActivity = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getActivity: (...a: unknown[]) => getActivity(...a) };
});

import { HomeActivityTile } from "../HomeActivityTile";

afterEach(() => { getActivity.mockReset(); });

const RUN = (over = {}) => ({ id: 51, routineId: "market-poll", routineName: "Market Poll", status: "ok", detail: "polled 5", startedAt: "2026-06-06T14:10:00Z", finishedAt: "2026-06-06T14:10:00Z", durationMs: 405, ...over });
const FEED = (runs: unknown[]) => ({ success: true, data: { runs, count: runs.length, runsToday: runs.length, okCount: runs.length, warnCount: 0, errorCount: 0, successRate: 100, avgDurationMs: 405, byRoutine: [] } });

describe("HomeActivityTile — recent runs (per-tile fail-open)", () => {
  it("shows recent runs (routine name + status chip)", async () => {
    getActivity.mockResolvedValueOnce(FEED([RUN()]));
    render(<HomeActivityTile />);
    await waitFor(() => expect(screen.getByTestId("home-activity-row-51")).toBeInTheDocument());
    expect(screen.getByTestId("home-activity-row-51")).toHaveTextContent("Market Poll");
    expect(screen.getByTestId("home-activity-row-51")).toHaveTextContent("✓");
  });

  it("caps at 5 recent rows", async () => {
    const runs = Array.from({ length: 8 }, (_, i) => RUN({ id: i + 1 }));
    getActivity.mockResolvedValueOnce(FEED(runs));
    render(<HomeActivityTile />);
    await waitFor(() => expect(screen.getByTestId("home-activity-tile")).toBeInTheDocument());
    expect(screen.queryByTestId("home-activity-row-5")).toBeInTheDocument();
    expect(screen.queryByTestId("home-activity-row-6")).toBeNull(); // 6th dropped
  });

  it("empty runs → friendly empty message (no fake rows)", async () => {
    getActivity.mockResolvedValueOnce(FEED([]));
    render(<HomeActivityTile />);
    await waitFor(() => expect(screen.getByTestId("home-activity-empty")).toBeInTheDocument());
  });

  it("FAIL-OPEN: activity down → tile shows its own error (no blank, no throw)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getActivity.mockRejectedValueOnce(new (ApiError as any)(500, "boom"));
    render(<HomeActivityTile />);
    await waitFor(() => expect(screen.getByTestId("home-activity-error")).toBeInTheDocument());
    expect(screen.getByTestId("home-activity-error")).toHaveTextContent("boom");
  });
});
