

/* ============================================================
   Journal (S7) — MIRRORS backend modules/journal/schema.py (Sprint 9, FROZEN).
   ONE unified entry: trade-log fields + OPTIONAL SPEC decision fields. pnl is a
   free-form percent STRING ("+5.5%", null=open). confidence 0-100. Derived stats
   nullable (None when 0 closed). render-only.
   ============================================================ */
export type JournalAction = "BUY" | "SELL";
export type JournalChannel = "crypto" | "etf" | "vn" | "dry";
export type JournalOutcome = "open" | "right" | "wrong";
export interface JournalEntry {
  id: string;
  /** ISO-8601 UTC decision date. */
  date: string;
  action: JournalAction;
  asset: string;
  size: string;
  px: string;
  tag: string;
  reason: string;
  channel: JournalChannel | null;
  thesis: string | null;
  negationCondition: string | null;
  /** 0-100. */
  confidence: number | null;
  /** null=open; "+5.5%"/"-4.1%" when closed (free-form % STRING). */
  pnl: string | null;
  outcome: JournalOutcome;
  lesson: string | null;
  createdAt: string;
  updatedAt: string;
}
/** POST/PUT body — mirrors `JournalInput`. PUT closes a trade (pnl/outcome/lesson). */
export interface JournalInput {
  date?: string | null;
  action: JournalAction;
  asset: string;
  size?: string;
  px?: string;
  tag?: string;
  reason: string;
  channel?: JournalChannel | null;
  thesis?: string | null;
  negationCondition?: string | null;
  confidence?: number | null;
  pnl?: string | null;
  outcome?: JournalOutcome | null;
  lesson?: string | null;
}
/** One confidence band vs actual win-rate — mirrors `CalibrationBand`. */
export interface CalibrationBand {
  band: string;
  predicted: number;
  actual: number;
  n: number;
}
/** GET /journal — entries + derived performance/calibration stats. */
export interface JournalStats {
  entries: JournalEntry[];
  count: number;
  /** closed pnl>0 / total closed; null if 0 closed. */
  winRate: number | null;
  avgPnl: number | null;
  ladderDiscipline: number | null;
  /** {total, buy, sell, ladder} for the current month. */
  thisMonth: { total: number; buy: number; sell: number; ladder: number };
  calibration: CalibrationBand[];
}
