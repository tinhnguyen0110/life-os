import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const apiGet = vi.fn();
const apiPost = vi.fn();
const apiDelete = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    apiGet: (...a: unknown[]) => apiGet(...a),
    apiPost: (...a: unknown[]) => apiPost(...a),
    apiDelete: (...a: unknown[]) => apiDelete(...a),
  };
});

import MarketPage from "../page";

afterEach(() => {
  apiGet.mockReset();
  apiPost.mockReset();
  apiDelete.mockReset();
});

const FULL = {
  success: true,
  data: {
    quotes: [
      { symbol: "BTC", name: "Bitcoin", assetClass: "crypto", price: 68240, changePct: 3.1, currency: "USD", ts: "2026-06-06T12:00:00Z", source: "coingecko" },
      { symbol: "VNINDEX", name: "VN-Index", assetClass: "vn", price: 1284, changePct: -0.6, currency: "VND", ts: "2026-06-06T12:00:00Z", source: "mock" },
    ],
    triggers: [
      // FROZEN schema: distancePct (signed %), no id on triggers
      { symbol: "BTC", op: "above", threshold: 72000, price: 68240, state: "near", distancePct: 5.5 },
      { symbol: "ETH", op: "below", threshold: 3000, price: 3820, state: "far", distancePct: -21 },
    ],
    // macro value is a display-ready STRING ("$72","54%")
    macro: [{ name: "Brent", value: "$72", status: "neutral", note: "dầu" }],
    alertHistory: [{ symbol: "BTC", op: "above", threshold: 65000, price: 65100, ts: "2026-06-05T10:00:00Z" }],
  },
};

// AlertRule list (carries server-assigned ids — delete is BY id).
const RULES = {
  success: true,
  data: [{ id: "btc-1", symbol: "BTC", op: "above", threshold: 72000, enabled: true }],
};

/** Route apiGet by path: /market → market data, /market/alerts → rules. */
function routeGet(market = FULL, rules = RULES) {
  apiGet.mockImplementation((path: string) =>
    path === "/market/alerts" ? Promise.resolve(rules) : Promise.resolve(market),
  );
}

describe("S8 Market screen", () => {
  it("renders quotes with formatted price + signed % once loaded", async () => {
    routeGet();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByText("68,240")).toBeInTheDocument());
    expect(screen.getByText("+3.1%")).toBeInTheDocument();
    expect(screen.getByText("-0.6%")).toBeInTheDocument();
  });

  it("renders the macro block with a STRING value verbatim (live: '$72', not '—')", async () => {
    routeGet();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("market-macro")).toBeInTheDocument());
    expect(screen.getByText("Brent")).toBeInTheDocument();
    // string value shown as-is (regression: was "—" because type said number)
    expect(screen.getByText("$72")).toBeInTheDocument();
  });

  it("renders trigger proximity from distancePct (live field) without NaN", async () => {
    routeGet();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("market-triggers")).toBeInTheDocument());
    // distancePct=5.5 → "còn cách 5.5%"; NOT "NaN%"
    expect(screen.getByText(/còn cách 5\.5%/)).toBeInTheDocument();
    expect(screen.queryByText(/NaN/)).toBeNull();
    expect(screen.getByTestId("del-BTC-above")).toBeInTheDocument();
  });

  it("survives duplicate symbol+op triggers (unique keys, no dropped rows)", async () => {
    routeGet({
      success: true,
      data: {
        quotes: [],
        triggers: [
          { symbol: "BTC", op: "above", threshold: 70000, price: 100, state: "far", distancePct: 6 },
          { symbol: "BTC", op: "above", threshold: 70000, price: 100, state: "far", distancePct: 6 },
        ],
        macro: [],
        alertHistory: [],
      },
    });
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("market-triggers")).toBeInTheDocument());
    // both duplicate rows render (2 trigger rows), no React key crash
    expect(screen.getAllByText("BTC").length).toBeGreaterThanOrEqual(2);
  });

  it("renders alert history", async () => {
    routeGet();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("market-history")).toBeInTheDocument());
    expect(screen.getByText(/BTC ≥ 65,000/)).toBeInTheDocument();
  });

  it("empty quotes/triggers/history → empty states, not broken tables", async () => {
    routeGet(
      { success: true, data: { quotes: [], triggers: [], macro: [], alertHistory: [] } },
      { success: true, data: [] },
    );
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByText(/Chưa có mã nào/)).toBeInTheDocument());
    expect(screen.getByText(/Chưa đặt trigger nào/)).toBeInTheDocument();
    expect(screen.getByText(/Chưa có cảnh báo nào kích hoạt/)).toBeInTheDocument();
  });

  it("API error → friendly error state, no white-screen crash", async () => {
    const { ApiError } = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
    apiGet.mockRejectedValueOnce(new (ApiError as any)(0, "Network error"));
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("market-error")).toBeInTheDocument());
  });

  it("threshold form: submitting posts a new alert rule", async () => {
    routeGet();
    apiPost.mockResolvedValueOnce({ success: true, data: [] });
    const user = userEvent.setup();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("alert-symbol")).toBeInTheDocument());
    await user.type(screen.getByTestId("alert-symbol"), "sol");
    await user.type(screen.getByTestId("alert-threshold"), "200");
    await user.click(screen.getByTestId("alert-submit"));
    await waitFor(() =>
      expect(apiPost).toHaveBeenCalledWith("/market/alerts", {
        symbol: "SOL",
        op: "above",
        threshold: 200,
      }),
    );
  });

  it("threshold form: invalid input shows a validation error, no POST", async () => {
    routeGet();
    const user = userEvent.setup();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("alert-submit")).toBeInTheDocument());
    await user.click(screen.getByTestId("alert-submit")); // empty form
    expect(screen.getByTestId("alert-form-error")).toBeInTheDocument();
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("delete button maps trigger→rule id and DELETEs by id (FROZEN: by id, not symbol/op)", async () => {
    // RULES has {id:"btc-1", symbol:"BTC", op:"above"} → the BTC/above trigger's
    // delete must resolve to rule id "btc-1".
    routeGet();
    apiDelete.mockResolvedValueOnce({ success: true, data: { deleted: "btc-1" } });
    const user = userEvent.setup();
    render(<MarketPage />);
    await waitFor(() => expect(screen.getByTestId("del-BTC-above")).toBeInTheDocument());
    await user.click(screen.getByTestId("del-BTC-above"));
    await waitFor(() => expect(apiDelete).toHaveBeenCalledWith("/market/alerts/btc-1"));
  });

  it("delete button is disabled when no matching rule id exists (ETH trigger, no ETH rule)", async () => {
    routeGet();
    render(<MarketPage />);
    // RULES only has a BTC rule → the ETH/below trigger has no rule id → disabled
    await waitFor(() => expect(screen.getByTestId("del-ETH-below")).toBeInTheDocument());
    expect(screen.getByTestId("del-ETH-below")).toBeDisabled();
  });
});
