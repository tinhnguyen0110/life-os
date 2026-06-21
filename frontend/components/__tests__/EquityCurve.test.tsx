import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EquityCurve } from "../EquityCurve";
import type { EquityPoint, UseFinanceHistory, RangeDays } from "@/lib/useFinanceHistory";

// Mock the hook so the component test is deterministic (no fetch).
const hookState: { current: Partial<UseFinanceHistory> } = { current: {} };
const setDays = vi.fn();
const reload = vi.fn();
const snapshotToday = vi.fn();
vi.mock("@/lib/useFinanceHistory", async () => {
  const actual = await vi.importActual<typeof import("@/lib/useFinanceHistory")>("@/lib/useFinanceHistory");
  return {
    ...actual,
    useFinanceHistory: () => ({
      points: [], status: "ready", errMsg: "", warning: null, values: [],
      days: 30 as RangeDays, setDays, reload, snapshotToday, snapshotting: false,
      ...hookState.current,
    }),
  };
});

const P = (over: Partial<EquityPoint>): EquityPoint => ({
  day: "2026-06-15", ts: "2026-06-15T02:00:00+00:00", totalValue: 10000, ...over,
});

function withData(values: number[], extra: Partial<UseFinanceHistory> = {}) {
  hookState.current = {
    values,
    points: values.map((v, i) => P({ totalValue: v, day: `2026-06-${String(10 + i).padStart(2, "0")}` })),
    ...extra,
  };
}

describe("EquityCurve", () => {
  beforeEach(() => { hookState.current = {}; setDays.mockClear(); reload.mockClear(); snapshotToday.mockClear(); });
  afterEach(cleanup);

  it("loading state", () => {
    hookState.current = { status: "loading" };
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-loading")).toBeTruthy();
  });

  it("error state shows retry", () => {
    hookState.current = { status: "error", errMsg: "down" };
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-error")).toHaveTextContent("down");
  });

  it("EMPTY history → friendly empty-state + snapshot button (no broken svg)", () => {
    hookState.current = { status: "ready", values: [], warning: "no portfolio snapshots yet — POST /finance/snapshot to start the equity curve" };
    render(<EquityCurve />);
    const empty = screen.getByTestId("ecurve-empty");
    expect(empty).toBeTruthy();
    expect(empty).toHaveTextContent("Chưa có dữ liệu lịch sử");
    expect(empty).toHaveTextContent("no portfolio snapshots yet");
    expect(screen.getByTestId("ecurve-snapshot-empty")).toBeTruthy();
    expect(screen.queryByTestId("ecurve-svg")).toBeNull();
  });

  it("empty snapshot button calls snapshotToday", async () => {
    const user = userEvent.setup();
    hookState.current = { status: "ready", values: [] };
    render(<EquityCurve />);
    await user.click(screen.getByTestId("ecurve-snapshot-empty"));
    expect(snapshotToday).toHaveBeenCalledTimes(1);
  });

  it("SINGLE point → flat line + explicit dot (no NaN, visible)", () => {
    withData([10645]);
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-svg")).toBeTruthy();
    expect(screen.getByTestId("ecurve-single-dot")).toBeTruthy();
    // last value shown, delta is 0% (first==last)
    expect(screen.getByTestId("ecurve-last")).toHaveTextContent("$10,645");
  });

  it("renders line + area with multi-point data", () => {
    withData([9000, 9500, 10200]);
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-line")).toBeTruthy();
    expect(screen.getByTestId("ecurve-area")).toBeTruthy();
    expect(screen.queryByTestId("ecurve-single-dot")).toBeNull();
  });

  it("shows last value + positive delta (green) when portfolio grew", () => {
    withData([9000, 9900]); // +10%
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-last")).toHaveTextContent("$9,900");
    const delta = screen.getByTestId("ecurve-delta");
    expect(delta).toHaveTextContent("10.00%");
    expect(delta.className).toContain("pos");
  });

  it("delta is negative (red) when portfolio shrank", () => {
    withData([10000, 9000]); // -10%
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-delta").className).toContain("neg");
  });

  // #81 teeth — a literally-FLAT curve (first === last → 0.00%) must read NEUTRAL,
  // not a green ▲ pos. Reverting the widget to `up ? pos : neg` (0 → up) turns this RED.
  it("FLAT 0.00% delta → ▬ / faint, NOT green ▲ pos (false-gain bug)", () => {
    withData([10000, 10000]); // exactly flat → deltaPct === 0
    render(<EquityCurve />);
    const delta = screen.getByTestId("ecurve-delta");
    expect(delta).toHaveTextContent("0.00%");
    expect(delta).toHaveTextContent("▬");
    expect(delta.className).toContain("faint");
    expect(delta.className).not.toContain("pos"); // the teeth: not green-up
    expect(delta.textContent).not.toContain("▲");
  });

  it("hover shows tooltip with value + day + crosshair", () => {
    withData([10000, 10500, 10200]);
    render(<EquityCurve />);
    const svg = screen.getByTestId("ecurve-svg");
    fireEvent.pointerMove(svg, { clientX: 0, clientY: 10 }); // jsdom 0×0 rect → index 0
    expect(screen.getByTestId("ecurve-tooltip")).toBeTruthy();
    expect(screen.getByTestId("ecurve-tooltip")).toHaveTextContent("$10,000");
    expect(screen.getByTestId("ecurve-crosshair")).toBeTruthy();
    fireEvent.pointerLeave(svg);
    expect(screen.queryByTestId("ecurve-tooltip")).toBeNull();
  });

  it("range toggle calls setDays and marks the active range", async () => {
    const user = userEvent.setup();
    withData([10000, 10500], { days: 30 });
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-range-30").getAttribute("aria-pressed")).toBe("true");
    await user.click(screen.getByTestId("ecurve-range-90"));
    expect(setDays).toHaveBeenCalledWith(90);
  });

  it("shows axis endpoints + day count", () => {
    withData([10000, 10500, 10200]);
    render(<EquityCurve />);
    expect(screen.getByTestId("ecurve-axis-first")).toBeTruthy();
    expect(screen.getByTestId("ecurve-axis-last")).toBeTruthy();
  });
});
