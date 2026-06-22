import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getGraveyard = vi.fn();
const restoreProject = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getGraveyard: () => getGraveyard(), restoreProject: (...a: unknown[]) => restoreProject(...a) };
});

// #114 — the graveyard UI moved from the page (now a redirect) into <GraveyardView>,
// rendered in the /projects "Nghĩa địa" sub-tab. The S4 behavior tests follow it here.
import { GraveyardView as GraveyardPage } from "@/components/GraveyardView";

afterEach(() => {
  getGraveyard.mockReset();
  restoreProject.mockReset();
});

const GRAVE = (over = {}) => ({
  id: "p1", name: "OldProj", peak: 68, reason: "pivot", lesson: "Ship ở 70%, đừng đợi 90%.",
  died: "2026-04-11T10:00:00Z", users: 0, health: "dead", repo: "/r", ...over,
});
const STATS = (over = {}) => ({
  success: true,
  data: {
    graves: [GRAVE()], count: 1, avgPeak: 68, commonReasons: [{ reason: "pivot", count: 1 }],
    reachedUser: 0, beforeUser: 1, lessons: ["Ship ở 70%, đừng đợi 90%."], ...over,
  },
});

describe("S4 Graveyard — render", () => {
  it("renders pattern summary (avgPeak + reached/before) render-only", async () => {
    getGraveyard.mockResolvedValueOnce(STATS());
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-pattern")).toBeInTheDocument());
    expect(screen.getByTestId("graveyard-avgpeak")).toHaveTextContent("68%");
    expect(screen.getByTestId("graveyard-pattern")).toHaveTextContent(/1 bỏ trước khi có user/);
    expect(screen.getByTestId("graveyard-pattern")).toHaveTextContent(/pivot \(1\)/);
  });

  it("pattern copy: avgPeak=0 → softened 'chưa ghi mức hoàn thành' (not awkward '0% hoàn thành')", async () => {
    getGraveyard.mockResolvedValueOnce(STATS({ avgPeak: 0, graves: [GRAVE({ peak: 0 })] }));
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-pattern-text")).toBeInTheDocument());
    expect(screen.getByTestId("graveyard-pattern-text")).toHaveTextContent(/chưa ghi mức hoàn thành/);
    expect(screen.getByTestId("graveyard-pattern-text")).not.toHaveTextContent(/bỏ dự án ở mức 0% hoàn thành/);
  });

  it("pattern copy: avgPeak>0 → normal 'bỏ ở mức X% hoàn thành' sentence", async () => {
    getGraveyard.mockResolvedValueOnce(STATS({ avgPeak: 68 }));
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-pattern-text")).toBeInTheDocument());
    expect(screen.getByTestId("graveyard-pattern-text")).toHaveTextContent(/bỏ dự án ở mức 68% hoàn thành/);
  });

  it("renders grave cards (name/peak/reason/lesson/died) + restore button", async () => {
    getGraveyard.mockResolvedValueOnce(STATS());
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("grave-p1")).toBeInTheDocument());
    expect(screen.getByText("OldProj")).toBeInTheDocument();
    expect(screen.getByTestId("grave-p1")).toHaveTextContent("pivot");
    expect(screen.getByTestId("grave-p1")).toHaveTextContent(/Ship ở 70%/);
    expect(screen.getByTestId("grave-p1")).toHaveTextContent("04/2026"); // died MM/YYYY
    expect(screen.getByTestId("restore-p1")).toBeInTheDocument();
  });

  it("lesson null → 💡 line SKIPPED entirely (never fabricated, per dispatch)", async () => {
    getGraveyard.mockResolvedValueOnce(STATS({ graves: [GRAVE({ lesson: null })], lessons: [] }));
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("grave-p1")).toBeInTheDocument());
    // no 💡 line at all when lesson is null (not a placeholder, not fabricated)
    expect(screen.getByTestId("grave-p1")).not.toHaveTextContent("💡");
    // the card still renders (name/reason intact)
    expect(screen.getByTestId("grave-p1")).toHaveTextContent("pivot");
  });

  it("lesson present → 💡 line shown verbatim", async () => {
    getGraveyard.mockResolvedValueOnce(STATS());
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("grave-p1")).toBeInTheDocument());
    expect(screen.getByTestId("grave-p1")).toHaveTextContent(/💡 Ship ở 70%/);
  });

  it("empty graveyard → celebratory empty state, no crash", async () => {
    getGraveyard.mockResolvedValueOnce(STATS({ graves: [], count: 0, lessons: [], commonReasons: [] }));
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-empty")).toBeInTheDocument());
  });

  it("renders the lessons panel from lessons[]", async () => {
    getGraveyard.mockResolvedValueOnce(STATS());
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-lessons")).toHaveTextContent(/Ship ở 70%/));
  });

  it("grid/timeline toggle switches view", async () => {
    getGraveyard.mockResolvedValueOnce(STATS());
    const user = userEvent.setup();
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-toggle")).toBeInTheDocument());
    await user.click(screen.getByText("Dòng thời gian"));
    // still renders graves (no crash on view switch)
    expect(screen.getByTestId("grave-p1")).toBeInTheDocument();
  });

  it("GET error → friendly error state", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getGraveyard.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-error")).toBeInTheDocument());
  });

  it("TEETH: fulfilled-but-undefined body → error, no crash", async () => {
    getGraveyard.mockResolvedValueOnce(undefined);
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("graveyard-error")).toBeInTheDocument());
  });
});

describe("S4 Graveyard — restore (write) + fail-closed teeth", () => {
  it("restore success → POSTs /restore then refetches", async () => {
    getGraveyard.mockResolvedValue(STATS());
    restoreProject.mockResolvedValueOnce({ success: true, data: {} });
    const user = userEvent.setup();
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("restore-p1")).toBeInTheDocument());
    await user.click(screen.getByTestId("restore-p1"));
    await waitFor(() => expect(restoreProject).toHaveBeenCalledWith("p1"));
  });

  it("TEETH: restore FAILS → error surfaces, grave NOT removed (fail-closed)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getGraveyard.mockResolvedValue(STATS());
    restoreProject.mockRejectedValueOnce(new (ApiError as any)(500, "restore blew up"));
    const user = userEvent.setup();
    render(<GraveyardPage />);
    await waitFor(() => expect(screen.getByTestId("restore-p1")).toBeInTheDocument());
    await user.click(screen.getByTestId("restore-p1"));
    await waitFor(() => expect(screen.getByTestId("graveyard-action-error")).toHaveTextContent(/thất bại/));
    // the grave is still on screen (not optimistically removed)
    expect(screen.getByText("OldProj")).toBeInTheDocument();
  });
});
