/* ============================================================
   Shared client types — MIRROR backend modules/projects/schema.py EXACTLY.
   C3 (ROADMAP §6) — the common status shape every reader returns. FROZEN
   on the backend (schema.py docstring "Tier-S"). Source of truth on any
   divergence = backend schema.py. Do NOT invent shapes or "human-friendly"
   fields the backend does not return.

   Sprint 1 reconciliation: nullable human/git fields (None in Python →
   `T | null` in TS), `testPass` is camelCase (not snake), `branch` added,
   `last`/`lastAuto` are ISO-8601 UTC strings (NOT pre-formatted "2h trước" —
   the UI formats them client-side).
   ============================================================ */

/** Project health bucket — backend `Health = Literal["act","slow","stall","dead"]`. */
export type ProjectHealth = "act" | "slow" | "stall" | "dead";

/**
 * Per-project metrics — mirrors `ProjectMetrics`.
 * git-derived where possible; stars/testPass are honest null this build
 * (no GitHub API, no test-artifact parser).
 */
export interface ProjectMetrics {
  /** git rev-list --count HEAD (≥0). */
  commits: number;
  /** current branch (git rev-parse --abbrev-ref HEAD); "" if unknown. */
  branch: string;
  /** dominant tracked-file language, else null. */
  lang: string | null;
  /** test pass %, null — no parser this sprint. */
  testPass: number | null;
  /** repo stars, null — no GitHub API this build. */
  stars: number | null;
}

/**
 * C3 — common ProjectStatus shape (FROZEN). Mirrors `ProjectStatus`.
 * Human-authored fields (desc/progress/users/next) come from status.md and are
 * null/0 when absent — never fabricated. git-derived fields (health/last/
 * lastDays/metrics) come from read-only local git.
 */
export interface ProjectStatus {
  /** slug = repo folder name, lowercased, non-alnum→'-'. */
  id: string;
  /** status.md name: else repo folder name. */
  name: string;
  /** status.md desc:/goal: else null. */
  desc: string | null;
  /** act|slow|stall|dead from lastDays. */
  health: ProjectHealth;
  /** status.md progress 0-100, else null. */
  progress: number | null;
  /** status.md users, else 0. */
  users: number;
  /** ISO-8601 UTC of last commit, null if unknown. */
  last: string | null;
  /** whole UTC days since last commit, null if unknown. */
  lastDays: number | null;
  /** status.md next action, else null. */
  next: string | null;
  /** absolute path of the source repo. */
  repo: string;
  metrics: ProjectMetrics;
  /** routine ids touching this project. */
  routines: string[];
  /** ISO-8601 UTC of last automation touch, else null. */
  lastAuto: string | null;
}

/** Health summary bar (S2) — mirrors router `_summary()`. */
export interface ProjectsSummary {
  act: number;
  slow: number;
  stall: number;
  dead: number;
  total: number;
}

/** GET /projects `data` payload — `{projects, summary}`. */
export interface ProjectsListData {
  projects: ProjectStatus[];
  summary: ProjectsSummary;
}

/** Body of POST /projects — mirrors `ProjectRegisterInput`. */
export interface ProjectRegisterInput {
  name: string;
  repo: string;
  goal?: string | null;
  progress?: number | null;
  next?: string | null;
  users?: number | null;
}

/** Body of POST /projects/{id}/abandon — mirrors `ProjectAbandonInput`. */
export interface ProjectAbandonInput {
  reason: string;
  atProgress?: number | null;
}

/** C4 — every endpoint answers this envelope (ROADMAP §6). */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  warning?: string;
}

/** /health payload (Sprint 0). */
export interface HealthData {
  status: string;
  modules: string[];
}

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

/** GET /market `data` envelope — `{quotes, triggers, macro, alertHistory}`. */
export interface MarketData {
  quotes: AssetQuote[];
  triggers: AlertTrigger[];
  macro: MacroSignal[];
  alertHistory: AlertEvent[];
}
