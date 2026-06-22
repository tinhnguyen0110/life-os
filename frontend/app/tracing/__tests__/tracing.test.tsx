import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #65-P3 Daily Tracing screen — render + empty + streak-badge thresholds + heatmap
   + log round-trip + agent-error display. Mocks the NAMED api fns the hook calls
   (mock-named-getter-not-apiget). Asserts scoped to testids
   (scope-no-fabrication-asserts-to-element). Steady-state fetches use
   mockResolvedValue (NOT ...Once) so a refetch after a write doesn't exhaust the
   queue → undefined → unhandled rejection (unhandled-errors-not-green). */
const getTracing = vi.fn();
const logTracingSession = vi.fn();
const createActivity = vi.fn();
const archiveActivity = vi.fn();
const getReminderChannels = vi.fn();
const getTracingTemplates = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getTracing: (...a: unknown[]) => getTracing(...a),
    logTracingSession: (...a: unknown[]) => logTracingSession(...a),
    createActivity: (...a: unknown[]) => createActivity(...a),
    archiveActivity: (...a: unknown[]) => archiveActivity(...a),
    getReminderChannels: (...a: unknown[]) => getReminderChannels(...a),
    getTracingTemplates: (...a: unknown[]) => getTracingTemplates(...a),
  };
});

import TracingPage from "../page";

// default the #111 channels + #109 templates so the form renders deterministically.
const CHANNELS_OK = { success: true, data: { channels: [
  { id: "in_app", label: "In-app", available: true },
  { id: "email", label: "Email", available: true },
  { id: "discord", label: "Discord", available: true },
] } };
beforeEach(() => {
  getReminderChannels.mockResolvedValue(CHANNELS_OK);
  getTracingTemplates.mockResolvedValue({ success: true, data: { templates: [] } });
});

afterEach(() => {
  getTracing.mockReset();
  logTracingSession.mockReset();
  createActivity.mockReset();
  archiveActivity.mockReset();
  getReminderChannels.mockReset();
  getTracingTemplates.mockReset();
});

const ACT = (over = {}) => ({
  id: "water",
  name: "Uống nước",
  emoji: "💧",
  icon: "",
  unit: "ly",
  goal: 8,
  color: "#4ea0ff",
  today: { done: false, val: 3, dur: "5m", durMin: 5, note: "sáng", pct: 38, sessions: 1 },
  streak: 0,
  week: [0, 0, 0, 0, 0, 0, 3],
  history12w: Array(84).fill(0),
  ...over,
});

const OVERVIEW = (acts = [ACT()], over = {}) => ({
  success: true,
  data: {
    date: "2026-06-21",
    activities: acts,
    heatmap12w: Array(84).fill(0),
    score: { total: acts.length, done: 0, pct: 0, timeActive: "5m", topStreak: 0 },
    ...over,
  },
});

describe("#65-P3 Tracing — render + score", () => {
  it("renders the screen + score KPI strip from backend (render-only)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()], { score: { total: 3, done: 2, pct: 67, timeActive: "1h 20m", topStreak: 9 } }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-score")).toBeInTheDocument());
    const sc = screen.getByTestId("tracing-score");
    expect(sc).toHaveTextContent("1h 20m"); // timeActive
    expect(sc).toHaveTextContent("9"); // topStreak
    expect(sc).toHaveTextContent("67%"); // pct
  });

  it("honest-empty: 0 activities → empty-state (NOT blank/crash)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([], { score: { total: 0, done: 0, pct: 0, timeActive: "", topStreak: 0 } }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-empty")).toBeInTheDocument());
    expect(screen.getByTestId("tracing-empty")).toHaveTextContent(/Chưa có hoạt động nào/);
    expect(screen.getByTestId("empty-add")).toBeInTheDocument();
  });

  it("loading + error states", async () => {
    getTracing.mockRejectedValue(new Error("boom"));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("tracing-error")).toHaveTextContent("boom"));
  });
});

describe("#65-P3 Tracing — activity card", () => {
  it("renders a card with name, today val, pct (render-only)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    render(<TracingPage />);
    const card = await screen.findByTestId("act-water");
    expect(within(card).getByText("Uống nước")).toBeInTheDocument();
    expect(card).toHaveTextContent("3 ly");
    expect(card).toHaveTextContent("38%");
  });

  it("streak badge thresholds: 🔥 ≥7, ✦ ≥3, none <3 (ported EXACTLY — distinguishing)", async () => {
    getTracing.mockResolvedValue(
      OVERVIEW([
        ACT({ id: "fire", name: "Fire", streak: 7 }),
        ACT({ id: "star", name: "Star", streak: 3 }),
        ACT({ id: "none", name: "None", streak: 2 }),
      ]),
    );
    render(<TracingPage />);
    await screen.findByTestId("act-fire");
    // the badge span shows "ngày <badge>" — distinguishing the 3 thresholds
    expect(screen.getByTestId("badge-fire")).toHaveTextContent("🔥");
    expect(screen.getByTestId("badge-star")).toHaveTextContent("✦");
    expect(screen.getByTestId("badge-none")).toHaveTextContent(/ngày\s*$/); // no badge char
    expect(screen.getByTestId("badge-none")).not.toHaveTextContent("🔥");
    expect(screen.getByTestId("badge-none")).not.toHaveTextContent("✦");
  });

  it("boundary: streak 6 → ✦ (not 🔥), streak 3 → ✦, streak 2 → none", async () => {
    getTracing.mockResolvedValue(
      OVERVIEW([ACT({ id: "six", streak: 6 }), ACT({ id: "three", streak: 3 }), ACT({ id: "two", streak: 2 })]),
    );
    render(<TracingPage />);
    await screen.findByTestId("act-six");
    expect(screen.getByTestId("badge-six")).toHaveTextContent("✦");
    expect(screen.getByTestId("badge-six")).not.toHaveTextContent("🔥");
    expect(screen.getByTestId("badge-three")).toHaveTextContent("✦");
    expect(screen.getByTestId("badge-two")).not.toHaveTextContent("✦");
  });
});

describe("#65-P3 Tracing — heatmap", () => {
  it("renders 84 cells; color bands by per-day COUNT (0 = empty, >0 = accent)", async () => {
    const hm = Array(84).fill(0);
    hm[10] = 0; hm[20] = 1; hm[30] = 3; // a few non-zero
    getTracing.mockResolvedValue(OVERVIEW([ACT()], { heatmap12w: hm, score: { total: 3, done: 0, pct: 0, timeActive: "", topStreak: 0 } }));
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("heatmap-grid")).toBeInTheDocument());
    const cells = screen.getByTestId("heatmap-grid").querySelectorAll(".hc");
    expect(cells).toHaveLength(84);
    // a 0-count cell is the empty bg; a >0 cell is accent-tinted (distinguishing)
    const c20 = screen.getByTestId("hc-20");
    const c0 = screen.getByTestId("hc-0");
    expect(c20.getAttribute("data-count")).toBe("1");
    expect(c0.getAttribute("data-count")).toBe("0");
    expect(c20.getAttribute("style")).toContain("color-mix"); // accent band
    expect(c0.getAttribute("style")).toContain("--bg-3"); // empty
  });

  it("a11y: the grid is a labeled role=img + each cell has an aria-label (screen-reader readable)", async () => {
    const hm = Array(84).fill(0);
    hm[5] = 2;
    getTracing.mockResolvedValue(OVERVIEW([ACT()], { heatmap12w: hm, score: { total: 3, done: 0, pct: 0, timeActive: "", topStreak: 0 } }));
    render(<TracingPage />);
    const grid = await screen.findByTestId("heatmap-grid");
    expect(grid).toHaveAttribute("role", "img");
    expect(grid.getAttribute("aria-label")).toMatch(/12 tuần/);
    expect(screen.getByTestId("hc-5")).toHaveAttribute("aria-label", "2 hoạt động đạt");
  });
});

describe("#65-P3 Tracing — log round-trip + errors (fail-closed)", () => {
  it("log: open form → submit → calls logTracingSession(id, {val,...}) + refetch", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    logTracingSession.mockResolvedValue({ success: true, data: ACT({ today: { done: true, val: 8, dur: "10m", durMin: 10, note: null, pct: 100, sessions: 2 }, streak: 1 }) });
    const user = userEvent.setup();
    render(<TracingPage />);
    await user.click(await screen.findByTestId("log-water"));
    await user.type(screen.getByTestId("log-val"), "5");
    await user.type(screen.getByTestId("log-dur"), "10");
    await user.click(screen.getByTestId("log-submit"));
    await waitFor(() => expect(logTracingSession).toHaveBeenCalledTimes(1));
    expect(logTracingSession.mock.calls[0][0]).toBe("water");
    expect(logTracingSession.mock.calls[0][1]).toMatchObject({ val: 5, dur_min: 10 });
    await waitFor(() => expect(screen.queryByTestId("log-form")).toBeNull()); // closes on success
  });

  it("log: negative val → validation error VISIBLE, api NOT called", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    const user = userEvent.setup();
    render(<TracingPage />);
    await user.click(await screen.findByTestId("log-water"));
    await user.type(screen.getByTestId("log-val"), "-3");
    await user.click(screen.getByTestId("log-submit"));
    expect(screen.getByTestId("log-error")).toHaveTextContent(/≥ 0/);
    expect(logTracingSession).not.toHaveBeenCalled();
  });

  it("log: server 422 → the agent_error message + hint shown (not silent)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    logTracingSession.mockRejectedValue(
      new ApiError(422, "request validation failed — body.val: Input should be greater than or equal to 0", { hint: "check the schema" }),
    );
    const user = userEvent.setup();
    render(<TracingPage />);
    await user.click(await screen.findByTestId("log-water"));
    await user.type(screen.getByTestId("log-val"), "1");
    await user.click(screen.getByTestId("log-submit"));
    await waitFor(() => expect(screen.getByTestId("log-error")).toHaveTextContent(/greater than or equal to 0/));
    expect(screen.getByTestId("log-error")).toHaveTextContent(/check the schema/); // hint shown
    expect(screen.getByTestId("log-form")).toBeInTheDocument(); // stays open
  });

  it("add: dup id 409 → the conflict message + hint shown", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    createActivity.mockRejectedValue(new ApiError(409, "activity 'water' already exists", { hint: "use PUT to update, or a new id" }));
    const user = userEvent.setup();
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("add-activity")).toBeInTheDocument());
    await user.click(screen.getByTestId("add-activity"));
    // #110 lean form: id auto-slugs from the name (no a-id field by default)
    await user.type(screen.getByTestId("a-name"), "dup");
    await user.type(screen.getByTestId("a-goal"), "8");
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(screen.getByTestId("add-error")).toHaveTextContent(/already exists/));
    expect(screen.getByTestId("add-error")).toHaveTextContent(/use PUT/); // hint shown
  });

  it("archive: clicking ✕ calls archiveActivity(id)", async () => {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    archiveActivity.mockResolvedValue({ success: true, data: { archived: "water" } });
    const user = userEvent.setup();
    render(<TracingPage />);
    await user.click(await screen.findByTestId("archive-water"));
    await waitFor(() => expect(archiveActivity).toHaveBeenCalledWith("water"));
  });
});

describe("#75 Tracing — habit-reminder toggle (sets remind_at/remind_repeat; BE makes the reminder)", () => {
  async function openAdd() {
    getTracing.mockResolvedValue(OVERVIEW([ACT()]));
    createActivity.mockResolvedValue({ success: true, data: ACT({ id: "run", name: "Run" }) });
    const user = userEvent.setup();
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("add-activity")).toBeInTheDocument());
    await user.click(screen.getByTestId("add-activity"));
    return user;
  }

  it("remind toggle OFF (default) → create sends remind_at null + remind_repeat 'off'", async () => {
    const user = await openAdd();
    // #110 lean form: id auto-slugs from the name ("Run" → "run"); no a-id field by default
    await user.type(screen.getByTestId("a-name"), "Run");
    await user.type(screen.getByTestId("a-goal"), "5");
    // toggle is off by default — the time/repeat inputs are NOT shown
    expect(screen.queryByTestId("a-remind-time")).toBeNull();
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.remindAt).toBeNull();
    expect(body.remindRepeat).toBe("off");
  });

  it("remind toggle ON → time + cadence inputs appear → create sends remind_at + remind_repeat", async () => {
    const user = await openAdd();
    // #110 lean form: id auto-slugs from the name ("Run" → "run")
    await user.type(screen.getByTestId("a-name"), "Run");
    await user.type(screen.getByTestId("a-goal"), "5");
    await user.click(screen.getByTestId("a-remind-toggle"));
    // now the time + repeat inputs are revealed
    const time = screen.getByTestId("a-remind-time") as HTMLInputElement;
    expect(time).toBeInTheDocument();
    await user.clear(time);
    await user.type(time, "07:30");
    await user.selectOptions(screen.getByTestId("a-remind-repeat"), "weekdays");
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    const body = createActivity.mock.calls[0][0];
    expect(body.remindAt).toBe("07:30");
    expect(body.remindRepeat).toBe("weekdays");
  });

  it("card shows the habit's reminder when set (defensive: absent field → no chip)", async () => {
    // with remindAt set → the 🔔 chip renders
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "run", name: "Run", remindAt: "07:00", remindRepeat: "daily" })]));
    const { unmount } = render(<TracingPage />);
    expect(await screen.findByTestId("remind-run")).toHaveTextContent("07:00");
    expect(screen.getByTestId("remind-run")).toHaveTextContent(/hằng ngày/);
    unmount();
    // defensive: pre-#75-BE the field is absent → NO chip, no crash
    getTracing.mockResolvedValue(OVERVIEW([ACT({ id: "run2", name: "Run2" })])); // no remindAt
    render(<TracingPage />);
    await screen.findByTestId("act-run2");
    expect(screen.queryByTestId("remind-run2")).toBeNull();
  });
});

/* ---- #110 lean-form restructure: 3 default fields + Advanced disclosure + auto-slug ---- */
describe("#110 Tracing — lean add form", () => {
  async function openAdd() {
    getTracing.mockResolvedValue(OVERVIEW([]));
    createActivity.mockResolvedValue({ success: true, data: ACT({ id: "uong-nuoc", name: "Uống nước" }) });
    const user = userEvent.setup();
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("add-activity")).toBeInTheDocument());
    await user.click(screen.getByTestId("add-activity"));
    return user;
  }

  it("default shows only Tên + Mục tiêu + Đơn vị — id/emoji/màu are HIDDEN (in Advanced)", async () => {
    await openAdd();
    expect(screen.getByTestId("a-name")).toBeInTheDocument();
    expect(screen.getByTestId("a-goal")).toBeInTheDocument();
    expect(screen.getByTestId("a-unit")).toBeInTheDocument();
    // advanced fields are collapsed by default
    expect(screen.queryByTestId("a-id")).toBeNull();
    expect(screen.queryByTestId("a-emoji")).toBeNull();
    expect(screen.queryByTestId("a-color")).toBeNull();
    expect(screen.getByTestId("a-advanced-toggle")).toBeInTheDocument();
  });

  it("Advanced disclosure expands → id/emoji/màu appear", async () => {
    const user = await openAdd();
    await user.click(screen.getByTestId("a-advanced-toggle"));
    expect(screen.getByTestId("a-advanced")).toBeInTheDocument();
    expect(screen.getByTestId("a-id")).toBeInTheDocument();
    expect(screen.getByTestId("a-emoji")).toBeInTheDocument();
    expect(screen.getByTestId("a-color")).toBeInTheDocument();
  });

  it("id auto-slugs from the name (Vietnamese) — shown as a preview, sent on submit", async () => {
    const user = await openAdd();
    await user.type(screen.getByTestId("a-name"), "Uống nước");
    await user.type(screen.getByTestId("a-goal"), "8");
    // the derived-id preview reflects the slug
    expect(screen.getByTestId("a-id-preview")).toHaveTextContent("uong-nuoc");
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0].id).toBe("uong-nuoc"); // auto-slugged id sent
  });

  it("Advanced id override → idManual, the typed id wins over the name-slug", async () => {
    const user = await openAdd();
    await user.type(screen.getByTestId("a-name"), "Uống nước");
    await user.type(screen.getByTestId("a-goal"), "8");
    await user.click(screen.getByTestId("a-advanced-toggle"));
    const idInput = screen.getByTestId("a-id");
    await user.clear(idInput);
    await user.type(idInput, "my-water");
    // typing more name does NOT clobber the manual id; the preview is gone (manual)
    expect(screen.queryByTestId("a-id-preview")).toBeNull();
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0].id).toBe("my-water"); // manual id wins
  });

  it("submitting with no name → honest error (Cần tên), no API call", async () => {
    const user = await openAdd();
    await user.type(screen.getByTestId("a-goal"), "8");
    await user.click(screen.getByTestId("a-submit"));
    expect(screen.getByTestId("add-error")).toHaveTextContent(/Cần tên/);
    expect(createActivity).not.toHaveBeenCalled();
  });
});

/* ---- #111 channel-select in the reminder block ---- */
describe("#111 Tracing — reminder channel select", () => {
  async function openAdd() {
    getTracing.mockResolvedValue(OVERVIEW([]));
    createActivity.mockResolvedValue({ success: true, data: ACT({ id: "run", name: "Run" }) });
    const user = userEvent.setup();
    render(<TracingPage />);
    await waitFor(() => expect(screen.getByTestId("add-activity")).toBeInTheDocument());
    await user.click(screen.getByTestId("add-activity"));
    return user;
  }

  it("channel select is HIDDEN until the 🔔 toggle is ON", async () => {
    const user = await openAdd();
    expect(screen.queryByTestId("a-remind-channel")).toBeNull();
    await user.click(screen.getByTestId("a-remind-toggle"));
    await waitFor(() => expect(screen.getByTestId("a-remind-channel")).toBeInTheDocument());
  });

  it("shows in_app/email/discord (all available → enabled)", async () => {
    const user = await openAdd();
    await user.click(screen.getByTestId("a-remind-toggle"));
    const sel = await screen.findByTestId("a-remind-channel");
    expect(within(sel).getByTestId("a-channel-opt-in_app")).toBeInTheDocument();
    expect(within(sel).getByTestId("a-channel-opt-email")).toBeInTheDocument();
    expect((within(sel).getByTestId("a-channel-opt-discord") as HTMLOptionElement).disabled).toBe(false);
  });

  it("an UNAVAILABLE channel is disabled + tagged 'chưa cấu hình'", async () => {
    getReminderChannels.mockResolvedValue({ success: true, data: { channels: [
      { id: "in_app", label: "In-app", available: true },
      { id: "discord", label: "Discord", available: false },
    ] } });
    const user = await openAdd();
    await user.click(screen.getByTestId("a-remind-toggle"));
    const disc = await screen.findByTestId("a-channel-opt-discord");
    expect((disc as HTMLOptionElement).disabled).toBe(true);
    expect(disc).toHaveTextContent(/chưa cấu hình/);
  });

  it("picking discord → create sends remindChannel:'discord' (only when toggle ON)", async () => {
    const user = await openAdd();
    await user.type(screen.getByTestId("a-name"), "Run");
    await user.type(screen.getByTestId("a-goal"), "5");
    await user.click(screen.getByTestId("a-remind-toggle"));
    await user.selectOptions(screen.getByTestId("a-remind-channel"), "discord");
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0].remindChannel).toBe("discord");
  });

  it("toggle OFF → create does NOT send a channel (undefined)", async () => {
    const user = await openAdd();
    await user.type(screen.getByTestId("a-name"), "Run");
    await user.type(screen.getByTestId("a-goal"), "5");
    // toggle stays off
    await user.click(screen.getByTestId("a-submit"));
    await waitFor(() => expect(createActivity).toHaveBeenCalled());
    expect(createActivity.mock.calls[0][0].remindChannel).toBeUndefined();
  });

  it("channels API error → fallback to in_app-only (render-safe, form still works)", async () => {
    getReminderChannels.mockRejectedValue(new Error("channels 500"));
    const user = await openAdd();
    await user.click(screen.getByTestId("a-remind-toggle"));
    const sel = await screen.findByTestId("a-remind-channel");
    // only in_app present (fallback), email/discord absent — form not blocked
    expect(within(sel).getByTestId("a-channel-opt-in_app")).toBeInTheDocument();
    expect(within(sel).queryByTestId("a-channel-opt-discord")).toBeNull();
  });
});
