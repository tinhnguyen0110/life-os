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
    resetIn: null, weekly: null, // default: no live snapshot
    pct5h: null, resetWeek: null, ctxPct: null, ctxUsed: null, ctxMax: null, ctxModel: null, quotaSource: "stub",
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
    costUSD: 39145.5, byProject: [], tokenSource: "stats-cache", asOf: "2026-04-17", stale: true, source: "stats-cache",
    ...over,
  },
});

describe("S9 Claude Usage", () => {
  it("gauge falls back to pct (today/cap) when no live 5h quota; shows today tokens", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE()); // pct5h null → gauge shows u.pct
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-gauge")).toBeInTheDocument());
    expect(screen.getByTestId("usage-gauge")).toHaveTextContent("18.9%");
    expect(screen.getByTestId("usage-stats")).toHaveTextContent("37.7k"); // today in stats
  });

  it("dual gauge shows LIVE 5h + 7d quota % when snapshot present (not today/cap)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE({ pct5h: 7, quotaSource: "snapshot", resetIn: "16m", weekly: 6, ctxPct: 23, resetWeek: "100h" }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-quota-5h")).toBeInTheDocument());
    expect(screen.getByTestId("usage-quota-5h")).toHaveTextContent("7%"); // 5h gauge, NOT 18.9
    expect(screen.getByTestId("usage-quota-7d")).toHaveTextContent("6%"); // 7d gauge = weekly
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

  it("byModel segment renders per-model rows with cost (short model label)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-bymodel")).toBeInTheDocument());
    // modelLabel strips the "claude-" prefix → "sonnet", "opus-4-6"
    expect(screen.getByTestId("usage-bymodel")).toHaveTextContent("sonnet");
    expect(screen.getByTestId("usage-bymodel")).toHaveTextContent("opus-4-6");
  });

  it("byProject EMPTY (stats-cache mode) → honest empty hint, no fabricated projects", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE()); // byProject: []
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-byproject")).toBeInTheDocument());
    expect(screen.getByTestId("usage-byproject")).toHaveTextContent(/Chưa có transcript/);
  });

  it("byProject LIVE → renders project rows with tokens + cost, sorted (transcript source)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE({
      tokenSource: "transcripts", source: "transcripts", stale: false, asOf: "2026-06-09",
      byProject: [
        { project: "OutboundOS", inputTokens: 1, outputTokens: 2, cacheReadTokens: 0, cacheCreateTokens: 0, total: 32000000, costUSD: 26959, msgs: 29583 },
        { project: "life-os", inputTokens: 1, outputTokens: 2, cacheReadTokens: 0, cacheCreateTokens: 0, total: 4000000, costUSD: 3580, msgs: 6017 },
      ],
    }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-byproject")).toBeInTheDocument());
    const panel = screen.getByTestId("usage-byproject");
    expect(panel).toHaveTextContent("OutboundOS");
    expect(panel).toHaveTextContent("life-os");
    expect(panel).toHaveTextContent("32M"); // total formatted (fmtTokens)
    expect(panel).not.toHaveTextContent(/Chưa có transcript/);
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

  it("cost: total headline + direct/cache-read breakdown (RULING 2, computed from byModel)", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE());
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-cost-breakdown")).toBeInTheDocument());
    expect(screen.getByTestId("usage-cost-breakdown")).toHaveTextContent("$39,146"); // total
    expect(screen.getByTestId("usage-cost-cache")).toBeInTheDocument(); // cache-read $ leg present
    expect(screen.getByTestId("usage-cost-direct")).toBeInTheDocument(); // direct $ leg present
  });

  it("summary KPI row: total cost + project + model counts", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE({
      tokenSource: "transcripts",
      byProject: [
        { project: "a", inputTokens: 1, outputTokens: 1, cacheReadTokens: 0, cacheCreateTokens: 0, total: 100, costUSD: 5, msgs: 3 },
        { project: "b", inputTokens: 1, outputTokens: 1, cacheReadTokens: 0, cacheCreateTokens: 0, total: 50, costUSD: 2, msgs: 1 },
      ],
    }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-summary")).toBeInTheDocument());
    const s = screen.getByTestId("usage-summary");
    expect(s).toHaveTextContent("$39,146"); // total cost
    expect(s).toHaveTextContent("2"); // 2 projects + 2 models
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

  it("LIVE quota: snapshot source → 5h+7d gauges + reset countdowns render real values", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE({
      resetIn: "16m", weekly: 6, pct5h: 6, resetWeek: "147h 41m", ctxPct: 23, quotaSource: "snapshot",
    }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-quota-5h")).toBeInTheDocument());
    // 5h gauge: pct + reset countdown
    expect(screen.getByTestId("usage-quota-5h")).toHaveTextContent("6%");
    expect(screen.getByTestId("usage-reset")).toHaveTextContent("16m");
    // 7d gauge: weekly % + 7d reset countdown
    expect(screen.getByTestId("usage-quota-7d")).toHaveTextContent("6%");
    expect(screen.getByTestId("usage-quota-7d")).toHaveTextContent("147h 41m");
  });

  it("7d gauge shows '—' when weekly is null (stub) — no fabricated quota", async () => {
    getClaudeUsage.mockResolvedValueOnce(USAGE()); // weekly null
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-quota-7d")).toBeInTheDocument());
    expect(screen.getByTestId("usage-quota-7d")).toHaveTextContent("—");
  });

  it("per-session context is NOT shown in the quota card (account quota spans many sessions)", async () => {
    // even with a live ctx in the payload, the quota card must not render it — a
    // single session's window would misread as "the quota".
    getClaudeUsage.mockResolvedValueOnce(USAGE({
      quotaSource: "snapshot", pct5h: 0, weekly: 7, resetIn: "4h", resetWeek: "147h",
      ctxUsed: 323106, ctxMax: 1000000, ctxPct: 32, ctxModel: "Opus 4.8 (1M context)",
    }));
    render(<ClaudeUsagePage />);
    await waitFor(() => expect(screen.getByTestId("usage-gauge")).toBeInTheDocument());
    expect(screen.queryByTestId("usage-context")).not.toBeInTheDocument();
    expect(screen.getByTestId("usage-gauge")).not.toHaveTextContent("Context phiên này");
  });
});
