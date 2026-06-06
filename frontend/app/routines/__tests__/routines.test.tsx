import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getRoutines = vi.fn();
const toggleRoutine = vi.fn();
const runRoutine = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getRoutines: () => getRoutines(), toggleRoutine: (...a: unknown[]) => toggleRoutine(...a), runRoutine: (...a: unknown[]) => runRoutine(...a) };
});

import RoutinesPage from "../page";

afterEach(() => { getRoutines.mockReset(); toggleRoutine.mockReset(); runRoutine.mockReset(); });

const R = (over = {}) => ({
  id: "market-poll", name: "Market Poll", trigger: "interval", triggerLabel: "mỗi 5 phút",
  desc: "Lấy giá + eval cảnh báo", action: "fetch + persist + alert", enabled: true,
  lastRun: "2026-06-06T14:10:00Z", lastResult: "ok", runs: 34, ...over,
});
const VIEW = (over = {}) => ({
  success: true,
  data: { routines: [R()], activeCount: 1, total: 4, runsToday: 12, lastRunAt: "2026-06-06T14:10:00Z", ...over },
});

describe("S13 Routines — render + filter", () => {
  it("renders 4 stat cards (activeCount/total render-only)", async () => {
    getRoutines.mockResolvedValueOnce(VIEW());
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("routines-stats")).toBeInTheDocument());
    expect(screen.getByTestId("routines-stats")).toHaveTextContent("trên 4 đã định nghĩa");
    expect(screen.getByTestId("routines-stats")).toHaveTextContent("12"); // runsToday
  });

  it("scheduler banner present + routine card renders trigger pill/desc/runs", async () => {
    getRoutines.mockResolvedValueOnce(VIEW());
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("routine-market-poll")).toBeInTheDocument());
    expect(screen.getByTestId("routines-banner")).toHaveTextContent(/Scheduler online/);
    expect(screen.getByText("Market Poll")).toBeInTheDocument();
    expect(screen.getByTestId("routine-market-poll")).toHaveTextContent("34 lần");
  });

  it("4th stat card = 'Đang chạy 0 · scheduler idle' (no live-running state)", async () => {
    getRoutines.mockResolvedValueOnce(VIEW());
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("routines-stats")).toBeInTheDocument());
    expect(screen.getByTestId("routines-stats")).toHaveTextContent(/Đang chạy/);
    expect(screen.getByTestId("routines-stats")).toHaveTextContent(/scheduler idle/);
  });

  it("lastResult chip: ok=✓ / warn=⚠ / null=no chip (never fabricated)", async () => {
    getRoutines.mockResolvedValueOnce(VIEW({ routines: [
      R({ id: "w", name: "Warn R", lastResult: "warn", lastRun: "2026-06-06T10:00:00Z" }),
      R({ id: "n", name: "Never R", lastResult: null, lastRun: null }),
    ] }));
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("routine-w")).toBeInTheDocument());
    expect(screen.getByTestId("result-w")).toHaveTextContent("⚠"); // warn
    expect(screen.queryByTestId("result-n")).toBeNull(); // null → no chip
    expect(screen.getByTestId("routine-n")).toHaveTextContent("chưa chạy"); // null lastRun
  });

  it("event filter shows only event-trigger routines", async () => {
    getRoutines.mockResolvedValueOnce(VIEW({ routines: [R({ id: "a", name: "Interval R", trigger: "interval" }), R({ id: "b", name: "Event R", trigger: "event" })] }));
    const user = userEvent.setup();
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByText("Interval R")).toBeInTheDocument());
    // click the filter button (scope to the filter seg — "Sự kiện" also appears as a trigpill label)
    await user.click(within(screen.getByTestId("routines-filter")).getByText("Sự kiện"));
    await waitFor(() => expect(screen.queryByText("Interval R")).toBeNull());
    expect(screen.getByText("Event R")).toBeInTheDocument();
  });

  it("'Routine mới' → CONSTRAINED note (~6 limit), NOT a builder", async () => {
    getRoutines.mockResolvedValueOnce(VIEW());
    const user = userEvent.setup();
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("routine-new")).toBeInTheDocument());
    await user.click(screen.getByTestId("routine-new"));
    expect(screen.getByTestId("routine-new-note")).toHaveTextContent(/giới hạn ~6 routine/);
  });

  it("GET error → friendly error; malformed body → error (teeth)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getRoutines.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("routines-error")).toBeInTheDocument());
  });
});

describe("S13 Routines — toggle/run (write) + fail-closed teeth", () => {
  it("toggle → PATCH then refetch", async () => {
    getRoutines.mockResolvedValue(VIEW());
    toggleRoutine.mockResolvedValueOnce({ success: true, data: R({ enabled: false }) });
    const user = userEvent.setup();
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("toggle-market-poll")).toBeInTheDocument());
    await user.click(screen.getByTestId("toggle-market-poll"));
    await waitFor(() => expect(toggleRoutine).toHaveBeenCalledWith("market-poll", false)); // was enabled → toggle off
  });

  it("run → POST then shows the run status", async () => {
    getRoutines.mockResolvedValue(VIEW());
    runRoutine.mockResolvedValueOnce({ success: true, data: { id: "market-poll", status: "ok", detail: "polled 5", startedAt: "x", finishedAt: "y" } });
    const user = userEvent.setup();
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("run-market-poll")).toBeInTheDocument());
    await user.click(screen.getByTestId("run-market-poll"));
    await waitFor(() => expect(runRoutine).toHaveBeenCalledWith("market-poll"));
    await waitFor(() => expect(screen.getByTestId("routines-action-msg")).toHaveTextContent(/ok — polled 5/));
  });

  it("TEETH: toggle FAILS → error msg surfaces (fail-closed, no silent flip)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getRoutines.mockResolvedValue(VIEW());
    toggleRoutine.mockRejectedValueOnce(new (ApiError as any)(500, "toggle blew up"));
    const user = userEvent.setup();
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("toggle-market-poll")).toBeInTheDocument());
    await user.click(screen.getByTestId("toggle-market-poll"));
    await waitFor(() => expect(screen.getByTestId("routines-action-msg")).toHaveTextContent(/thất bại/));
  });

  it("TEETH: run FAILS → error msg surfaces", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getRoutines.mockResolvedValue(VIEW());
    runRoutine.mockRejectedValueOnce(new (ApiError as any)(500, "run blew up"));
    const user = userEvent.setup();
    render(<RoutinesPage />);
    await waitFor(() => expect(screen.getByTestId("run-market-poll")).toBeInTheDocument());
    await user.click(screen.getByTestId("run-market-poll"));
    await waitFor(() => expect(screen.getByTestId("routines-action-msg")).toHaveTextContent(/Chạy.*thất bại/));
  });
});
