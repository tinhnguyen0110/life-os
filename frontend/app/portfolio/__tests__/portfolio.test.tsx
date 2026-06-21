import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pushMock = vi.fn();
vi.mock("@/lib/useNav", () => ({ useSafeRouter: () => ({ push: pushMock }) }));

const getFinance = vi.fn();
const createHolding = vi.fn();
const getNavHistory = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getFinance: () => getFinance(),
    createHolding: (...a: unknown[]) => createHolding(...a),
    getNavHistory: (...a: unknown[]) => getNavHistory(...a),
  };
});

import PortfolioPage from "../page";
import { ApiError } from "@/lib/api";

// the PortfolioNavLine fetches /decision/nav-history on every ready render → default it
// to a benign empty series so the existing tests don't hit a real fetch.
const NAV_EMPTY = { success: true, data: { series: [], points: 0, range: { from: "", to: "" }, confidence: 0, warning: null } };
afterEach(() => { getFinance.mockReset(); createHolding.mockReset(); getNavHistory.mockReset(); pushMock.mockReset(); });
beforeEach(() => { getNavHistory.mockResolvedValue(NAV_EMPTY); });

const ALLOC = (over = {}) => ({ channel: "crypto", value: 60599, pct: 96.08, target: 38, drift: 58.08, driftAlert: true, pnl: { cost: 40000, current: 60599, abs: 20599, pct: 51.5 }, ...over });
const HOLDING = (over = {}) => ({ channel: "crypto", symbol: "BTC", qty: 1, avgCost: 40000, source: "manual", asOf: "2026-06-06T11:19:04Z", ...over });
const FIN = (over = {}) => ({
  success: true,
  data: {
    totalValue: 63069, change: { abs: 0, pct: null },
    holdings: [HOLDING(), HOLDING({ channel: "etf", symbol: "FUEVFVND", qty: 100, avgCost: 24.8 })],
    allocations: [ALLOC(), ALLOC({ channel: "etf", value: 2470, pct: 3.92, target: 24, drift: -20.08, pnl: { cost: 2480, current: 2470, abs: -10, pct: -0.4 } }), ALLOC({ channel: "dry", value: 0, pct: 0 })],
    pnlTotal: { cost: 42480, current: 63069, abs: 20589, pct: 48.5 }, dryPowder: 0, series: [],
    ...over,
  },
});
const err422 = (field: string, msg: string) => new ApiError(422, `${field}: ${msg}`, { detail: [{ type: "x", loc: ["body", field], msg }] });

describe("S6 Portfolio LIST — render (render-only)", () => {
  it("header counts: N holdings · M channels (value>0)", async () => {
    getFinance.mockResolvedValueOnce(FIN());
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-counts")).toBeInTheDocument());
    // 2 holdings · 2 channels with value>0 (crypto+etf; dry=0 excluded)
    expect(screen.getByTestId("portfolio-counts")).toHaveTextContent("2 vị thế · 2 kênh");
  });

  it("donut legend shows allocations with value>0 + their pct/value (render-only)", async () => {
    getFinance.mockResolvedValueOnce(FIN());
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-donut")).toBeInTheDocument());
    expect(screen.getByTestId("legend-crypto")).toHaveTextContent("96%");
    expect(screen.getByTestId("legend-crypto")).toHaveTextContent("$60,599");
    expect(screen.getByTestId("legend-etf")).toHaveTextContent("$2,470");
    expect(screen.queryByTestId("legend-dry")).toBeNull(); // value 0 → excluded
  });

  it("holdings table: per-holding qty + CHANNEL pnl (honest label), row→detail nav", async () => {
    // T3: the list shows qty + price + 24h + value + per-coin P&L + CHANNEL P&L.
    // (avgCost moved to the per-channel detail page; the list is now value/P&L oriented.)
    getFinance.mockResolvedValueOnce(FIN());
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("holding-BTC")).toBeInTheDocument());
    const row = screen.getByTestId("holding-BTC");
    expect(row).toHaveTextContent("BTC");
    expect(row).toHaveTextContent("1"); // qty
    expect(row).toHaveTextContent("+$20,599"); // channel pnl (render-only, BTC's channel=crypto)
    expect(row).toHaveTextContent("+51.5%"); // channel pnl pct
    await user.click(row);
    expect(pushMock).toHaveBeenCalledWith("/portfolio/crypto"); // → existing detail
  });

  it("empty holdings → friendly empty state (no fabricated rows)", async () => {
    getFinance.mockResolvedValueOnce(FIN({ holdings: [], allocations: [] }));
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-empty")).toBeInTheDocument());
  });

  it("channel filter tabs → filter the holdings table by channel", async () => {
    getFinance.mockResolvedValueOnce(FIN()); // crypto BTC + etf FUEVFVND
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-filter")).toBeInTheDocument());
    // both rows visible under "Tất cả"
    expect(screen.getByTestId("holding-BTC")).toBeInTheDocument();
    expect(screen.getByTestId("holding-FUEVFVND")).toBeInTheDocument();
    // click ETF → only the etf holding remains
    await user.click(screen.getByTestId("filter-etf"));
    await waitFor(() => expect(screen.queryByTestId("holding-BTC")).toBeNull());
    expect(screen.getByTestId("holding-FUEVFVND")).toBeInTheDocument();
    // header count stays the FULL count (counts don't lie under a filter)
    expect(screen.getByTestId("portfolio-counts")).toHaveTextContent("2 vị thế");
  });

  it("single-channel portfolio → NO filter tabs (a filter would be pointless)", async () => {
    getFinance.mockResolvedValueOnce(FIN({ holdings: [HOLDING()], allocations: [ALLOC()] }));
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-counts")).toBeInTheDocument());
    expect(screen.queryByTestId("portfolio-filter")).toBeNull();
  });

  it("GET error → friendly error + retry", async () => {
    getFinance.mockRejectedValueOnce(new ApiError(0, "down"));
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-error")).toBeInTheDocument());
  });

  it("TEETH: malformed body (data==null) → error, not silent-empty", async () => {
    getFinance.mockResolvedValueOnce({ success: true, data: null });
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-error")).toBeInTheDocument());
  });
});

describe("S6 Portfolio — add holding (write, fail-closed)", () => {
  it("add valid holding → POST then REFETCH (server-truth, not optimistic)", async () => {
    getFinance.mockResolvedValue(FIN());
    createHolding.mockResolvedValueOnce({ success: true, data: HOLDING({ symbol: "ETH", channel: "crypto" }) });
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-add-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("portfolio-add-toggle"));
    await user.type(screen.getByTestId("add-symbol-input"), "ETH");
    await user.type(screen.getByTestId("add-qty-input"), "5");
    await user.type(screen.getByTestId("add-avgCost-input"), "3000");
    await user.click(screen.getByTestId("add-submit"));
    await waitFor(() => expect(createHolding).toHaveBeenCalledWith({ channel: "crypto", symbol: "ETH", qty: 5, avgCost: 3000 }));
    // fail-closed: refetched GET /finance after the POST (1 initial + 1 refetch)
    await waitFor(() => expect(getFinance).toHaveBeenCalledTimes(2));
  });

  it("TEETH: 422 on channel → INLINE per-field error, form stays open (not fake success)", async () => {
    getFinance.mockResolvedValue(FIN());
    createHolding.mockRejectedValueOnce(err422("channel", "Input should be 'crypto', 'etf', 'vn' or 'dry'"));
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-add-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("portfolio-add-toggle"));
    await user.type(screen.getByTestId("add-symbol-input"), "X");
    await user.type(screen.getByTestId("add-qty-input"), "1");
    await user.type(screen.getByTestId("add-avgCost-input"), "1");
    await user.click(screen.getByTestId("add-submit"));
    await waitFor(() => expect(screen.getByTestId("add-channel-error")).toBeInTheDocument());
    expect(screen.getByTestId("add-channel-error")).toHaveTextContent(/crypto.*etf.*vn.*dry/);
    // form NOT closed (swallowed-422 would close it as if it succeeded)
    expect(screen.getByTestId("portfolio-add-form")).toBeInTheDocument();
  });

  it("TEETH: client requires symbol/qty/avgCost (matches backend required) before POST", async () => {
    getFinance.mockResolvedValue(FIN());
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-add-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("portfolio-add-toggle"));
    // submit empty → required errors, no POST fired
    await user.click(screen.getByTestId("add-submit"));
    await waitFor(() => expect(screen.getByTestId("add-symbol-error")).toHaveTextContent("bắt buộc"));
    expect(createHolding).not.toHaveBeenCalled();
  });

  it("TEETH: non-422 POST failure → form-level error, fail-closed", async () => {
    getFinance.mockResolvedValue(FIN());
    createHolding.mockRejectedValueOnce(new ApiError(500, "server blew up"));
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-add-toggle")).toBeInTheDocument());
    await user.click(screen.getByTestId("portfolio-add-toggle"));
    await user.type(screen.getByTestId("add-symbol-input"), "X");
    await user.type(screen.getByTestId("add-qty-input"), "1");
    await user.type(screen.getByTestId("add-avgCost-input"), "1");
    await user.click(screen.getByTestId("add-submit"));
    await waitFor(() => expect(screen.getByTestId("add-form-error")).toHaveTextContent(/server blew up/));
  });
});

/* ── T3 — per-coin P&L enrich (holdings[].pnl/price/changePct, backend-computed, null-safe) ── */
describe("S6 Portfolio — per-coin P&L (render-only, null-safe '—')", () => {
  // a holding WITH a real basis (PEPE -58%) and one with NO basis (USDT honest-null).
  const FIN_PERCOIN = FIN({
    holdings: [
      // basis-less stablecoin → price/pnl present but pnl null, changePct null
      { channel: "crypto", symbol: "USDT", qty: 10000, avgCost: null, source: "okx", asOf: "2026-06-16T06:17:05Z", price: 0.99944, usdValue: 9994, changePct: null, isDust: false, count: null, pnl: null },
      // real-basis coin with a deep loss
      { channel: "crypto", symbol: "PEPE", qty: 28518412, avgCost: 7.02e-6, source: "okx", asOf: "2026-06-16T06:17:05Z", price: 3e-6, usdValue: 84.07, changePct: -1.45, isDust: false, count: null, pnl: { cost: 200.25, current: 84.07, abs: -116.18, pct: -58.02 } },
    ],
  });

  it("a coin WITH basis shows its own P&L (PEPE −58.02%, abs negative tone)", async () => {
    getFinance.mockResolvedValueOnce(FIN_PERCOIN);
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("holding-PEPE")).toBeInTheDocument());
    const cell = screen.getByTestId("coinpnl-PEPE");
    expect(cell).toHaveTextContent("−$116"); // signed abs
    expect(cell).toHaveTextContent("−58.0%"); // its own pct
    expect(cell.className).toContain("neg");
  });

  it("a basis-less coin (USDT) shows '—' for per-coin P&L — NEVER a fabricated 0/+∞%", async () => {
    getFinance.mockResolvedValueOnce(FIN_PERCOIN);
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("holding-USDT")).toBeInTheDocument());
    expect(screen.getByTestId("coinpnl-USDT")).toHaveTextContent("—");
    // its 24h change is also null → "—" (no series), NOT "+0.0%"
    expect(screen.getByTestId("chg-USDT")).toHaveTextContent("—");
    // price IS present → shown (sub-$1 with sig digits, not "$0")
    expect(screen.getByTestId("price-USDT")).not.toHaveTextContent("—");
  });

  it("sub-cent price (PEPE ~$3e-6) renders with significant digits, not '$0'", async () => {
    getFinance.mockResolvedValueOnce(FIN_PERCOIN);
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("price-PEPE")).toBeInTheDocument());
    const price = screen.getByTestId("price-PEPE").textContent ?? "";
    expect(price).not.toBe("$0");
    expect(price).toMatch(/0\.0+3/); // shows the tiny price
  });
});

/* ── T3 — NAV line (short-series honest) ── */
describe("S6 Portfolio — NAV line", () => {
  it("short series → renders the backend warning (no confident trend)", async () => {
    getFinance.mockResolvedValueOnce(FIN());
    getNavHistory.mockResolvedValueOnce({
      success: true,
      data: { series: [{ date: "2026-06-15", nav: 10652 }, { date: "2026-06-16", nav: 10641 }], points: 2, range: { from: "2026-06-15", to: "2026-06-16" }, confidence: 0.066, warning: "2 point(s) — short series, still accumulating" },
    });
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-nav")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("portfolio-nav-warning")).toHaveTextContent(/still accumulating/i));
    // a dot per point — discrete observations, not a trend
    expect(screen.getByTestId("portfolio-nav-dot-0")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-nav-dot-1")).toBeInTheDocument();
  });

  it("NAV fetch error → its own error state (does NOT break the holdings table)", async () => {
    getFinance.mockResolvedValueOnce(FIN());
    getNavHistory.mockReset();
    getNavHistory.mockRejectedValue(new ApiError(500, "nav boom"));
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("portfolio-table")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("portfolio-nav-error")).toHaveTextContent(/nav boom/));
  });
});
