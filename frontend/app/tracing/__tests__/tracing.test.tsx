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
});
afterEach(() => {
  getTracing.mockReset(); logTracingSession.mockReset(); createActivity.mockReset();
  archiveActivity.mockReset(); getReminderChannels.mockReset();
  getTracingNotes.mockReset(); createTracingNote.mockReset(); updateTracingNote.mockReset();
  deleteTracingNote.mockReset(); getTracingTemplates.mockReset();
  addTemplateToToday.mockReset(); addAllTemplates.mockReset(); cleanup();
});

describe("#126 Tracing — timeline read-view (default) + edit toggle", () => {
  it("DEFAULT = the timeline rail (read-only); the edit add-tools are HIDDEN until Sửa", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("timeline-rail")).toBeInTheDocument());
    expect(screen.getByTestId("tracing-timeline")).toBeInTheDocument();
    // read-mode: no add-input, no template button
    expect(screen.queryByTestId("todo-input")).toBeNull();
    expect(screen.queryByTestId("tpl-open")).toBeNull();
    // the edit toggle is present + says "Sửa"
    expect(screen.getByTestId("edit-toggle")).toHaveTextContent(/Sửa/);
  });

  it("clicking Sửa → edit-mode: add-input + '+ Từ mẫu' appear; toggle says Xong", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("edit-toggle"));
    expect(screen.getByTestId("todo-input")).toBeInTheDocument();
    expect(screen.getByTestId("tpl-open")).toBeInTheDocument();
    expect(screen.getByTestId("edit-toggle")).toHaveTextContent(/Xong/);
  });

  it("the timeline orders TIMED activities by remindAt, then un-timed under 'CẢ NGÀY'", async () => {
    getTracing.mockResolvedValue(OVERVIEW([
      ACT({ id: "anytime", name: "Bất kỳ", remindAt: null }),
      ACT({ id: "late", name: "Tối", remindAt: "21:00", remindRepeat: "daily" }),
      ACT({ id: "early", name: "Sáng", remindAt: "06:00", remindRepeat: "daily" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-early")).toBeInTheDocument());
    const order = screen.getAllByTestId(/^tl-(early|late|anytime)$/).map((r) => r.getAttribute("data-testid"));
    expect(order).toEqual(["tl-early", "tl-late", "tl-anytime"]); // 06:00 < 21:00 < anytime
    expect(screen.getByTestId("timeline-anytime-sep")).toBeInTheDocument();
    expect(screen.getByTestId("tl-time-early")).toHaveTextContent("06:00");
    expect(screen.getByTestId("tl-time-anytime")).toHaveTextContent("—"); // no fixed time
  });

  it("streak + heatmap KEPT (collapsed <details>) — base preserved", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-stats")).toBeInTheDocument());
    expect(screen.getByTestId("tracing-stats").tagName.toLowerCase()).toBe("details");
    expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument();
  });
});

describe("#126 Tracing — tick is 1-click IN READ MODE (not gated behind edit)", () => {
  it("ticking an undone todo in read-mode → log(id, {val:1}); no edit needed", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", today: { done: false, val: 0, dur: "", durMin: 0, note: null, pct: 0, sessions: 0 } })]));
    logTracingSession.mockResolvedValue({ success: true, data: ACT() });
    render(<TracingPage />);
    // do NOT enter edit-mode
    await waitFor(() => expect(screen.getByTestId("tick-water")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("tick-water"));
    await waitFor(() => expect(logTracingSession).toHaveBeenCalledWith("water", expect.objectContaining({ val: 1 })));
  });

  it("a DONE todo → checked tick, line-through name, not re-loggable", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water", today: { done: true, val: 1, dur: "", durMin: 0, note: null, pct: 100, sessions: 1 } })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    expect(screen.getByTestId("tl-water")).toHaveAttribute("data-done", "true");
    expect(screen.getByTestId("tick-water")).toBeDisabled();
    await userEvent.setup().click(screen.getByTestId("tick-water"));
    expect(logTracingSession).not.toHaveBeenCalled();
  });

  it("a timed todo shows its remind chip in the rail", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "run", name: "Chạy bộ", remindAt: "06:30", remindRepeat: "daily" })]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-remind-run")).toBeInTheDocument());
    expect(screen.getByTestId("tl-remind-run")).toHaveTextContent("06:30");
  });

  it("archive ✕ appears only in EDIT-mode → archiveActivity(id)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "water" })]));
    archiveActivity.mockResolvedValue({ success: true, data: { archived: "water" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tl-water")).toBeInTheDocument());
    expect(screen.queryByTestId("tl-archive-water")).toBeNull(); // hidden in read-mode
    await userEvent.setup().click(screen.getByTestId("edit-toggle"));
    await userEvent.setup().click(screen.getByTestId("tl-archive-water"));
    await waitFor(() => expect(archiveActivity).toHaveBeenCalledWith("water"));
  });

  it("empty board → honest timeline-empty", async () => {
    getTracing.mockResolvedValue(OVERVIEW([]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("timeline-empty")).toBeInTheDocument());
  });
});

describe("#126 Tracing — add-todo (edit-mode) → createActivity(goal:1) [base kept]", () => {
  it("add-via-text → createActivity(text, goal:1, slug id)", async () => {
    createActivity.mockResolvedValue({ success: true, data: { id: "uong-nuoc" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("edit-toggle"));
    await user.type(screen.getByTestId("todo-input"), "Uống nước");
    await user.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.name).toBe("Uống nước");
    expect(body.goal).toBe(1);
    expect(body.id).toBe("uong-nuoc");
    expect(body.remindRepeat).toBe("off");
  });

  it("add WITH remind on → sends remindAt + remindRepeat + remindChannel", async () => {
    createActivity.mockResolvedValue({ success: true, data: { id: "tap-the-duc" } });
    render(<TracingPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("edit-toggle"));
    await user.type(screen.getByTestId("todo-input"), "Tập thể dục");
    await user.click(screen.getByTestId("todo-remind-toggle"));
    await waitFor(() => expect(screen.getByTestId("todo-remind-channel")).toBeInTheDocument());
    await user.selectOptions(screen.getByTestId("todo-remind-channel"), "discord");
    await user.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.remindAt).toBe("07:00");
    expect(body.remindRepeat).toBe("daily");
    expect(body.remindChannel).toBe("discord");
  });

  it("blank text → validation error, no POST", async () => {
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("edit-toggle"));
    await user.click(screen.getByTestId("todo-submit"));
    await waitFor(() => expect(screen.getByTestId("todo-add-error")).toBeInTheDocument());
    expect(createActivity).not.toHaveBeenCalled();
  });
});

describe("#126 Tracing — '+ Từ mẫu' template picker (#124)", () => {
  it("opens the picker, lists templates, adds one → addTemplateToToday(id) + refetch", async () => {
    getTracingTemplates.mockResolvedValue({ success: true, data: { templates: [TPL({ id: "ngu", name: "Ngủ đủ giấc" })] } });
    addTemplateToToday.mockResolvedValue({ success: true, data: { activity: { id: "ngu", name: "Ngủ đủ giấc", goal: 1 }, added: true } });
    render(<TracingPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("edit-toggle"));
    await user.click(screen.getByTestId("tpl-open"));
    await waitFor(() => expect(screen.getByTestId("tpl-ngu")).toBeInTheDocument());
    await user.click(screen.getByTestId("tpl-ngu"));
    await waitFor(() => expect(addTemplateToToday).toHaveBeenCalledWith("ngu"));
  });

  it("'Thêm tất cả' → addAllTemplates()", async () => {
    addAllTemplates.mockResolvedValue({ success: true, data: { created: [], skipped: [] } });
    render(<TracingPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("edit-toggle"));
    await user.click(screen.getByTestId("tpl-open"));
    await waitFor(() => expect(screen.getByTestId("tpl-add-all")).toBeInTheDocument());
    await user.click(screen.getByTestId("tpl-add-all"));
    await waitFor(() => expect(addAllTemplates).toHaveBeenCalled());
  });

  it("template load error → honest error (no crash)", async () => {
    getTracingTemplates.mockRejectedValue(new Error("templates down"));
    render(<TracingPage />);
    const user = userEvent.setup();
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("edit-toggle"));
    await user.click(screen.getByTestId("tpl-open"));
    await waitFor(() => expect(screen.getByTestId("tpl-error")).toBeInTheDocument());
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
      NOTE({ id: "2", text: "ghi chú hai", remindAt: "21:00", remindRepeat: "daily" }),
      NOTE({ id: "3", text: "ghi chú ba" }),
    ]));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-1")).toBeInTheDocument());
    expect(screen.getByTestId("note-2")).toBeInTheDocument();
    expect(screen.getByTestId("note-3")).toBeInTheDocument();
    expect(screen.getByTestId("note-text-1")).toHaveTextContent("ghi chú một");
    expect(screen.getByTestId("note-remind-2")).toHaveTextContent("21:00");
    expect(screen.queryByTestId("note-remind-1")).toBeNull(); // no remind → no chip
    expect(screen.getByTestId("note-delete-3")).toBeInTheDocument();
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

  it("delete a note → deleteTracingNote(id)", async () => {
    getTracingNotes.mockResolvedValue(NOTES([NOTE({ id: "7", text: "xóa tôi" })]));
    deleteTracingNote.mockResolvedValue({ success: true, data: { deleted: "7" } });
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("note-delete-7")).toBeInTheDocument());
    await userEvent.setup().click(screen.getByTestId("note-delete-7"));
    await waitFor(() => expect(deleteTracingNote).toHaveBeenCalledWith("7"));
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
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("edit-toggle")).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(screen.getByTestId("edit-toggle"));
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
