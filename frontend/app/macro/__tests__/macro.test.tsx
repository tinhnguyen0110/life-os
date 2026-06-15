import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const apiGet = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiGet: (...a: unknown[]) => apiGet(...a) };
});

import MacroPage from "../page";
import { ApiError } from "@/lib/api";

function ok<T>(data: T, warning?: string) { return { success: true, data, ...(warning ? { warning } : {}) }; }
const OVERVIEW = {
  indicators: [
    { indicator: "fed_funds_rate", label: "Fed Funds Rate", unit: "%", latest: 5.31, asOf: "2026-06-15", previous: 5.34, change: -0.03, trend: "down", source: "mock", points: 6 },
    { indicator: "cpi", label: "US CPI", unit: "index", latest: 312.44, asOf: "2026-06-15", previous: 315.55, change: -3.11, trend: "down", source: "mock", points: 6 },
  ],
  asOf: "2026-06-15", source: "mock",
};
const HISTORY = { indicator: "cpi", points: [{ indicator: "cpi", value: 315.5, ts: "2026-05-16", source: "mock" }, { indicator: "cpi", value: 312.4, ts: "2026-06-15", source: "mock" }] };

// route apiGet by URL: overview vs history
function routeGet(over = OVERVIEW, warn = "macro data is mock — placeholders") {
  apiGet.mockImplementation((path?: string) =>
    (path ?? "").startsWith("/macro/overview")
      ? Promise.resolve(ok(over, warn))
      : Promise.resolve(ok(HISTORY)),
  );
}

describe("Macro view (FE-5)", () => {
  beforeEach(() => apiGet.mockReset());

  it("renders Fed/CPI cards with latest value + descriptive trend", async () => {
    routeGet();
    render(<MacroPage />);
    await waitFor(() => expect(screen.getByTestId("macro-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("macro-card").length).toBe(2);
    expect(screen.getByText("Fed Funds Rate")).toBeInTheDocument();
    // descriptive trend (NO forecast/advice) — down → "giảm"
    expect(screen.getAllByTestId("macro-trend")[0]).toHaveTextContent("giảm");
  });

  it("HONEST-MIRROR: source=mock → mock badge + warning shown verbatim", async () => {
    routeGet();
    render(<MacroPage />);
    await waitFor(() => expect(screen.getByTestId("macro-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("macro-badge-mock").length).toBe(2);
    expect(screen.getByTestId("macro-warning")).toHaveTextContent(/mock/i);
  });

  it("no mock badge when source is live (e.g. fred)", async () => {
    routeGet({ ...OVERVIEW, source: "fred", indicators: OVERVIEW.indicators.map((i) => ({ ...i, source: "fred" })) }, undefined as any);
    render(<MacroPage />);
    await waitFor(() => expect(screen.getByTestId("macro-screen")).toBeInTheDocument());
    expect(screen.queryByTestId("macro-badge-mock")).toBeNull();
  });

  it("sparkline renders from /macro/history (fail-soft if history empty)", async () => {
    routeGet();
    render(<MacroPage />);
    await waitFor(() => expect(screen.getAllByTestId("macro-spark").length).toBeGreaterThan(0));
  });

  it("empty indicators → honest empty (not a crash)", async () => {
    apiGet.mockResolvedValue(ok({ indicators: [], asOf: "", source: "mock" }));
    render(<MacroPage />);
    await waitFor(() => expect(screen.getByTestId("macro-empty")).toBeInTheDocument());
  });

  it("overview error → error state w/ retry", async () => {
    // overview rejects; history resolves (won't be called since error blocks cards,
    // but a defined default avoids any stray unhandled rejection).
    apiGet.mockImplementation((path?: string) =>
      (path ?? "").startsWith("/macro/overview")
        ? Promise.reject(new ApiError(500, "macro down"))
        : Promise.resolve(ok(HISTORY)),
    );
    render(<MacroPage />);
    await waitFor(() => expect(screen.getByTestId("macro-error")).toHaveTextContent("macro down"));
  });
});
