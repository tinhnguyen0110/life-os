import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";

// mock the NAMED api fns the hook calls — partial-mock keeps ApiError real.
const getBrief = vi.fn();
const getBriefHistory = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getBrief: () => getBrief(), getBriefHistory: () => getBriefHistory() };
});

import BriefPage from "../page";

afterEach(() => { getBrief.mockReset(); getBriefHistory.mockReset(); });

const PRIORITY = (over = {}) => ({ n: 1, text: "crewly đứng 69 ngày — xem lại hay bỏ?", source: "projects", severity: "warn", ...over });
const BRIEF = (over = {}) => ({
  success: true,
  data: {
    generatedAt: "2026-06-06T15:32:30Z", asOf: "2026-04-17", source: "template",
    summary: { netWorth: 63121, projectsActive: 3, claudePct: 18.9, alertsToday: 2 },
    priorities: [PRIORITY()], stale: true, warnings: [],
    ...over,
  },
});
const HIST = (data: unknown[] = []) => ({ success: true, data });

describe("S11 Brief — render + summary", () => {
  it("renders 4 summary stat cards render-only (netWorth/projectsActive/claudePct/alertsToday)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF());
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-summary")).toBeInTheDocument());
    const s = screen.getByTestId("brief-summary");
    expect(s).toHaveTextContent("$63,121");
    expect(s).toHaveTextContent("3"); // projectsActive
    expect(s).toHaveTextContent("18.9%"); // claudePct render-only, NOT ×100
    expect(s).toHaveTextContent("2"); // alertsToday
  });

  it("header says 'template' NOT opus/AI model (honest source)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF());
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-meta")).toBeInTheDocument());
    expect(screen.getByTestId("brief-meta")).toHaveTextContent("template");
    expect(screen.getByTestId("brief-meta")).not.toHaveTextContent(/opus|sonnet|gpt/i);
  });

  it("stale brief → header shows 'cũ' marker (don't imply live)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF({ stale: true }));
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-meta")).toBeInTheDocument());
    expect(screen.getByTestId("brief-meta")).toHaveTextContent("cũ");
  });

  it("null summary source → '—' NOT a fabricated 0 (claude/netWorth down)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF({ summary: { netWorth: null, projectsActive: 0, claudePct: null, alertsToday: 0 } }));
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-summary")).toBeInTheDocument());
    // netWorth null → "—", claudePct null → "—" (NOT "$0" / "0.0%")
    const s = screen.getByTestId("brief-summary");
    expect(s).toHaveTextContent("—");
    expect(s).not.toHaveTextContent("0.0%");
  });
});

describe("S11 Brief — priorities (severity-ordered, styled)", () => {
  it("renders numbered priorities with severity class + source/label", async () => {
    getBrief.mockResolvedValueOnce(BRIEF({ priorities: [
      PRIORITY({ n: 1, text: "Quota 95%", source: "claude", severity: "urgent" }),
      PRIORITY({ n: 2, text: "drift crypto", source: "finance", severity: "warn" }),
    ] }));
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-priority-1")).toBeInTheDocument());
    expect(screen.getByTestId("brief-priority-1")).toHaveAttribute("data-severity", "urgent");
    expect(screen.getByTestId("brief-priority-1")).toHaveClass("urgent");
    expect(screen.getByTestId("brief-priority-1")).toHaveTextContent("Quota 95%");
    expect(screen.getByTestId("brief-priority-1")).toHaveTextContent("claude");
    expect(screen.getByTestId("brief-priority-2")).toHaveAttribute("data-severity", "warn");
  });

  it("HONEST-EMPTY: priorities=[] → calm 'Ổn định' state (NOT an error)", async () => {
    getBrief.mockResolvedValueOnce(BRIEF({ priorities: [] }));
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-calm")).toBeInTheDocument());
    expect(screen.getByTestId("brief-calm")).toHaveTextContent(/Ổn định/);
    expect(screen.queryByTestId("brief-error")).toBeNull(); // calm is NOT an error
  });
});

describe("S11 Brief — history (secondary, fail-open)", () => {
  it("empty history → friendly empty message", async () => {
    getBrief.mockResolvedValueOnce(BRIEF());
    getBriefHistory.mockResolvedValueOnce(HIST([]));
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-history-empty")).toBeInTheDocument());
  });

  it("history present → renders past brief cards", async () => {
    getBrief.mockResolvedValueOnce(BRIEF());
    getBriefHistory.mockResolvedValueOnce(HIST([BRIEF({ asOf: "2026-04-16" }).data]));
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-history-card")).toBeInTheDocument());
  });

  it("FAIL-OPEN: history down → brief still renders, history shows its own error", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getBrief.mockResolvedValueOnce(BRIEF());
    getBriefHistory.mockRejectedValueOnce(new (ApiError as any)(500, "hist down"));
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-history-error")).toBeInTheDocument());
    // primary brief unaffected
    expect(screen.getByTestId("brief-summary")).toBeInTheDocument();
    expect(screen.getByTestId("brief-priority-1")).toBeInTheDocument();
  });
});

describe("S11 Brief — states + warning", () => {
  it("GET /brief error → friendly error + retry", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getBrief.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-error")).toBeInTheDocument());
    expect(screen.getByTestId("brief-error")).toHaveTextContent("down");
  });

  it("TEETH: malformed brief (data==null) → error, NOT a blank render", async () => {
    getBrief.mockResolvedValueOnce({ success: true, data: null });
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-error")).toBeInTheDocument());
    expect(screen.getByTestId("brief-error")).toHaveTextContent("phản hồi không hợp lệ");
  });

  it("warning passthrough → banner shown", async () => {
    getBrief.mockResolvedValueOnce({ ...BRIEF(), warning: "active: repo unreadable" });
    getBriefHistory.mockResolvedValueOnce(HIST());
    render(<BriefPage />);
    await waitFor(() => expect(screen.getByTestId("brief-warning")).toBeInTheDocument());
    expect(screen.getByTestId("brief-warning")).toHaveTextContent("repo unreadable");
  });
});
