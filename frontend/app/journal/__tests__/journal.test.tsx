import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getJournal = vi.fn();
const createJournal = vi.fn();
const updateJournal = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getJournal: () => getJournal(), createJournal: (...a: unknown[]) => createJournal(...a), updateJournal: (...a: unknown[]) => updateJournal(...a) };
});

import JournalPage from "../page";

afterEach(() => { getJournal.mockReset(); createJournal.mockReset(); updateJournal.mockReset(); });

const ENTRY = (over = {}) => ({
  id: "e1", date: "2026-06-05T10:00:00Z", action: "BUY", asset: "BTC", size: "$2,000", px: "$68,240",
  tag: "ladder", reason: "rung 2 ladder", channel: "crypto", thesis: null, negationCondition: null,
  confidence: 70, pnl: null, outcome: "open", lesson: null, createdAt: "2026-06-05T10:00:00Z", updatedAt: "2026-06-05T10:00:00Z", ...over,
});
const STATS = (over = {}) => ({
  success: true,
  data: {
    entries: [ENTRY()], count: 1, winRate: 72, avgPnl: 6.8, ladderDiscipline: 94,
    thisMonth: { total: 5, buy: 3, sell: 1, ladder: 1 },
    calibration: [{ band: "70-80", predicted: 75, actual: 80, n: 4 }],
    ...over,
  },
});

describe("S7 Journal — render + filter", () => {
  it("renders 4 stat cards (render-only)", async () => {
    getJournal.mockResolvedValueOnce(STATS());
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-stats")).toBeInTheDocument());
    expect(screen.getByTestId("journal-stats")).toHaveTextContent("72%"); // winRate
    expect(screen.getByTestId("journal-stats")).toHaveTextContent("+6.8%"); // avgPnl
    expect(screen.getByTestId("journal-stats")).toHaveTextContent("94%"); // ladder
    expect(screen.getByTestId("journal-stats")).toHaveTextContent(/3 mua · 1 bán · 1 ladder/);
  });

  it("null stats → '—' (never fabricated)", async () => {
    getJournal.mockResolvedValueOnce(STATS({ winRate: null, avgPnl: null, ladderDiscipline: null }));
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-stats")).toBeInTheDocument());
    expect(screen.getByTestId("journal-stats")).toHaveTextContent("—");
  });

  it("renders trade-log row with action chip + open pnl 'mở'", async () => {
    getJournal.mockResolvedValueOnce(STATS());
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByText("BTC")).toBeInTheDocument());
    expect(screen.getByText("BUY")).toBeInTheDocument();
    expect(screen.getByText("mở")).toBeInTheDocument(); // null pnl → "mở"
  });

  it("tab filter (Ladder) shows only ladder-tagged", async () => {
    getJournal.mockResolvedValueOnce(STATS({ entries: [ENTRY({ id: "a", asset: "BTC", tag: "ladder" }), ENTRY({ id: "b", asset: "ETH", tag: "value" })], count: 2 }));
    const user = userEvent.setup();
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByText("BTC")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-ladder"));
    await waitFor(() => expect(screen.queryByText("ETH")).toBeNull());
    expect(screen.getByText("BTC")).toBeInTheDocument();
  });

  it("calibration panel renders bands + low-n (n<3) noise caveat", async () => {
    getJournal.mockResolvedValueOnce(STATS({ calibration: [{ band: "70-80", predicted: 75, actual: 80, n: 1 }] }));
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-calibration")).toBeInTheDocument());
    expect(screen.getByTestId("calib-70-80")).toHaveTextContent("70-80% (n=1 ⚠)"); // low-n marked
    expect(screen.getByTestId("calib-lown-note")).toHaveTextContent(/nhiễu thống kê/);
  });

  it("calibration high-n band → no noise caveat", async () => {
    getJournal.mockResolvedValueOnce(STATS({ calibration: [{ band: "70-80", predicted: 75, actual: 80, n: 8 }] }));
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("calib-70-80")).toBeInTheDocument());
    expect(screen.getByTestId("calib-70-80")).toHaveTextContent("(n=8)");
    expect(screen.queryByTestId("calib-lown-note")).toBeNull();
  });

  it("calibration empty → 'chưa đủ dữ liệu' (never fabricate a curve)", async () => {
    getJournal.mockResolvedValueOnce(STATS({ calibration: [] }));
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("calib-empty")).toHaveTextContent(/Chưa đủ dữ liệu để hiệu chỉnh/));
  });

  it("ladder stat labeled honestly (% ladder-tagged, NOT plan-adherence)", async () => {
    getJournal.mockResolvedValueOnce(STATS());
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-stats")).toBeInTheDocument());
    expect(screen.getByTestId("journal-stats")).toHaveTextContent(/% lệnh gắn tag "ladder"/);
    expect(screen.getByTestId("journal-stats")).not.toHaveTextContent(/theo đúng kế hoạch/);
  });

  it("GET error → friendly error", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getJournal.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-error")).toBeInTheDocument());
  });

  it("TEETH: malformed body → error, no crash", async () => {
    getJournal.mockResolvedValueOnce(undefined);
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-error")).toBeInTheDocument());
  });
});

describe("S7 Journal — write (create/close) + fail-closed teeth", () => {
  it("create: posts decision fields (thesis/confidence/channel)", async () => {
    getJournal.mockResolvedValue(STATS({ entries: [], count: 0 }));
    createJournal.mockResolvedValueOnce({ success: true, data: ENTRY() });
    const user = userEvent.setup();
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("journal-new")).toBeInTheDocument());
    await user.click(screen.getByTestId("journal-new"));
    await user.type(screen.getByTestId("c-asset"), "SOL");
    await user.type(screen.getByTestId("c-reason"), "breakout");
    await user.type(screen.getByTestId("c-confidence"), "65");
    await user.selectOptions(screen.getByTestId("c-channel"), "crypto");
    await user.click(screen.getByTestId("c-submit"));
    await waitFor(() => expect(createJournal).toHaveBeenCalledWith(expect.objectContaining({ asset: "SOL", reason: "breakout", confidence: 65, channel: "crypto" })));
  });

  it("create: confidence out of 0-100 → validation error, no POST", async () => {
    getJournal.mockResolvedValue(STATS({ entries: [], count: 0 }));
    const user = userEvent.setup();
    render(<JournalPage />);
    await user.click(screen.getByTestId("journal-new"));
    await user.type(screen.getByTestId("c-asset"), "X");
    await user.type(screen.getByTestId("c-reason"), "r");
    await user.type(screen.getByTestId("c-confidence"), "150");
    await user.click(screen.getByTestId("c-submit"));
    expect(screen.getByTestId("create-error")).toHaveTextContent(/0.100|0–100/);
    expect(createJournal).not.toHaveBeenCalled();
  });

  it("close: open entry → PUT with pnl/outcome/lesson", async () => {
    getJournal.mockResolvedValue(STATS());
    updateJournal.mockResolvedValueOnce({ success: true, data: ENTRY({ pnl: "+5.5%", outcome: "right" }) });
    const user = userEvent.setup();
    render(<JournalPage />);
    await waitFor(() => expect(screen.getByTestId("close-e1")).toBeInTheDocument());
    await user.click(screen.getByTestId("close-e1"));
    await user.type(screen.getByTestId("close-pnl"), "+5.5%");
    await user.click(screen.getByTestId("close-submit"));
    await waitFor(() => expect(updateJournal).toHaveBeenCalledWith("e1", expect.objectContaining({ pnl: "+5.5%", outcome: "right" })));
  });

  it("TEETH: create FAILS → error surfaces, form stays open (fail-closed)", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getJournal.mockResolvedValue(STATS({ entries: [], count: 0 }));
    createJournal.mockRejectedValueOnce(new (ApiError as any)(500, "write blew up"));
    const user = userEvent.setup();
    render(<JournalPage />);
    await user.click(screen.getByTestId("journal-new"));
    await user.type(screen.getByTestId("c-asset"), "X");
    await user.type(screen.getByTestId("c-reason"), "r");
    await user.click(screen.getByTestId("c-submit"));
    await waitFor(() => expect(screen.getByTestId("create-error")).toHaveTextContent(/write blew up/));
    expect(screen.getByTestId("journal-create-form")).toBeInTheDocument(); // form did NOT close
  });
});
