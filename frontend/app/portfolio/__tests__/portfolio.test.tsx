import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const pushMock = vi.fn();
vi.mock("@/lib/useNav", () => ({ useSafeRouter: () => ({ push: pushMock }) }));

const getFinance = vi.fn();
const createHolding = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getFinance: () => getFinance(), createHolding: (...a: unknown[]) => createHolding(...a) };
});

import PortfolioPage from "../page";
import { ApiError } from "@/lib/api";

afterEach(() => { getFinance.mockReset(); createHolding.mockReset(); pushMock.mockReset(); });

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
const err422 = (field: string, msg: string) => new ApiError(422, `${field}: ${msg}`, [{ type: "x", loc: ["body", field], msg }]);

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

  it("holdings table: per-holding qty/avgCost + CHANNEL pnl (honest label), row→detail nav", async () => {
    getFinance.mockResolvedValueOnce(FIN());
    const user = userEvent.setup();
    render(<PortfolioPage />);
    await waitFor(() => expect(screen.getByTestId("holding-BTC")).toBeInTheDocument());
    const row = screen.getByTestId("holding-BTC");
    expect(row).toHaveTextContent("BTC");
    expect(row).toHaveTextContent("$40,000"); // avgCost
    expect(row).toHaveTextContent("+$20,599"); // channel pnl (render-only)
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
