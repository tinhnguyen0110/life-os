/* ============================================================
   Claude Usage (S9) — MIRRORS backend modules/claude_usage/schema.py (Sprint 7,
   FROZEN). REAL: model/used/cap/pct/remaining/series/today/avgPerDay/peak/byModel/
   costUSD/asOf/stale/source. STUBS (None unless manual override): resetIn, weekly,
   byProject. Derived fields carry inputs (pct carries used+cap). render-only.
   ============================================================ */
export interface DayBurn {
  date: string;
  /** weekday short label T2..CN. */
  label: string;
  tokens: number;
}
export interface ModelBurn {
  model: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreateTokens: number;
  total: number;
  costUSD: number;
}
/** Per-project token + derived-cost (LIVE from transcript cwd attribution). */
export interface ProjectBurn {
  project: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreateTokens: number;
  total: number;
  costUSD: number;
  msgs: number;
}
export interface ClaudeUsage {
  model: string;
  used: number;
  cap: number;
  pct: number;
  remaining: number;
  /** LIVE 5h-window reset countdown (quota snapshot) or manual override; null if neither. */
  resetIn: string | null;
  /** LIVE 7-day used % (quota snapshot) or manual override; null if neither. */
  weekly: number | null;
  /** LIVE: 5h rate-limit used % (quota snapshot). null if snapshot absent. */
  pct5h: number | null;
  /** LIVE: 7-day reset countdown (quota snapshot). */
  resetWeek: string | null;
  /** LIVE: current SESSION context-window used % (quota snapshot). */
  ctxPct: number | null;
  /** LIVE: current session context tokens used (raw). */
  ctxUsed: number | null;
  /** LIVE: current session context window size (opus 1M, sonnet 200k). */
  ctxMax: number | null;
  /** LIVE: model of the current session (from statusline). */
  ctxModel: string | null;
  /** 'snapshot' (live statusline tee) | 'manual' | 'stub'. */
  quotaSource: string;
  series: DayBurn[];
  today: number;
  avgPerDay: number;
  peak: DayBurn;
  byModel: ModelBurn[];
  costUSD: number;
  /** LIVE per-project burn (transcript cwd), total desc. [] if no transcripts. */
  byProject: ProjectBurn[];
  /** 'transcripts' (live .jsonl) | 'stats-cache' | 'none'. */
  tokenSource: string;
  asOf: string;
  stale: boolean;
  /** mirror of tokenSource (legacy field). */
  source: string;
}
