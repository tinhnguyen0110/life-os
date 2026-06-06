import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const getClaudeUsage = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getClaudeUsage: () => getClaudeUsage() };
});

import ClaudeUsagePage from "../page";

afterEach(() => getClaudeUsage.mockReset());

const USAGE = (over = {}) => ({
  success: true,
  data: {
    model: "claude-opus-4-6", used: 37727, cap: 200000, pct: 18.9, remaining: 162273,
    resetIn: null, weekly: null, // STUBS
    series: [
      { date: "2026-06-01", label: "T2", tokens: 48000 },
      { date: "2026-06-02", label: "T3", tokens: 62000 },
      { date: "2026-06-03", label: "T7", tokens: 0 },
    ],
    today: 37727, avgPerDay: 50000, peak: { date: "2026-06-02", label: "T3", tokens: 62000 },
    byModel: [
      { model: "claude-opus-4-6", inputTokens: 100, outputTokens: 200, cacheReadTokens: 0, cacheCreateTokens: 0, total: 16931105, costUSD: 36254.7 },
      { model: "claude-sonnet", inputTokens: 50, outputTokens: 100, cacheReadTokens: 0, cacheCreateTokens: 0, total: 500000, costUSD: 120.5 },
    ],
    costUSD: 39145.5, byProject: null, asOf: "2026-04-17", stale: true, source: "stats-cache",
    ...over,
  },
});

describe("S9 Claude Usage", () => {
  it("renders the gauge pct + used/cap (render-only)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-gauge")).toBeInTheDocument());
    expect(screen.getByTestId("usage-gauge")).toHaveTextContent("18.9%");
    expect(screen.getByTestId("usage-gauge")).toHaveTextContent("37.7k"); // used
    expect(screen.getByTestId("usage-gauge")).toHaveTextContent("200k"); // cap
  });

  it("resetIn + weekly are STUBS (null) → honest text / '—', NOT a fabricated number", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-reset")).toBeInTheDocument());
    expect(screen.getByTestId("usage-reset")).toHaveTextContent(/chưa nối/);
    expect(screen.getByTestId("usage-reset")).not.toHaveTextContent(/\d+:\d+/); // no fake countdown
  });

  it("3 stats render today/avgPerDay/peak from backend (no recompute)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-stats")).toBeInTheDocument());
    expect(screen.getByTestId("usage-stats")).toHaveTextContent("37.7k"); // today
    expect(screen.getByTestId("usage-stats")).toHaveTextContent("62k"); // peak
  });

  it("daily bar chart renders one bar per series day", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-daily")).toBeInTheDocument());
    // 3 day labels
    expect(screen.getByTestId("usage-daily")).toHaveTextContent("T2");
    expect(screen.getByTestId("usage-daily")).toHaveTextContent("T7");
  });

  it("byModel segment renders per-model rows with cost", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-bymodel")).toBeInTheDocument());
    expect(screen.getByTestId("usage-bymodel")).toHaveTextContent("claude-sonnet");
  });

  it("per-project is a STUB (byProject null) → 'Sắp có', never fabricated", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-byproject-stub")).toBeInTheDocument());
    expect(screen.getByTestId("usage-byproject-stub")).toHaveTextContent(/Sắp có/);
  });

  it("stale data → PROMINENT stale badge with asOf (RULING 1, not a footnote)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-stale-badge")).toBeInTheDocument());
    expect(screen.getByTestId("usage-stale-badge")).toHaveTextContent("2026-04-17");
    expect(screen.getByTestId("usage-stale-badge")).toHaveTextContent(/chưa cập nhật/);
  });

  it("fresh data → no stale badge", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE({ stale: false, asOf: "2026-06-06" }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-screen")).toBeInTheDocument());
    expect(screen.queryByTestId("usage-stale-badge")).toBeNull();
  });

  it("cost: total headline + cache-read breakout (RULING 2, computed from byModel)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-cost")).toBeInTheDocument());
    expect(screen.getByTestId("usage-cost")).toHaveTextContent("$39,146"); // total
    expect(screen.getByTestId("usage-cost-cache")).toHaveTextContent(/cache-read/); // breakout present
  });

  it("empty series → empty chart state, not crash", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE({ series: [], peak: { date: "2026-06-06", label: "T6", tokens: 0 } }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-daily")).toHaveTextContent(/Chưa có dữ liệu theo ngày/));
  });

  it("API error → friendly error state", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    getClaudeUsage.mockRejectedValueOnce(new (ApiError as any)(0, "down"));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-error")).toBeInTheDocument());
  });

  it("TEETH: fulfilled-but-undefined body → error state, no crash (Sprint-5 guard)", async () => {
    getClaudeUsage.mockResolvedValueOnce(undefined);
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-error")).toBeInTheDocument());
  });
});
