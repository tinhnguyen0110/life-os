import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, within, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #122 TRACING-UX2 — the 2-column redesign: LEFT Hoạt động (todos = text + tick +
   optional inline 🔔-remind), RIGHT Note (text + optional 🔔-remind, #121
   /tracing/notes), streak/heatmap KEPT but small/collapsed. The old chip-row / emoji /
   color / goal / heavy-form / template-picker are INTENTIONALLY DROPPED — this suite
   asserts both the new behavior AND the inverted mock-diff (those are gone).

   Mocks the NAMED api fns (mock-named-getter-not-apiget). Steady-state fetches use
   mockResolvedValue (NOT ...Once) so a refetch-after-write doesn't exhaust the queue →
   undefined → unhandled rejection (unhandled-errors-not-green). Asserts scoped to
   testids (scope-no-fabrication-asserts-to-element). */
const getTracing = vi.fn();
const logTracingSession = vi.fn();
const createActivity = vi.fn();
const archiveActivity = vi.fn();
const getReminderChannels = vi.fn();
const getTracingNotes = vi.fn();
const createTracingNote = vi.fn();
const updateTracingNote = vi.fn();
const deleteTracingNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getTracing: (...a: unknown[]) => getTracing(...a),
    logTracingSession: (...a: unknown[]) => logTracingSession(...a),
    createActivity: (...a: unknown[]) => createActivity(...a),
    archiveActivity: (...a: unknown[]) => archiveActivity(...a),
    getReminderChannels: (...a: unknown[]) => getReminderChannels(...a),
    getTracingNotes: (...a: unknown[]) => getTracingNotes(...a),
    createTracingNote: (...a: unknown[]) => createTracingNote(...a),
    updateTracingNote: (...a: unknown[]) => updateTracingNote(...a),
    deleteTracingNote: (...a: unknown[]) => deleteTracingNote(...a),
  };
});

import TracingPage from "../page";

const CHANNELS_OK = { success: true, data: { channels: [
  { id: "in_app", label: "In-app", available: true },
  { id: "email", label: "Email", available: true },
  { id: "discord", label: "Discord", available: true },
] } };

const ACT = (over = {}) => ({
  id: "water", name: "Uống nước", emoji: "💧", icon: "", unit: "ly", goal: 1, color: "#4ea0ff",
  today: { done: false, val: 0, dur: "", durMin: 0, note: null, pct: 0, sessions: 0 },
  remindAt: null, remindRepeat: "off",
  streak: 0, week: [0, 0, 0, 0, 0, 0, 0], history12w: Array(84).fill(0),
  ...over,
});
const OVERVIEW = (acts = [ACT()], over = {}) => ({
  success: true,
  data: {
    date: "2026-06-22", activities: acts, heatmap12w: Array(84).fill(0),
    score: { total: acts.length, done: 0, pct: 0, timeActive: "", topStreak: 0 },
    ...over,
  },
});
const NOTE = (over = {}) => ({
  id: "1", text: "nhớ gọi điện", remindAt: null, remindRepeat: "off", remindChannel: "in_app",
  created: "2026-06-22T10:00:00+07:00", ...over,
});
const NOTES = (notes: ReturnType<typeof NOTE>[] = []) => ({ success: true, data: { notes } });

beforeEach(() => {
  getReminderChannels.mockResolvedValue(CHANNELS_OK);
  getTracingNotes.mockResolvedValue(NOTES([]));
  getTracing.mockResolvedValue(OVERVIEW());
});
afterEach(() => {
  getTracing.mockReset(); logTracingSession.mockReset(); createActivity.mockReset();
  archiveActivity.mockReset(); getReminderChannels.mockReset();
  getTracingNotes.mockReset(); createTracingNote.mockReset(); updateTracingNote.mockReset();
  deleteTracingNote.mockReset(); cleanup();
});

describe("#122 Tracing — 2-column layout", () => {
  it("renders the 2-col: a todos panel (left) + a notes panel (right)", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-2col")).toBeInTheDocument());
    expect(screen.getByTestId("tracing-todos")).toBeInTheDocument();
    expect(screen.getByTestId("tracing-notes")).toBeInTheDocument();
  });

  it("streak + heatmap are KEPT but in a small/collapsed <details> (not the focus)", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-stats")).toBeInTheDocument());
    // it's a <details> (collapsible), with the heatmap grid inside
    expect(screen.getByTestId("tracing-stats").tagName.toLowerCase()).toBe("details");
    expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument();
    expect(screen.getByTestId("tracing-stats-summary")).toBeInTheDocument();
  });
});

describe("#122 Tracing — LEFT todos (text + tick + remind)", () => {
  it("add-via-text → createActivity(text, goal:1) [goal hidden, defaulted to 1]", async () => {
    createActivity.mockResolvedValue({ success: true, data: { id: "uong-nuoc" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("todo-input"), "Uống nước");
    await user.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.name).toBe("Uống nước");
    expect(body.goal).toBe(1);          // hidden goal=1 (todo, not a measured habit)
    expect(body.id).toBe("uong-nuoc");  // slugified from the text
    expect(body.remindRepeat).toBe("off"); // no remind by default
  });

  it("blank text → honest validation error, no POST", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-submit")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(screen.getByTestId("todo-add-error")).toBeInTheDocument());
    expect(createActivity).not.toHaveBeenCalled();
  });

  it("ticking an undone todo → log(id, {val:1}) [tick = complete one session]", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", today: { done: false, val: 0, dur: "", durMin: 0, note: null, pct: 0, sessions: 0 } })]));
    logTracingSession.mockResolvedValue({ success: true, data: ACT() });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tick-water")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("tick-water"));
    await waitFor(() => expect(logTracingSession).toHaveBeenCalledWith("water", expect.objectContaining({ val: 1 })));
  });

  it("a DONE todo shows a checked tick (line-through) + is not re-loggable", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", today: { done: true, val: 1, dur: "", durMin: 0, note: null, pct: 100, sessions: 1 } })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-water")).toBeInTheDocument());
    expect(screen.getByTestId("todo-water")).toHaveAttribute("data-done", "true");
    expect(screen.getByTestId("tick-water")).toBeDisabled(); // append-only, no un-tick
    await userEvent.setup().click(screen.getByTestId("tick-water"));
    // a no-op click on a done todo must NOT fire a log
    expect(logTracingSession).not.toHaveBeenCalled();
  });

  it("todo with a remind shows the inline 🔔 chip (render-only from the activity)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "run", name: "Chạy bộ", remindAt: "06:30", remindRepeat: "daily" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-remind-run")).toBeInTheDocument());
    expect(screen.getByTestId("todo-remind-run")).toHaveTextContent("06:30");
    expect(screen.getByTestId("todo-remind-run")).toHaveTextContent(/hằng ngày/);
  });

  it("add WITH remind on → sends remindAt + remindRepeat + remindChannel", async () => {
    createActivity.mockResolvedValue({ success: true, data: { id: "tap-the-duc" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("todo-input"), "Tập thể dục");
    await user.click(screen.getByTestId("todo-remind-toggle"));   // turn remind on
    await waitFor(() => expect(screen.getByTestId("todo-remind-channel")).toBeInTheDocument());
    await user.selectOptions(screen.getByTestId("todo-remind-channel"), "discord");
    await user.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.remindAt).toBe("07:00");        // default time
    expect(body.remindRepeat).toBe("daily");
    expect(body.remindChannel).toBe("discord");
  });

  it("archive a todo → archiveActivity(id)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    archiveActivity.mockResolvedValue({ success: true, data: { archived: "water" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-archive-water")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("todo-archive-water"));
    await waitFor(() => expect(archiveActivity).toHaveBeenCalledWith("water"));
  });

  it("no todos → honest empty state (not blank)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todos-empty")).toBeInTheDocument());
  });
});

describe("#122 Tracing — RIGHT note (text + remind), #121 /tracing/notes", () => {
  it("add a note → createTracingNote({text}) + refetch", async () => {
    createTracingNote.mockResolvedValue({ success: true, data: NOTE({ id: "9", text: "deploy lúc 5pm" }) });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "deploy lúc 5pm");
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(createTracingNote).toHaveBeenCalled());
    expect(createTracingNote.mock.calls[0][0].text).toBe("deploy lúc 5pm");
    expect(createTracingNote.mock.calls[0][0].remindRepeat).toBe("off"); // no remind by default
  });

  it("add a note WITH remind → sends remindAt + remindRepeat + remindChannel", async () => {
    createTracingNote.mockResolvedValue({ success: true, data: NOTE() });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "uống thuốc");
    await user.click(screen.getByTestId("note-remind-toggle"));
    await waitFor(() => expect(screen.getByTestId("note-remind-time")).toBeInTheDocument());
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(createTracingNote).toHaveBeenCalled());
    const body = createTracingNote.mock.calls[0][0];
    expect(body.remindAt).toBe("07:00");
    expect(body.remindRepeat).toBe("daily");
    expect(body.remindChannel).toBe("in_app");
  });

  it("blank note text → validation error, no POST", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-submit")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(screen.getByTestId("note-add-error")).toBeInTheDocument());
    expect(createTracingNote).not.toHaveBeenCalled();
  });

  it("renders existing notes (text + remind chip when set)", async () => {
    getTracingNotes.mockResolvedValue(NOTES([
      NOTE({ id: "1", text: "nhớ gọi điện" }),
      NOTE({ id: "2", text: "uống thuốc", remindAt: "21:00", remindRepeat: "daily" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-1")).toBeInTheDocument());
    expect(screen.getByTestId("note-text-1")).toHaveTextContent("nhớ gọi điện");
    expect(screen.getByTestId("note-remind-2")).toHaveTextContent("21:00");
    // note 1 has no remind → no chip
    expect(screen.queryByTestId("note-remind-1")).toBeNull();
  });

  it("delete a note → deleteTracingNote(id)", async () => {
    getTracingNotes.mockResolvedValue(NOTES([NOTE({ id: "7", text: "xóa tôi" })]));
    deleteTracingNote.mockResolvedValue({ success: true, data: { deleted: "7" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-delete-7")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("note-delete-7"));
    await waitFor(() => expect(deleteTracingNote).toHaveBeenCalledWith("7"));
  });

  it("no notes → honest empty (not blank)", async () => {
    getTracingNotes.mockResolvedValue(NOTES([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("notes-empty")).toBeInTheDocument());
  });

  it("notes load error → honest error, does NOT break the page (todos still render)", async () => {
    getTracingNotes.mockRejectedValue(new Error("notes down"));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("notes-load-error")).toBeInTheDocument());
    // the rest of the page is fine
    expect(screen.getByTestId("tracing-todos")).toBeInTheDocument();
  });
});

describe("#122 Tracing — inverted mock-diff (the DROPPED set is gone)", () => {
  it("NO template picker, NO emoji/color/goal field, NO heavy add-form, NO chip row", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-2col")).toBeInTheDocument());
    // the old heavy-form / template / emoji / color / goal-field testids must be ABSENT
    for (const gone of ["add-form", "log-form", "a-name", "a-goal", "a-unit", "a-emoji", "a-color", "a-id", "a-advanced-toggle", "tracing-template-picker"]) {
      expect(screen.queryByTestId(gone)).toBeNull();
    }
  });
});

describe("#122 Tracing — defensive (kept from #65)", () => {
  it("loading state", async () => {
    getTracing.mockReturnValue(new Promise(() => {})); // never resolves
    render(<TracingPage />);
    expect(screen.getByTestId("tracing-loading")).toBeInTheDocument();
    // let the (separate) channels fetch settle so its state update is flushed in-act
    // (it resolves independently of the never-resolving getTracing).
    await waitFor(() => expect(getReminderChannels).toHaveBeenCalled());
  });

  it("GET /tracing error → friendly error + retry", async () => {
    getTracing.mockRejectedValue(new Error("tracing 500"));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-error")).toHaveTextContent("tracing 500"));
  });

  it("heatmap renders 84 cells, banded by count (kept, render-only)", async () => {
    const hm = Array(84).fill(0); hm[20] = 3;
    getTracing.mockResolvedValue(OVERVIEW([ACT()], { heatmap12w: hm, score: { total: 1, done: 1, pct: 100, timeActive: "", topStreak: 4 } }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument());
    expect(screen.getByTestId("hc-20").getAttribute("data-count")).toBe("3");
    expect(screen.getByTestId("hc-20").getAttribute("style")).toContain("color-mix"); // colored
    expect(screen.getByTestId("hc-0").getAttribute("style")).toContain("--bg-3");     // empty
  });

  it("streak badge thresholds: ≥7 🔥, ≥3 ✦ (kept in the collapsed stats)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "fire", name: "Fire", streak: 9 }),
      ACT({ id: "star", name: "Star", streak: 4 }),
      ACT({ id: "none", name: "None", streak: 1 }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("streak-fire")).toBeInTheDocument());
    expect(screen.getByTestId("streak-fire")).toHaveTextContent("🔥");
    expect(screen.getByTestId("streak-star")).toHaveTextContent("✦");
    expect(screen.getByTestId("streak-none")).not.toHaveTextContent(/🔥|✦/);
  });
});
