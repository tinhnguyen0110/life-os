import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #31 reminders screen — render + filter + create + tick + overdue-RED + error.
   Mocks the NAMED api fns the hook calls (getReminders/createReminder/tickReminder/
   deleteReminder), NOT apiGet — a named getter reaches a module-internal apiGet a
   top-level mock can't (memory mock-named-getter-not-apiget). Asserts are scoped to
   the row's testid, not a page-wide text query (scope-no-fabrication-asserts-to-element). */
const getReminders = vi.fn();
const createReminder = vi.fn();
const tickReminder = vi.fn();
const deleteReminder = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getReminders: (...a: unknown[]) => getReminders(...a),
    createReminder: (...a: unknown[]) => createReminder(...a),
    tickReminder: (...a: unknown[]) => tickReminder(...a),
    deleteReminder: (...a: unknown[]) => deleteReminder(...a),
  };
});

import RemindersPage from "../page";

afterEach(() => {
  getReminders.mockReset();
  createReminder.mockReset();
  tickReminder.mockReset();
  deleteReminder.mockReset();
});

const REM = (over = {}) => ({
  id: 1,
  title: "Nộp báo cáo thuế",
  note: null,
  due_at: "2030-06-21T09:00:00+00:00",
  repeat: "once",
  re_notify_every: null,
  max_times: 3,
  notified_count: 0,
  last_notified: null,
  done_at: null,
  created: "2026-06-21T08:00:00+00:00",
  overdue: false,
  ...over,
});

const LIST = (reminders: ReturnType<typeof REM>[], over = {}) => ({
  success: true,
  data: {
    reminders,
    count: reminders.length,
    undoneCount: reminders.filter((r) => r.done_at == null).length,
    filter: "undone",
    ...over,
  },
});

describe("#31 Reminders — render + list", () => {
  it("renders the screen + a reminder row with its title (scoped to row testid)", async () => {
    getReminders.mockResolvedValue(LIST([REM()]));
    render(<RemindersPage />);
    await waitFor(() => expect(screen.getByTestId("reminders-screen")).toBeInTheDocument());
    const row = await screen.findByTestId("rem-1");
    expect(within(row).getByTestId("rem-title-1")).toHaveTextContent("Nộp báo cáo thuế");
  });

  it("#76 a11y: filter tabs are keyboard-ACTIVATABLE (focus + Enter switches filter) — they are real <button>s, not onClick-only spans", async () => {
    getReminders.mockResolvedValue(LIST([REM()]));
    const user = userEvent.setup();
    render(<RemindersPage />);
    const todayTab = await screen.findByTestId("tab-today");
    // it's a real button (keyboard-activatable natively) — NOT a span/div
    expect(todayTab.tagName).toBe("BUTTON");
    getReminders.mockClear();
    // focus it + press Enter → the filter switches (a span onClick would NOT fire on Enter)
    todayTab.focus();
    expect(todayTab).toHaveFocus();
    await user.keyboard("{Enter}");
    // switching to "today" re-fetches with the today server filter (the distinguishing effect)
    await waitFor(() => expect(getReminders).toHaveBeenCalledWith("today"));
  });

  it("empty list → inviting empty state (heading + copy + CTA opens form), no fabricated rows", async () => {
    const user = userEvent.setup();
    getReminders.mockResolvedValue(LIST([]));
    render(<RemindersPage />);
    await waitFor(() => expect(screen.getByTestId("reminders-empty")).toBeInTheDocument());
    // #153-R1: the bare stub is replaced by an inviting empty-state — keeps the tab-aware copy
    expect(screen.getByTestId("reminders-empty")).toHaveTextContent(/Không có nhắc nhở/);
    // a non-done tab (default "undone") gets a CTA that opens the create form
    expect(screen.queryByTestId("reminder-create-form")).toBeNull();
    await user.click(screen.getByTestId("reminders-empty-cta"));
    expect(screen.getByTestId("reminder-create-form")).toBeInTheDocument();
  });

  it("loading state shows while the fetch is pending", async () => {
    let resolve!: (v: unknown) => void;
    getReminders.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<RemindersPage />);
    expect(screen.getByTestId("reminders-loading")).toBeInTheDocument();
    resolve(LIST([]));
    await waitFor(() => expect(screen.queryByTestId("reminders-loading")).toBeNull());
  });

  it("error state surfaces the message + a retry", async () => {
    getReminders.mockRejectedValue(new Error("boom"));
    render(<RemindersPage />);
    await waitFor(() => expect(screen.getByTestId("reminders-error")).toBeInTheDocument());
    expect(screen.getByTestId("reminders-error")).toHaveTextContent("boom");
  });
});

describe("#31 Reminders — overdue RED (the distinguishing case)", () => {
  it("an overdue (un-done & past-due) row carries the .overdue class; a future one does NOT", async () => {
    getReminders.mockResolvedValue(
      LIST([
        REM({ id: 10, title: "QUÁ HẠN", due_at: "2020-01-01T00:00:00+00:00", overdue: true }),
        REM({ id: 11, title: "TƯƠNG LAI", due_at: "2030-01-01T00:00:00+00:00", overdue: false }),
      ]),
    );
    render(<RemindersPage />);
    const overdueRow = await screen.findByTestId("rem-10");
    const futureRow = await screen.findByTestId("rem-11");
    // overdue boolean → .overdue class + data-overdue attr; NOT an FE date-compare.
    expect(overdueRow.className).toContain("overdue");
    expect(overdueRow).toHaveAttribute("data-overdue", "true");
    expect(futureRow.className).not.toContain("overdue");
    expect(futureRow).toHaveAttribute("data-overdue", "false");
    // the overdue row labels itself
    expect(within(overdueRow).getByTestId("rem-due-10")).toHaveTextContent(/quá hạn/);
  });
});

describe("#31 Reminders — create (fail-closed) + tick", () => {
  it("create: submit → calls createReminder with the typed fields → form closes + refetch", async () => {
    getReminders.mockResolvedValue(LIST([]));
    createReminder.mockResolvedValue({ success: true, data: REM({ id: 2, title: "Gọi bác sĩ" }) });
    const user = userEvent.setup();
    render(<RemindersPage />);
    await waitFor(() => expect(screen.getByTestId("reminders-empty")).toBeInTheDocument());

    await user.click(screen.getByTestId("reminder-new"));
    await user.type(screen.getByTestId("c-title"), "Gọi bác sĩ");
    // datetime-local needs a full value
    const due = screen.getByTestId("c-due") as HTMLInputElement;
    await user.clear(due);
    await user.type(due, "2030-06-21T09:00");
    await user.click(screen.getByTestId("c-submit"));

    await waitFor(() => expect(createReminder).toHaveBeenCalledTimes(1));
    const body = createReminder.mock.calls[0][0];
    expect(body.title).toBe("Gọi bác sĩ");
    expect(body.due_at).toBe("2030-06-21T09:00");
    expect(body.repeat).toBe("once");
    expect(body.max_times).toBe(3);
    // form closes on success
    await waitFor(() => expect(screen.queryByTestId("reminder-create-form")).toBeNull());
  });

  it("create: blank title → validation error VISIBLE, createReminder NOT called", async () => {
    getReminders.mockResolvedValue(LIST([]));
    const user = userEvent.setup();
    render(<RemindersPage />);
    await waitFor(() => expect(screen.getByTestId("reminders-empty")).toBeInTheDocument());
    await user.click(screen.getByTestId("reminder-new"));
    await user.click(screen.getByTestId("c-submit"));
    expect(screen.getByTestId("create-error")).toHaveTextContent(/Cần tiêu đề/);
    expect(createReminder).not.toHaveBeenCalled();
  });

  it("create: a 422 from the server surfaces VISIBLY (swallowed-422 guard), form stays open", async () => {
    getReminders.mockResolvedValue(LIST([]));
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    createReminder.mockRejectedValue(new ApiError(422, "due_at: must be a non-empty ISO-8601 datetime"));
    const user = userEvent.setup();
    render(<RemindersPage />);
    await waitFor(() => expect(screen.getByTestId("reminders-empty")).toBeInTheDocument());
    await user.click(screen.getByTestId("reminder-new"));
    await user.type(screen.getByTestId("c-title"), "X");
    const due = screen.getByTestId("c-due") as HTMLInputElement;
    await user.clear(due);
    await user.type(due, "2030-06-21T09:00");
    await user.click(screen.getByTestId("c-submit"));
    await waitFor(() => expect(screen.getByTestId("create-error")).toHaveTextContent(/ISO-8601/));
    expect(screen.getByTestId("reminder-create-form")).toBeInTheDocument(); // stays open
  });

  it("tick: clicking ✓ Xong calls tickReminder(id) (idempotent done)", async () => {
    getReminders.mockResolvedValue(LIST([REM({ id: 5 })]));
    tickReminder.mockResolvedValue({ success: true, data: REM({ id: 5, done_at: "2026-06-21T10:00:00+00:00", overdue: false }) });
    const user = userEvent.setup();
    render(<RemindersPage />);
    await user.click(await screen.findByTestId("tick-5"));
    await waitFor(() => expect(tickReminder).toHaveBeenCalledWith(5));
  });

  it("tick error surfaces in a row-level message (fail-closed, not silent)", async () => {
    getReminders.mockResolvedValue(LIST([REM({ id: 6 })]));
    tickReminder.mockRejectedValue(new Error("network down"));
    const user = userEvent.setup();
    render(<RemindersPage />);
    await user.click(await screen.findByTestId("tick-6"));
    await waitFor(() => expect(screen.getByTestId("row-error")).toHaveTextContent("network down"));
  });
});

describe("#31 Reminders — done tab (render-only client filter, no server `done` filter)", () => {
  it("Done tab shows only done_at != null rows (subsets the fetched `all`)", async () => {
    getReminders.mockResolvedValue(
      LIST([
        REM({ id: 20, title: "ĐÃ XONG", done_at: "2026-06-21T10:00:00+00:00" }),
        REM({ id: 21, title: "CHƯA XONG", done_at: null }),
      ]),
    );
    const user = userEvent.setup();
    render(<RemindersPage />);
    await screen.findByTestId("rem-20");
    await user.click(screen.getByTestId("tab-done"));
    await waitFor(() => expect(screen.queryByTestId("rem-21")).toBeNull());
    expect(screen.getByTestId("rem-20")).toBeInTheDocument();
    // the done row is de-emphasized + shows a done badge
    expect(screen.getByTestId("done-badge-20")).toBeInTheDocument();
  });

  it("Done tab orders most-recently-completed FIRST (done_at DESC — team-lead refinement)", async () => {
    getReminders.mockResolvedValue(
      LIST([
        REM({ id: 30, title: "XONG CŨ", done_at: "2026-06-20T08:00:00+00:00" }),
        REM({ id: 31, title: "XONG MỚI", done_at: "2026-06-21T08:00:00+00:00" }),
        REM({ id: 32, title: "XONG GIỮA", done_at: "2026-06-20T20:00:00+00:00" }),
      ]),
    );
    const user = userEvent.setup();
    render(<RemindersPage />);
    await screen.findByTestId("rem-30");
    await user.click(screen.getByTestId("tab-done"));
    await waitFor(() => expect(screen.getByTestId("rem-31")).toBeInTheDocument());
    // DOM order of the rows = newest done_at first: 31 (06-21) → 32 (06-20 20:00) → 30 (06-20 08:00)
    const list = screen.getByTestId("reminders-list");
    const ids = Array.from(list.querySelectorAll<HTMLElement>('[data-testid^="rem-title-"]')).map(
      (el) => el.getAttribute("data-testid"),
    );
    expect(ids).toEqual(["rem-title-31", "rem-title-32", "rem-title-30"]);
  });
});

describe("#75 Reminders — source badge (from-habit, honest)", () => {
  it("source='tracing' → '📿 từ thói quen' badge renders (with the activity link in the title)", async () => {
    getReminders.mockResolvedValue(LIST([REM({ id: 1, source: "tracing", activity_id: "run" })]));
    render(<RemindersPage />);
    const badge = await screen.findByTestId("rem-source-1");
    expect(badge).toHaveTextContent(/từ thói quen/);
    expect(badge.getAttribute("title")).toMatch(/run/); // links to the activity
  });

  it("source='manual' → NO badge (honest — don't badge a manual reminder)", async () => {
    getReminders.mockResolvedValue(LIST([REM({ id: 2, source: "manual" })]));
    render(<RemindersPage />);
    await screen.findByTestId("rem-2");
    expect(screen.queryByTestId("rem-source-2")).toBeNull();
  });

  it("defensive: source ABSENT (pre-#75-BE backend) → NO badge, no crash (treated as manual)", async () => {
    getReminders.mockResolvedValue(LIST([REM({ id: 3 })])); // no source field
    render(<RemindersPage />);
    await screen.findByTestId("rem-3");
    expect(screen.queryByTestId("rem-source-3")).toBeNull();
  });
});
