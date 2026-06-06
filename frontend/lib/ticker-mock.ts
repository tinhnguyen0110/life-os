/* ============================================================
   Ticker mock data — Sprint 0 placeholder (mock-first, ARCH/operating-model §5).
   Swapped for the real /market feed in Sprint 4. Shape ported from mock data.js DB.market.
   ============================================================ */
export interface TickerItem {
  sym: string;
  px: string;
  chg: string;
  dir: "pos" | "neg";
}

export const TICKER_MOCK: TickerItem[] = [
  { sym: "BTC", px: "68,240", chg: "+3.1%", dir: "pos" },
  { sym: "ETH", px: "3,820", chg: "+5.2%", dir: "pos" },
  { sym: "SOL", px: "164.2", chg: "+2.4%", dir: "pos" },
  { sym: "SPY", px: "612.4", chg: "+0.4%", dir: "pos" },
  { sym: "QQQ", px: "528.1", chg: "+0.6%", dir: "pos" },
  { sym: "VNINDEX", px: "1,284", chg: "-0.6%", dir: "neg" },
  { sym: "USDT/VND", px: "24,180", chg: "+0.1%", dir: "pos" },
  { sym: "BRENT", px: "78.4", chg: "-1.2%", dir: "neg" },
  { sym: "GOLD", px: "2,418", chg: "+0.3%", dir: "pos" },
];
