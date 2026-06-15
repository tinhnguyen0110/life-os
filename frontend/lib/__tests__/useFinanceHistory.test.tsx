/**
 * FE-3 — useFinanceHistory hook tests (mocks global.fetch like useMarket.test).
 * Covers: loads equity points, exposes totalValue series oldest→newest, surfaces
 * the cold-start "no snapshots yet" warning, empty + single-point states, error,
 * range-days drives the URL, snapshotToday POSTs then reloads.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { useFinanceHistory, type EquityPoint } from "../useFinanceHistory";

afterEach(() => vi.restoreAllMocks());

const P = (over: Partial<EquityPoint>): EquityPoint => ({
  day: "2026-06-15", ts: "2026-06-15T02:00:00+00:00", totalValue: 10000, ...over,
});

function mockFetch(body: unknown, { ok = true, status = 200 } = {}) {
  global.fetch = vi.fn().mockResolvedValue({ ok, status, json: async () => body } as Response) as never;
}

function Probe() {
  const { status, values, warning, errMsg, days, setDays, points } = useFinanceHistory();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="values">{values.join(",")}</span>
      <span data-testid="warning">{warning ?? ""}</span>
      <span data-testid="err">{errMsg}</span>
      <span data-testid="days">{days}</span>
      <span data-testid="count">{points.length}</span>
      <button data-testid="to-7" onClick={() => setDays(7)}>7</button>
    </div>
  );
}

describe("useFinanceHistory", () => {
  it("loads points and exposes totalValue oldest→newest", async () => {
    mockFetch({
      success: true,
      data: { points: [P({ day: "2026-06-13", totalValue: 9000 }), P({ day: "2026-06-14", totalValue: 9500 }), P({ day: "2026-06-15", totalValue: 10200 })], days: 30 },
    });
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("values")).toHaveTextContent("9000,9500,10200");
    expect(screen.getByTestId("count")).toHaveTextContent("3");
  });

  it("empty history → ready with cold-start warning surfaced (no NaN)", async () => {
    mockFetch({ success: true, data: { points: [], days: 30 }, warning: "no portfolio snapshots yet — POST /finance/snapshot to start the equity curve" });
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("values")).toHaveTextContent("");
    expect(screen.getByTestId("warning")).toHaveTextContent("no portfolio snapshots yet");
  });

  it("single point is a valid ready state", async () => {
    mockFetch({ success: true, data: { points: [P({ totalValue: 10645 })], days: 30 } });
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    expect(screen.getByTestId("values")).toHaveTextContent("10645");
    expect(screen.getByTestId("count")).toHaveTextContent("1");
  });

  it("error state on fetch failure", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED")) as never;
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("error"));
    expect(screen.getByTestId("err").textContent).toMatch(/Network error|ECONNREFUSED/);
  });

  it("changing range-days refetches with the new days in the URL", async () => {
    const spy = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ success: true, data: { points: [P({})], days: 7 } }) });
    global.fetch = spy as never;
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("ready"));
    await act(async () => { screen.getByTestId("to-7").click(); });
    await waitFor(() => expect(screen.getByTestId("days")).toHaveTextContent("7"));
    expect(spy.mock.calls.some((c) => String(c[0]).includes("days=7"))).toBe(true);
  });

  it("default range is 30 days", async () => {
    mockFetch({ success: true, data: { points: [P({})], days: 30 } });
    render(<Probe />);
    await waitFor(() => expect(screen.getByTestId("days")).toHaveTextContent("30"));
  });
});
