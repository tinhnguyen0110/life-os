import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const push = vi.fn();
let mockPath = "/market";
vi.mock("@/lib/useNav", () => ({
  useSafeRouter: () => ({ push }),
  useSafePathname: () => mockPath,
}));

const getHealth = vi.fn();
const getRoutines = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getHealth: () => getHealth(), getRoutines: () => getRoutines() };
});

import { TopBar } from "../TopBar";

// TopBar fires two async fetches on mount (getHealth → api-pill, getRoutines →
// routine-active-pill). Tests that assert synchronously must still let BOTH settle
// or React logs an act() warning when the state lands after the test. waitFor
// retries inside act() until the api-pill leaves its initial "checking" label —
// by then both mounted-effect promises have flushed.
async function settleTopBar() {
  await waitFor(() => expect(screen.getByTestId("api-pill")).not.toHaveTextContent("checking"));
}

describe("TopBar", () => {
  beforeEach(() => {
    push.mockClear();
    getHealth.mockReset();
    getRoutines.mockReset();
    getRoutines.mockResolvedValue({ success: true, data: { routines: [], activeCount: 3, total: 4, runsToday: 0, lastRunAt: null } });
  });

  it("routine-active pill shows the LIVE activeCount (wired to /routines)", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar route="Home" />);
    await waitFor(() => expect(screen.getByTestId("routine-active-pill")).toHaveTextContent("3 routine active"));
  });

  it("routine pill fails soft → '—', does not crash the TopBar", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    getRoutines.mockRejectedValueOnce(new Error("down"));
    render(<TopBar route="Home" />);
    await waitFor(() => expect(screen.getByTestId("routine-active-pill")).toHaveTextContent("— routine active"));
  });

  it("shows breadcrumb for the current route", async () => {
    mockPath = "/market";
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Thị trường & Cảnh báo");
    await settleTopBar();
  });

  it("API pill goes live when /health succeeds", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    await waitFor(() => expect(screen.getByTestId("api-pill")).toHaveTextContent("live"));
  });

  it("API pill goes down when /health rejects (backend not up — no crash)", async () => {
    getHealth.mockRejectedValue(new Error("ECONNREFUSED"));
    render(<TopBar />);
    await waitFor(() => expect(screen.getByTestId("api-pill")).toHaveTextContent("down"));
  });

  it("bell navigates to /market", async () => {
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    screen.getByLabelText("Cảnh báo").click();
    expect(push).toHaveBeenCalledWith("/market");
    await settleTopBar();
  });

  it("detail route falls back to the parent breadcrumb", async () => {
    mockPath = "/projects/foo";
    getHealth.mockResolvedValue({ success: true, data: { status: "ok", modules: [] } });
    render(<TopBar />);
    expect(screen.getByTestId("crumb")).toHaveTextContent("Dự án");
    await settleTopBar();
  });
});
