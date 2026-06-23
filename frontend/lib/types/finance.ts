/** One position — mirrors backend `Holding` (finance/schema.py). RAW qty/avgCost +
 *  provenance, PLUS additive per-holding enrichment (FINANCE-CORRECTNESS #49 + P1 #52):
 *  price/usdValue/changePct SURFACED from the per-holding numbers _aggregate already
 *  computes (NOT re-priced); `pnl` is THIS holding's OWN P&L (distinct from the
 *  channel-level ChannelAlloc.pnl). Every enrichment field is NULLABLE — a basis-less
 *  coin (OKX value-only, e.g. USDT) carries avgCost=null → pnl=null (honest-null, never
 *  fabricates a 0-cost/+∞% gain); a `·dust` summary entry (isDust) carries price/pnl=null.
 *  FE renders + formats + colors these — NEVER recomputes (a wrong number is a BE bug). */
export interface Holding {
  channel: string;
  symbol: string;
  qty: number;
  /** avg cost per unit; null = no per-coin basis (OKX value-only coin). */
  avgCost: number | null;
  source: string;
  asOf: string | null;
  /** current unit price (USD); null when unpriceable / on a ·dust summary entry. */
  price?: number | null;
  /** current market value (USD) = price×qty; null when unpriceable. */
  usdValue?: number | null;
  /** 24h % change; null when no price series for the symbol / on a ·dust entry. */
  changePct?: number | null;
  /** true ONLY on a per-channel ·dust summary entry; a real holding is always false. */
  isDust?: boolean;
  /** # of holdings folded into a ·dust summary; set ONLY on a dust entry (else null). */
  count?: number | null;
  /** this holding's OWN P&L (abs/pct from its own avgCost vs current); null when no
   *  basis (basis-less coin) or on a ·dust entry. DISTINCT from ChannelAlloc.pnl. */
  pnl?: PnL | null;
}
/** Profit/loss carrying its inputs — mirrors `PnL`. */
export interface PnL {
  cost: number;
  current: number;
  /** current - cost. */
  abs: number;
  /** abs/cost*100; null when cost==0. */
  pct: number | null;
}
/** The SCOPE of a P&L number — mirrors backend `PnlScope`. Critical for honesty: a
 *  −72% pnlTotal is over the ~2.2% of the book that HAS a cost basis, NOT the whole
 *  portfolio. The FE must render this so the honest number isn't itself misread as a
 *  whole-portfolio loss. coveragePct = % of book value that has a basis. */
export interface PnlScope {
  /** e.g. "known-cost-only" — which slice the P&L covers. */
  basis: string;
  /** % of book value that has a cost basis (the denominator the pct applies to); null if unknown. */
  coveragePct: number | null;
  /** human-readable explanation (rendered as the scope caption/tooltip). */
  note: string;
}
/** A channel allocation slice — mirrors `ChannelAlloc`. drift is a SIGNED number
 *  (pct - target); |drift|>5 ⇒ rebalance alert. actual % = `pct`.
 *  NOTE: the LIVE channel-detail serializes an extra `driftAlert: bool` (computed
 *  in service.py, not in schema.py's ChannelAlloc) — accepted optionally. */
export interface ChannelAlloc {
  channel: string;
  value: number;
  /** actual % of total portfolio. */
  pct: number;
  /** target % (golden-path). */
  target: number;
  /** pct - target (signed). */
  drift: number;
  /** |drift| > threshold — live-only field (service adds it). */
  driftAlert?: boolean;
  pnl: PnL;
}
/** A holding priced to current market — the S6 detail's holdings[] item shape
 *  (live /finance/{channel}). Wraps the raw Holding + market price + value + pnl. */
export interface PricedHolding {
  holding: Holding;
  price: number;
  /** price provenance: coingecko | mock | last-known. */
  source: string;
  value: number;
  pnl: PnL;
}
/** GET /finance/{channel} — S6 detail composite (alloc + priced holdings + ladder). */
export interface ChannelDetail {
  channel: string;
  alloc: ChannelAlloc;
  holdings: PricedHolding[];
  ladder: LadderState | null;
}
/** DCA buy-ladder state for a channel — mirrors `LadderState`. */
export interface LadderState {
  channel: string;
  referencePrice: number;
  currentPrice: number;
  rungsIn: number;
  /** {pct, triggerPrice} of the next rung below current, or null if all hit. */
  nextRung: { pct: number; triggerPrice: number } | null;
  /** (currentPrice - triggerPrice)/currentPrice*100 to nextRung; null if none. */
  distancePct: number | null;
}
/** Portfolio value change — mirrors `Change` (self-describing abs+pct). */
export interface Change {
  abs: number;
  pct: number | null;
}
/** GET /finance overview — mirrors `FinanceOverview` (re-read after schema evolved:
 *  `change` is now a Change object, `holdings` + `series` added). */
export interface FinanceOverview {
  totalValue: number;
  /** portfolio change {abs, pct}, null if no series. */
  change: Change | null;
  holdings: Holding[];
  allocations: ChannelAlloc[];
  pnlTotal: PnL;
  /** the SCOPE of pnlTotal — render so −72% reads as "on the ~2.2% with a basis", NOT
   *  whole-portfolio. Optional/nullable: backend field; fall back to bare text if absent. */
  pnlScope?: PnlScope | null;
  dryPowder: number;
  /** portfolio value over time ([] if none). */
  series: number[];
}
/** POST /finance/holdings body — mirrors `HoldingInput`. */
export interface HoldingInput {
  channel: string;
  symbol: string;
  qty: number;
  avgCost: number;
  source?: string;
}
/** One asset balance on OKX — mirrors `OkxBalance`. The cost-basis fields
 *  (accAvgPx/spotUpl/spotUplRatio) come from OKX's accAvgPx (free, per-coin) — backend-
 *  computed, FE renders/colors only (NEVER recomputes). NULLABLE: a value-only /
 *  stablecoin position (USDT, ETH with no basis) carries all three null → render "—",
 *  NEVER a fabricated 0/+∞% (honest-null, same discipline as per-coin Holding.pnl). */
export interface OkxBalance {
  symbol: string;
  available: number;
  frozen: number;
  total: number;
  usdValue: number | null;
  /** OKX accumulated average cost price per unit; null when no basis. */
  accAvgPx?: number | null;
  /** spot unrealized P&L in USD (current value − cost); null when no basis. */
  spotUpl?: number | null;
  /** spot unrealized P&L as a RATIO (e.g. -0.5786 = −57.86%); null when no basis. */
  spotUplRatio?: number | null;
  /** true when this "·dust" row is a FOLD of N sub-$0.001 coins (a rollup, not a real
   *  holding) — backend-set. The FE renders it distinctly so it never reads as a coin. */
  isDust?: boolean;
  /** number of dust coins folded into this rollup row (present only when isDust). */
  count?: number;
}
/** One open position (margin/futures) — mirrors `OkxPosition`. */
export interface OkxPosition {
  instId: string;
  side: string;
  qty: number;
  avgOpenPrice: number;
  unrealizedPnl: number;
  margin: number;
  lever: string;
}
/** Crypto cost-basis snapshot — mirrors `CryptoBasis` (GET /finance/crypto-basis). */
export interface CryptoBasis {
  /** cost basis in USD; null if not yet set. */
  basis: number | null;
  /** "snapshot" = auto-computed from holdings; "manual" = user override. */
  source: "snapshot" | "manual";
  /** ISO-8601 UTC when last set; null if never. */
  setAt: string | null;
}
/** OKX account overview — mirrors `ExchangeOverview`. */
export interface ExchangeOverview {
  totalUsdValue: number;
  balances: OkxBalance[];
  positions: OkxPosition[];
  syncedAt: string | null;
  configured: boolean;
}
