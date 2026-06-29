import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, within, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** set a controlled <input type="date"> value the React way (fireEvent.change drives the
 *  synthetic onChange so the component state actually updates — a raw .value= does not). */
function setDate(input: HTMLInputElement, value: string) {
  fireEvent.change(input, { target: { value } });
}

/* #126 TRACING-UX2 timeline redesign — the VIEW changed (default = a time-rail read-view +
   an edit-mode toggle + multi-list notes + "+ Từ mẫu" templates), the BASE model is KEPT
   (todo=activity goal=1, tick=log val=1→done, note→#121, streak/heatmap collapsed).

   AUDIT vs the #122 suite: the #122 tests that asserted the *plain 2-col left-list view
   shape* (tracing-todos panel id, always-visible todo-input, todo-* row testids) are
   REPLACED by timeline-shape tests here. The surviving BEHAVIOR is re-covered: add-todo →
   createActivity(goal:1), tick → log(val:1), remind chip, archive, empty-state, the note
   multi-list, streak/heatmap kept. NEW coverage: edit-mode gating, timeline time-order,
   tick-in-read-mode, the #124 template picker.

   Mocks the NAMED api fns. Steady-state = mockResolvedValue (unhandled-errors-not-green).
   Asserts scoped to testids. */
const getTracing = vi.fn();
const logTracingSession = vi.fn();
const createActivity = vi.fn();
const archiveActivity = vi.fn();
const getReminderChannels = vi.fn();
const getTracingNotes = vi.fn();
const createTracingNote = vi.fn();
const updateTracingNote = vi.fn();
const deleteTracingNote = vi.fn();
const getTracingTemplates = vi.fn();
const addTemplateToToday = vi.fn();
const addAllTemplates = vi.fn();
const updateActivity = vi.fn();   // #136 — rename + reminder PUT
const untickActivity = vi.fn();   // #136 — un-tick (clear today's log)
const getTemplateSets = vi.fn();  // #137 — the template-set modal source
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
    getTracingTemplates: (...a: unknown[]) => getTracingTemplates(...a),
    addTemplateToToday: (...a: unknown[]) => addTemplateToToday(...a),
    addAllTemplates: (...a: unknown[]) => addAllTemplates(...a),
    updateActivity: (...a: unknown[]) => updateActivity(...a),
    untickActivity: (...a: unknown[]) => untickActivity(...a),
    getTemplateSets: (...a: unknown[]) => getTemplateSets(...a),
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
  id: "1", text: "nhớ gọi điện", remindAt: null, remindDate: null, remindRepeat: "off", remindChannel: "in_app",
  created: "2026-06-22T10:00:00+07:00", ...over,
});
const NOTES = (notes: ReturnType<typeof NOTE>[] = []) => ({ success: true, data: { notes } });
const TPL = (over = {}) => ({ id: "uong-nuoc", name: "Uống nước", emoji: "💧", icon: "droplet", unit: "ly", goal: 8, color: "#38bdf8", source: "seed", ...over });

beforeEach(() => {
  getReminderChannels.mockResolvedValue(CHANNELS_OK);
  getTracingNotes.mockResolvedValue(NOTES([]));
  getTracing.mockResolvedValue(OVERVIEW());
  getTracingTemplates.mockResolvedValue({ success: true, data: { templates: [TPL()] } });
  getTemplateSets.mockResolvedValue({ success: true, data: { sets: [] } }); // #137 modal source
});
afterEach(() => {
  getTracing.mockReset(); logTracingSession.mockReset(); createActivity.mockReset();
  archiveActivity.mockReset(); getReminderChannels.mockReset();
  getTracingNotes.mockReset(); createTracingNote.mockReset(); updateTracingNote.mockReset();
  deleteTracingNote.mockReset(); getTracingTemplates.mockReset();
  addTemplateToToday.mockReset(); addAllTemplates.mockReset(); cleanup();
});

describe("#136 Tracing — timeline DEFAULT + NO global edit toggle", () => {
  it("DEFAULT = the timeline rail; the add-tools + template are ALWAYS visible (no global Sửa)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("timeline-rail")).toBeInTheDocument());
    expect(screen.getByTestId("tracing-timeline")).toBeInTheDocument();
    // #136 — NO global edit toggle
    expect(screen.queryByTestId("edit-toggle")).toBeNull();
    // add-input + "+ Từ mẫu" are visible in the DEFAULT view (the user's complaint: template was hidden)
    expect(screen.getByTestId("todo-input")).toBeInTheDocument();
    expect(screen.getByTestId("tpl-open")).toBeInTheDocument();
  });

  it("TRACING-UX3 req4 — streak panel is ALWAYS-VISIBLE (no more collapsed <details>) + heatmap kept", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-stats")).toBeInTheDocument());
    // no longer a <details> (always-visible panel now)
    expect(screen.getByTestId("tracing-stats").tagName.toLowerCase()).not.toBe("details");
    expect(screen.queryByTestId("tracing-stats-summary")).toBeNull();
    expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument();
  });

  it("#139 — timeline orders TIMED by time first, then a legacy timeless row at the END (NO 'CẢ NGÀY' header)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "anytime", name: "Bất kỳ", remindAt: null, time: null }),
      ACT({ id: "late", name: "Tối", remindAt: "21:00", remindRepeat: "daily" }),
      ACT({ id: "early", name: "Sáng", remindAt: "06:00", remindRepeat: "daily" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-early")).toBeInTheDocument());
    // timed rows ascending, then the timeless one LAST — ordering preserved.
    const order = screen.getAllByTestId(/^tl-(early|late|anytime)$/).map((r) => r.getAttribute("data-testid"));
    expect(order).toEqual(["tl-early", "tl-late", "tl-anytime"]);
    // #139 — the "CẢ NGÀY" bucket header is REMOVED (timeless rows just render at the end).
    expect(screen.queryByTestId("timeline-anytime-sep")).toBeNull();
    expect(screen.queryByText("CẢ NGÀY")).toBeNull();
  });

  it("#139 — a legacy null-time row shows a PROMINENT '⏰ Đặt giờ' pill (not a bare '—'), and clicking it opens the time editor", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "legacy", name: "Cũ", remindAt: null, time: null }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-legacy")).toBeInTheDocument());
    const timeCell = screen.getByTestId("tl-time-legacy");
    // the cell is the actionable pill, NOT a bare dash
    expect(timeCell.className).toContain("tl-settime-pill");
    expect(timeCell.textContent).toContain("Đặt giờ");
    expect(timeCell.textContent).not.toBe("—");
    expect(timeCell.textContent).not.toBe("–");
    // clicking it opens the same per-card time editor
    fireEvent.click(timeCell);
    await waitFor(() => expect(screen.getByTestId("tl-time-editor-legacy")).toBeInTheDocument());
  });

  it("#139 — a TIMED row shows the real time (no '⏰ Đặt giờ' pill)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "timed", name: "Có giờ", remindAt: "06:30", remindRepeat: "daily" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-timed")).toBeInTheDocument());
    const timeCell = screen.getByTestId("tl-time-timed");
    expect(timeCell.textContent).toContain("06:30");
    expect(timeCell.className).not.toContain("tl-settime-pill");
    expect(timeCell.textContent).not.toContain("Đặt giờ");
  });

  it("#139 — the add-form has a TIME input (default 08:00) → createActivity sends a time, so a new activity is never timeless", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    createActivity.mockResolvedValue({ success: true, data: ACT({ id: "doc-sach", name: "Đọc sách", time: "08:00" }) });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-add-form")).toBeInTheDocument());
    // the time input exists + defaults to 08:00
    const timeInput = screen.getByTestId("todo-time") as HTMLInputElement;
    expect(timeInput).toBeInTheDocument();
    expect(timeInput.value).toBe("08:00");
    // type a name + submit → createActivity called WITH a time
    fireEvent.change(screen.getByTestId("todo-input"), { target: { value: "Đọc sách" } });
    fireEvent.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.time).toBe("08:00");
    expect(body.name).toBe("Đọc sách");
  });
});

describe("TRACING-UX3 — req1 giờ bắt buộc · req2 nhắc default=giờ-việc · req3 anytime bucket · req4 streak panel", () => {
  // req1 — empty time blocks the add (custom message), no createActivity call.
  it("req1: empty time → blocks add with 'giờ là bắt buộc' message, createActivity NOT called", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-add-form")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("todo-input"), { target: { value: "Đọc sách" } });
    // clear the 08:00 prefill → empty time
    fireEvent.change(screen.getByTestId("todo-time"), { target: { value: "" } });
    fireEvent.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(screen.getByTestId("todo-add-error")).toHaveTextContent(/giờ là bắt buộc/i));
    expect(createActivity).not.toHaveBeenCalled();
  });

  it("req1: the time input is visually marked required (aria-required + '*' cue)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-time")).toBeInTheDocument());
    expect(screen.getByTestId("todo-time")).toHaveAttribute("aria-required", "true");
    expect(screen.getByTestId("todo-time-label")).toHaveTextContent("*");
  });

  // req2 — toggling the todo-row remind ON seeds remind.time = the activity time (todoTime).
  it("req2: toggle remind ON in the add-row → nhắc-time defaults to giờ-việc (not 07:00)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    createActivity.mockResolvedValue({ success: true, data: ACT({ id: "doc-sach" }) });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-add-form")).toBeInTheDocument());
    // set the activity time to 09:30, then toggle remind on
    fireEvent.change(screen.getByTestId("todo-time"), { target: { value: "09:30" } });
    fireEvent.click(screen.getByTestId("todo-remind-toggle"));
    // the remind-time input now shows the activity time, not the disjoint 07:00
    const remindTime = screen.getByTestId("todo-remind-time") as HTMLInputElement;
    expect(remindTime.value).toBe("09:30");
    // and it's still editable + the add carries it
    fireEvent.change(screen.getByTestId("todo-input"), { target: { value: "Đọc sách" } });
    fireEvent.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0].remindAt).toBe("09:30");
  });

  it("req2: the NOTE add-row remind keeps its own default (no activity time) — still 07:00", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    getTracingNotes.mockResolvedValue(NOTES([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-add-form")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("note-remind-toggle"));
    expect((screen.getByTestId("note-remind-time") as HTMLInputElement).value).toBe("07:00");
  });

  // req3 — leftover timeless rows go in a labeled "Chưa đặt giờ" bucket at the bottom; đặt-giờ works.
  it("req3: legacy timeless rows render under a 'Chưa đặt giờ' bucket header (timed rows above it)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "timeless", name: "Cũ", remindAt: null, time: null }),
      ACT({ id: "timed", name: "Sáng", remindAt: null, time: "06:00" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-timeless")).toBeInTheDocument());
    // the bucket header exists + names the count
    const head = screen.getByTestId("timeline-anytime-head");
    expect(head).toHaveTextContent(/Chưa đặt giờ/i);
    expect(head).toHaveTextContent(/1 việc/);
    // đặt-giờ on the timeless row still works (opens the time editor)
    fireEvent.click(screen.getByTestId("tl-time-timeless"));
    await waitFor(() => expect(screen.getByTestId("tl-time-editor-timeless")).toBeInTheDocument());
  });

  it("req3: NO 'Chưa đặt giờ' bucket header when every row is timed", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "timed", time: "06:00" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-timed")).toBeInTheDocument());
    expect(screen.queryByTestId("timeline-anytime-head")).toBeNull();
  });

  // req4 — streak tiles: current = max(a.streak), best = topStreak; heatmap renders 84 cells.
  it("req4: streak tiles show current = max(a.streak) 🔥 + best = topStreak ✦ + 84 heatmap cells", async () => {
    getTracing.mockResolvedValue(OVERVIEW(
      [ACT({ id: "a", streak: 4 }), ACT({ id: "b", streak: 9 }), ACT({ id: "c", streak: 2 })],
      { score: { total: 3, done: 0, pct: 0, timeActive: "", topStreak: 21 } },
    ));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("streak-tiles")).toBeInTheDocument());
    // current = max running streak across activities = 9
    expect(screen.getByTestId("streak-current")).toHaveTextContent("9");
    // best = topStreak = 21
    expect(screen.getByTestId("streak-best")).toHaveTextContent("21");
    // heatmap renders all 84 cells (12w × 7)
    expect(screen.getByTestId("heatmap-grid").querySelectorAll('[data-testid^="hc-"]').length).toBe(84);
  });

  it("req4: current streak = 0 (no crash) when there are no activities", async () => {
    getTracing.mockResolvedValue(OVERVIEW([], { score: { total: 0, done: 0, pct: 0, timeActive: "", topStreak: 0 } }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("streak-tiles")).toBeInTheDocument());
    expect(screen.getByTestId("streak-current")).toHaveTextContent("0");
  });
});

describe("#136 Tracing — tick is a TOGGLE (un-complete), 1-click in read view", () => {
  it("tick an UNDONE row → log(val:1) [the complete half]", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", today: { done: false, val: 0, dur: "", durMin: 0, note: null, pct: 0, sessions: 0 } })]));
    logTracingSession.mockResolvedValue({ success: true, data: ACT() });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tick-water")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("tick-water"));
    await waitFor(() => expect(logTracingSession).toHaveBeenCalledWith("water", expect.objectContaining({ val: 1 })));
  });

  it("ud tick a DONE row again → UN-complete (untickActivity) [the toggle's un-complete half]", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", today: { done: true, val: 1, dur: "", durMin: 0, note: null, pct: 100, sessions: 1 } })]));
    untickActivity.mockResolvedValue({ success: true, data: ACT() });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    expect(screen.getByTestId("tl-water")).toHaveAttribute("data-done", "true");
    // a DONE tick is NOT disabled anymore (it un-completes)
    expect(screen.getByTestId("tick-water")).not.toBeDisabled();
    await userEvent.setup().click(screen.getByTestId("tick-water"));
    await waitFor(() => expect(untickActivity).toHaveBeenCalledWith("water"));
    expect(logTracingSession).not.toHaveBeenCalled(); // un-complete path, not a new log
  });

  it("a timed todo shows its remind chip — GAP-2: time + freq + CHANNEL on the card face", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "run", name: "Chạy bộ", remindAt: "06:30", remindRepeat: "daily", remindChannel: "email" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-remind-run")).toBeInTheDocument());
    expect(screen.getByTestId("tl-remind-run")).toHaveTextContent("06:30");
    expect(screen.getByTestId("tl-remind-run")).toHaveTextContent(/hằng ngày/);  // freq
    expect(screen.getByTestId("tl-remind-run-channel")).toHaveTextContent("Email"); // channel
  });

  it("🔴 #136 GAP-4(A) — rich row: icon + metric (val·unit) + dur + note sub-detail (REAL fields, no fabrication)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({
      id: "water", name: "Uống nước", emoji: "💧", unit: "ly",
      today: { done: true, val: 3, dur: "15m", durMin: 15, note: "sáng", pct: 100, sessions: 1 },
    })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    expect(screen.getByTestId("tl-icon-water")).toHaveTextContent("💧"); // the emoji icon
    const detail = screen.getByTestId("tl-detail-water");
    expect(detail).toHaveTextContent("3 ly");   // metric = val + unit (REAL)
    expect(detail).toHaveTextContent("15m");     // dur (REAL)
    expect(detail).toHaveTextContent("sáng");    // today's note as sub-detail (REAL)
    // NO fabricated km/pace/location — only the fields that exist
    expect(detail).not.toHaveTextContent(/km|pace/);
  });

  it("GAP-4(A) — a bare todo (no metric/dur/note) shows NO sub-detail line (honest, not empty '·')", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "plain", name: "Việc trống", today: { done: false, val: 0, dur: "", durMin: 0, note: null, pct: 0, sessions: 0 } })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-plain")).toBeInTheDocument());
    expect(screen.queryByTestId("tl-detail-plain")).toBeNull(); // no fabricated detail
  });

  it("🔴 #136 GAP-3(ii) — a dedicated TIME (independent of reminder) shows on the rail + sorts the timeline", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "late", name: "Tối", time: "20:00", remindAt: null, remindRepeat: "off" }),   // time, NO reminder
      ACT({ id: "early", name: "Sáng", time: "06:00", remindAt: null, remindRepeat: "off" }),
      ACT({ id: "rem", name: "Có nhắc", time: null, remindAt: "12:00", remindRepeat: "daily" }), // fallback to remindAt
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-early")).toBeInTheDocument());
    // the rail shows the dedicated time even though there's NO reminder
    expect(screen.getByTestId("tl-time-early")).toHaveTextContent("06:00");
    expect(screen.getByTestId("tl-time-late")).toHaveTextContent("20:00");
    expect(screen.getByTestId("tl-time-rem")).toHaveTextContent("12:00"); // fallback to remindAt
    // sorted by the effective time: 06:00 < 12:00 < 20:00
    const order = screen.getAllByTestId(/^tl-(early|rem|late)$/).map((r) => r.getAttribute("data-testid"));
    expect(order).toEqual(["tl-early", "tl-rem", "tl-late"]);
  });

  it("🔴 #136 GAP-3(ii) — ⋯ → 'Đặt giờ' → set a time → edit(id, {time}) [no reminder needed]", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", time: null, remindAt: null })]));
    updateActivity.mockResolvedValue({ success: true, data: {} });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    fireEvent.click(screen.getByTestId("tl-op-time-water"));
    await waitFor(() => expect(screen.getByTestId("tl-time-editor-water")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("tl-time-input-water"), { target: { value: "08:30" } });
    fireEvent.click(screen.getByTestId("tl-time-save-water"));
    await waitFor(() => expect(updateActivity).toHaveBeenCalledWith("water", { time: "08:30" }));
  });

  it("GAP-3 — clearing the time → edit(id, {time:null})", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", time: "08:30", remindAt: null })]));
    updateActivity.mockResolvedValue({ success: true, data: {} });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    // the rail click opens the editor
    fireEvent.click(screen.getByTestId("tl-time-water"));
    await waitFor(() => expect(screen.getByTestId("tl-time-clear-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-time-clear-water"));
    await waitFor(() => expect(updateActivity).toHaveBeenCalledWith("water", { time: null }));
  });
});

describe("#136 Tracing — per-CARD edit (rename / reminder / delete), no global toggle", () => {
  it("each row has its OWN ⋯ ops menu (rename + reminder + delete)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    expect(screen.getByTestId("tl-op-rename-water")).toBeInTheDocument();
    expect(screen.getByTestId("tl-op-remind-water")).toBeInTheDocument();
    expect(screen.getByTestId("tl-op-delete-water")).toBeInTheDocument();
  });

  it("🔴 #137-T2 UX — the ⋯ menu CLOSES on an outside click (not re-click-the-icon)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    expect(screen.getByTestId("tl-ops-menu-water")).toBeInTheDocument();
    // a mousedown OUTSIDE the menu (the page body) closes it — no re-click of the ⋯ needed
    await new Promise((r) => setTimeout(r, 5)); // let the deferred listener attach
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByTestId("tl-ops-menu-water")).toBeNull());
  });

  it("🔴 #137-T2 UX — the inline TIME editor also closes on an outside click", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    fireEvent.click(screen.getByTestId("tl-op-time-water"));
    expect(screen.getByTestId("tl-time-editor-water")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 5));
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByTestId("tl-time-editor-water")).toBeNull());
  });

  it("🔴 #137-T2 UX — the inline REMINDER editor closes on an outside click", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    fireEvent.click(screen.getByTestId("tl-op-remind-water"));
    expect(screen.getByTestId("tl-remind-editor-water")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 5));
    fireEvent.mouseDown(document.body);
    await waitFor(() => expect(screen.queryByTestId("tl-remind-editor-water")).toBeNull());
  });

  it("🔴 INLINE RENAME (the missing Update) → updateActivity(id, {name})", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", name: "Uống nước" })]));
    updateActivity.mockResolvedValue({ success: true, data: {} });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    fireEvent.click(screen.getByTestId("tl-op-rename-water"));
    const input = screen.getByTestId("tl-rename-input-water") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Uống nước nhiều" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(updateActivity).toHaveBeenCalledWith("water", { name: "Uống nước nhiều" }));
  });

  it("🔴 set a reminder (time + freq + channel) on a todo → updateActivity {remindAt,remindRepeat,remindChannel}", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    updateActivity.mockResolvedValue({ success: true, data: {} });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    fireEvent.click(screen.getByTestId("tl-op-remind-water"));
    // the per-card RemindControls editor appears
    await waitFor(() => expect(screen.getByTestId("tl-remind-editor-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tlrem-water-remind-toggle")); // turn remind on
    await waitFor(() => expect(screen.getByTestId("tlrem-water-remind-channel")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("tlrem-water-remind-channel"), { target: { value: "discord" } });
    fireEvent.click(screen.getByTestId("tl-remind-save-water"));
    await waitFor(() => expect(updateActivity).toHaveBeenCalled());
    const [id, body] = updateActivity.mock.calls[0];
    expect(id).toBe("water");
    expect(body.remindAt).toBe("07:00");
    expect(body.remindRepeat).toBe("daily");
    expect(body.remindChannel).toBe("discord");
  });

  it("delete a todo via the ⋯ menu → archiveActivity", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    archiveActivity.mockResolvedValue({ success: true, data: { archived: "water" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("tl-ops-water"));
    fireEvent.click(screen.getByTestId("tl-op-delete-water"));
    await waitFor(() => expect(archiveActivity).toHaveBeenCalledWith("water"));
  });

  it("empty board → honest timeline-empty", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("timeline-empty")).toBeInTheDocument());
  });
});

describe("#136 Tracing — add-todo + '+ Từ mẫu' VISIBLE in default view", () => {
  it("add-via-text (always visible) → createActivity(text, goal:1)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    createActivity.mockResolvedValue({ success: true, data: { id: "uong-nuoc" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("todo-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("todo-input"), "Uống nước");
    await user.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.name).toBe("Uống nước");
    expect(body.goal).toBe(1);
  });

  it("🔴 #137 — '+ Từ mẫu' is visible in the DEFAULT view → opens the template-SET MODAL (not the old chip row)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    getTemplateSets.mockResolvedValue({ success: true, data: { sets: [] } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tpl-open")).toBeInTheDocument()); // visible, no edit gate
    // the OLD 1-word chip row is GONE
    expect(screen.queryByTestId("tpl-picker")).toBeNull();
    expect(screen.queryByTestId("tpl-add-all")).toBeNull();
    // clicking opens the MODAL (the new set surface)
    await userEvent.setup().click(screen.getByTestId("tpl-open"));
    await waitFor(() => expect(screen.getByTestId("tpl-modal")).toBeInTheDocument());
  });
});

describe("#126 Tracing — RIGHT note MULTI-LIST (text + remind), #121", () => {
  it("add a note → createTracingNote({text}); the form clears (add-multiple)", async () => {
    createTracingNote.mockResolvedValue({ success: true, data: NOTE({ id: "9", text: "deploy 5pm" }) });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "deploy 5pm");
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(createTracingNote).toHaveBeenCalled());
    expect(createTracingNote.mock.calls[0][0].text).toBe("deploy 5pm");
    // input cleared so the user can add another (multi-add)
    await waitFor(() => expect((screen.getByTestId("note-input") as HTMLTextAreaElement).value).toBe(""));
  });

  it("renders MULTIPLE note cards (the list), each with text + remind chip when set + delete", async () => {
    getTracingNotes.mockResolvedValue(NOTES([
      NOTE({ id: "1", text: "ghi chú một" }),
      NOTE({ id: "2", text: "ghi chú hai", remindAt: "21:00", remindRepeat: "daily", remindChannel: "discord" }),
      NOTE({ id: "3", text: "ghi chú ba" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-1")).toBeInTheDocument());
    expect(screen.getByTestId("note-2")).toBeInTheDocument();
    expect(screen.getByTestId("note-3")).toBeInTheDocument();
    expect(screen.getByTestId("note-text-1")).toHaveTextContent("ghi chú một");
    expect(screen.getByTestId("note-remind-2")).toHaveTextContent("21:00");
    // 🔴 #136 GAP-2 — the SET frequency + channel show ON the card face
    expect(screen.getByTestId("note-remind-2")).toHaveTextContent(/hằng ngày/);
    expect(screen.getByTestId("note-remind-2-channel")).toHaveTextContent("Discord");
    expect(screen.queryByTestId("note-remind-1")).toBeNull(); // no remind → no chip
    // #136 — each note card has its OWN ⋯ ops (the delete moved into it)
    expect(screen.getByTestId("note-ops-3")).toBeInTheDocument();
  });

  it("add a note WITH remind → sends remindAt/repeat/channel", async () => {
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
  });

  it("delete a note via the per-card ⋯ menu → deleteTracingNote(id)", async () => {
    getTracingNotes.mockResolvedValue(NOTES([NOTE({ id: "7", text: "xóa tôi" })]));
    deleteTracingNote.mockResolvedValue({ success: true, data: { deleted: "7" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-ops-7")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("note-ops-7"));
    fireEvent.click(screen.getByTestId("note-op-delete-7"));
    await waitFor(() => expect(deleteTracingNote).toHaveBeenCalledWith("7"));
  });

  it("🔴 #136 — set a reminder on an EXISTING note via its ⋯ → updateTracingNote {remindAt,...}", async () => {
    getTracingNotes.mockResolvedValue(NOTES([NOTE({ id: "5", text: "note no remind" })]));
    updateTracingNote.mockResolvedValue({ success: true, data: NOTE({ id: "5" }) });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-ops-5")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("note-ops-5"));
    fireEvent.click(screen.getByTestId("note-op-remind-5"));
    await waitFor(() => expect(screen.getByTestId("note-remind-editor-5")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("nrem-5-remind-toggle")); // turn remind on
    await waitFor(() => expect(screen.getByTestId("nrem-5-remind-channel")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("nrem-5-remind-channel"), { target: { value: "email" } });
    fireEvent.click(screen.getByTestId("note-remind-save-5"));
    await waitFor(() => expect(updateTracingNote).toHaveBeenCalled());
    const [id, body] = updateTracingNote.mock.calls[0];
    expect(id).toBe("5");
    expect(body.remindAt).toBe("07:00");
    expect(body.remindRepeat).toBe("daily");
    expect(body.remindChannel).toBe("email");
  });

  it("no notes → honest empty", async () => {
    getTracingNotes.mockResolvedValue(NOTES([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("notes-empty")).toBeInTheDocument());
  });

  it("notes load error → honest error, does NOT break the page (timeline still renders)", async () => {
    getTracingNotes.mockRejectedValue(new Error("notes down"));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("notes-load-error")).toBeInTheDocument());
    expect(screen.getByTestId("tracing-timeline")).toBeInTheDocument();
  });
});

describe("#125 Tracing — note ONE-SHOT future-date remind", () => {
  it("one-shot kind: pick a FUTURE date + time → body has remindDate (repeat stays off)", async () => {
    createTracingNote.mockResolvedValue({ success: true, data: NOTE({ id: "9", remindAt: "09:00", remindDate: "2030-01-01" }) });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "deploy 1/1");
    await user.click(screen.getByTestId("note-remind-toggle"));
    // switch to the one-shot kind, then set a future date
    await user.click(screen.getByTestId("note-kind-once"));
    await waitFor(() => expect(screen.getByTestId("note-remind-date")).toBeInTheDocument());
    setDate(screen.getByTestId("note-remind-date") as HTMLInputElement, "2030-01-01");
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(createTracingNote).toHaveBeenCalled());
    const body = createTracingNote.mock.calls[0][0];
    expect(body.remindDate).toBe("2030-01-01");
    expect(body.remindAt).toBe("07:00");
    expect(body.remindRepeat).toBe("off"); // one-shot → not a recurring repeat
  });

  it("recurring kind (default): repeat path unchanged → NO remindDate sent", async () => {
    createTracingNote.mockResolvedValue({ success: true, data: NOTE() });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "uống thuốc");
    await user.click(screen.getByTestId("note-remind-toggle"));
    // default kind = recurring → a repeat select, no date input
    expect(screen.getByTestId("note-remind-repeat")).toBeInTheDocument();
    expect(screen.queryByTestId("note-remind-date")).toBeNull();
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(createTracingNote).toHaveBeenCalled());
    const body = createTracingNote.mock.calls[0][0];
    expect(body.remindDate).toBeNull();           // recurring → no one-shot date
    expect(body.remindRepeat).toBe("daily");
  });

  it("one-shot with NO date picked → client guard error, no POST", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "thiếu ngày");
    await user.click(screen.getByTestId("note-remind-toggle"));
    await user.click(screen.getByTestId("note-kind-once"));
    // clear the auto-filled date so it's blank → the client guard should fire
    setDate(screen.getByTestId("note-remind-date") as HTMLInputElement, "");
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(screen.getByTestId("note-add-error")).toHaveTextContent(/ngày/));
    expect(createTracingNote).not.toHaveBeenCalled();
  });

  it("a PAST date → the BE 422 hint is surfaced honestly (note_remind_in_past)", async () => {
    // the client min= guard stops the UI from picking a past date; the BE is the authority
    // (it 422s note_remind_in_past). This proves the FE SURFACES that 422 message+hint
    // honestly (errText) instead of failing silently. We trigger a valid one-shot submit
    // and mock the BE rejecting it as past.
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    createTracingNote.mockRejectedValue(new (ApiError as any)(422, "remind 2020-01-01 09:00 is in the past", { hint: "a one-shot remindDate+remindAt must be in the FUTURE (VN time)" }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-input")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.type(screen.getByTestId("note-input"), "quá khứ");
    await user.click(screen.getByTestId("note-remind-toggle"));
    await user.click(screen.getByTestId("note-kind-once"));
    setDate(screen.getByTestId("note-remind-date") as HTMLInputElement, "2030-01-01"); // valid date; BE mock rejects
    await user.click(screen.getByTestId("note-submit"));
    await waitFor(() => expect(screen.getByTestId("note-add-error")).toHaveTextContent(/in the past/));
    expect(screen.getByTestId("note-add-error")).toHaveTextContent(/FUTURE/); // the hint, surfaced
  });

  it("a one-shot note renders a date chip (date @ time), not a recurring chip", async () => {
    getTracingNotes.mockResolvedValue(NOTES([NOTE({ id: "5", remindAt: "09:00", remindDate: "2030-01-01", remindRepeat: "off" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-remind-5")).toBeInTheDocument());
    expect(screen.getByTestId("note-remind-5")).toHaveTextContent("2030-01-01");
    expect(screen.getByTestId("note-remind-5")).toHaveTextContent("09:00");
    expect(screen.getByTestId("note-remind-5")).not.toHaveTextContent(/hằng ngày/);
  });

  it("🔴 the ACTIVITY (todo) remind has NO one-shot date — activity stays daily-recurring", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    render(<TracingPage />);
    // #136 — the add-todo remind is always visible (no global edit toggle)
    await waitFor(() => expect(screen.getByTestId("todo-remind-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("todo-remind-toggle"));
    // the todo remind has a repeat select but NO kind segment / date input (#125 = note-only)
    expect(screen.getByTestId("todo-remind-repeat")).toBeInTheDocument();
    expect(screen.queryByTestId("todo-kind-once")).toBeNull();
    expect(screen.queryByTestId("todo-remind-date")).toBeNull();
  });
});

describe("#126 Tracing — defensive (kept from #65)", () => {
  it("loading state", async () => {
    getTracing.mockReturnValue(new Promise(() => {}));
    render(<TracingPage />);
    expect(screen.getByTestId("tracing-loading")).toBeInTheDocument();
    await waitFor(() => expect(getReminderChannels).toHaveBeenCalled());
  });

  it("GET /tracing error → friendly error + retry", async () => {
    getTracing.mockRejectedValue(new Error("tracing 500"));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-error")).toHaveTextContent("tracing 500"));
  });

  it("heatmap renders 84 cells banded by count (kept, render-only)", async () => {
    const hm = Array(84).fill(0); hm[20] = 3;
    getTracing.mockResolvedValue(OVERVIEW([ACT()], { heatmap12w: hm, score: { total: 1, done: 1, pct: 100, timeActive: "", topStreak: 4 } }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument());
    expect(screen.getByTestId("hc-20").getAttribute("data-count")).toBe("3");
    expect(screen.getByTestId("hc-20").getAttribute("style")).toContain("color-mix");
    expect(screen.getByTestId("hc-0").getAttribute("style")).toContain("--bg-3");
  });

  it("streak badge thresholds: ≥7 🔥, ≥3 ✦ (in the collapsed stats)", async () => {
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
