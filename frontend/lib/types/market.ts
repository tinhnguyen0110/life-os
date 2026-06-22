

/* ============================================================
   Market (S8) — MIRRORS backend modules/market/schema.py EXACTLY (Sprint 3).
   Mirrored from the schema.py FILE (not a proposal): note `distance` (not
   distancePct), `MacroSignal.value` is a number, op is "above"|"below".
   render-only: changePct/distance/state are server-derived; FE formats + colors.
   ============================================================ */
export type AssetClass = "crypto" | "etf" | "vn";
export type AlertOp = "above" | "below";
export type AlertState = "hit" | "near" | "far";
/** A single asset's current quote — mirrors `AssetQuote`. */
export interface AssetQuote {
  symbol: string;
  name: string;
  assetClass: AssetClass;
  price: number;
  /** server-derived % change, null if no series. */
  changePct: number | null;
  currency: string;
  /** ISO-8601 UTC of this quote. */
  ts: string;
  /** coingecko | mock | last-known. */
  source: string;
}
/** A configured price-alert rule — mirrors `AlertRule` (FROZEN). id is
 *  server-assigned on create; clients DELETE by id. */
export interface AlertRule {
  id: string;
  symbol: string;
  op: AlertOp;
  threshold: number;
  enabled: boolean;
}
/** POST /market/alerts body — mirrors `AlertRuleInput` (no id; server assigns). */
export interface AlertRuleInput {
  symbol: string;
  op: AlertOp;
  threshold: number;
  enabled?: boolean;
}
/** An evaluated alert rule vs the current quote — mirrors `AlertTrigger` (FROZEN).
 *  `distancePct` = (threshold-price)/price*100, signed proximity %. */
export interface AlertTrigger {
  symbol: string;
  op: AlertOp;
  threshold: number;
  price: number;
  /** hit | near (|distancePct|≤5) | far. */
  state: AlertState;
  distancePct: number;
}
/** A fired alert recorded to history — mirrors `AlertEvent`. */
export interface AlertEvent {
  symbol: string;
  op: AlertOp;
  threshold: number;
  price: number;
  /** ISO-8601 UTC when it fired. */
  ts: string;
}
/** A macro indicator — mirrors `MacroSignal` (FROZEN). value is a display-ready
 *  STRING ("38", "54%", "$72") — mixed units, shown verbatim. */
export interface MacroSignal {
  name: string;
  value: string;
  /** fear | greed | neutral | ... */
  status: string;
  note: string;
}
/** One price-history point — mirrors `PricePoint`. */
export interface PricePoint {
  asset: string;
  price: number;
  ts: string;
}

/* ============================================================
   Finance (S5/S6) — MIRRORS backend modules/finance/schema.py EXACTLY (Sprint 4).
   Self-describing-raw: every DERIVED field ships with its inputs (PnL carries
   cost+current; ChannelAlloc carries target+pct so drift is checkable;
   LadderState carries trigger+current). FE renders + formats + colors — NEVER
   recomputes drift/pnl/ladder. NOTE (vs my earlier placeholder): the overview is
   `totalValue` (not total), a single `change` % (not day/week), `allocations`
   (not allocation), `pnlTotal` (not openPnl). NO series / recentTrades in the
   finance overview shape.
   ============================================================ */
/** GET /market `data` envelope — `{quotes, triggers, macro, alertHistory}`. */
export interface MarketData {
  quotes: AssetQuote[];
  triggers: AlertTrigger[];
  macro: MacroSignal[];
  alertHistory: AlertEvent[];
}

/* ============================================================
   OKX Exchange — mirrors modules/exchange/schema.py
   ============================================================ */
