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

/** One position — mirrors `Holding`. RAW qty/avgCost + provenance. */
export interface Holding {
  channel: string;
  symbol: string;
  qty: number;
  avgCost: number;
  source: string;
  asOf: string | null;
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

/* ============================================================
   Notes (S10) — MIRRORS backend modules/notes/schema.py EXACTLY (Sprint 6, FROZEN).
   NOTE: `attach` is a NESTED {type, ref} object (NOT flat attachedType/attachedId).
   ref required when type != "none". List returns pinned-first → updatedAt-desc.
   ============================================================ */
export type AttachType = "project" | "channel" | "none";

export interface Attach {
  type: AttachType;
  /** project id / channel id / null. Required when type != "none". */
  ref?: string | null;
}

/** A stored note — mirrors `Note`. id = slug(title)-6hex; timestamps ISO UTC. */
export interface Note {
  id: string;
  title: string;
  body: string;
  tags: string[];
  pinned: boolean;
  attach: Attach;
  createdAt: string;
  updatedAt: string;
}

/** POST/PUT body — mirrors `NoteInput`. id/timestamps server-assigned; title required. */
export interface NoteInput {
  title: string;
  body?: string;
  tags?: string[];
  pinned?: boolean;
  attach?: Attach;
}

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

/* ============================================================
   Activity (S14) — MIRRORS backend modules/activity/schema.py (S10B, FROZEN).
   Read-only run_log projection + roll-up. Self-describing-raw: each run carries
   durationMs; feed carries successRate (% 0-100, null when count==0 — NOT 0).
   CAP: runs = newest-100 slice; count = FULL filtered total ("100 gần nhất / N").
   ============================================================ */
export type RunStatus = "ok" | "warn" | "error";

export interface ActivityRun {
  /** run_log PK — addressable via GET /activity/{id}. */
  id: number;
  routineId: string;
  routineName: string;
  status: RunStatus;
  detail: string;
  startedAt: string;
  finishedAt: string | null;
  /** finished-started in ms; null if no finishedAt / unparseable. */
  durationMs: number | null;
}

export interface RoutineBreakdown {
  routine: string;
  routineName: string;
  count: number;
  okCount: number;
  warnCount: number;
  errorCount: number;
  lastRun: string | null;
}

export interface ActivityFeed {
  /** capped at newest 100. */
  runs: ActivityRun[];
  /** FULL filtered total (may exceed runs.length when >100). */
  count: number;
  runsToday: number;
  okCount: number;
  warnCount: number;
  errorCount: number;
  /** okCount/count*100, 1dp; null when count==0 (NOT 0% — no runs to rate). */
  successRate: number | null;
  avgDurationMs: number | null;
  byRoutine: RoutineBreakdown[];
}

/* ============================================================
   Automation / Routines (S13) — MIRRORS backend modules/automation/schema.py
   (Sprint 10A, FROZEN). A routine = a rule-based job (NO AI). lastRun/lastResult/
   runs from run_log; enabled is the persisted toggle. render-only.
   ============================================================ */
export type Trigger = "interval" | "cron" | "date" | "event";
export type RunResult = "ok" | "warn" | "error";

export interface RoutineInfo {
  id: string;
  name: string;
  trigger: Trigger;
  /** human display, e.g. "22:00 mỗi tối". */
  triggerLabel: string;
  desc: string;
  action: string;
  enabled: boolean;
  lastRun: string | null;
  lastResult: RunResult | null;
  runs: number;
}

export interface RoutinesView {
  routines: RoutineInfo[];
  /** enabled count → sidebar badge. */
  activeCount: number;
  total: number;
  runsToday: number;
  lastRunAt: string | null;
}

/** POST /routines/{id}/run → the recorded run. */
export interface RunResultView {
  id: string;
  status: RunResult;
  detail: string;
  startedAt: string;
  finishedAt: string;
}

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

/* ============================================================
   Graveyard (S4) — MIRRORS backend modules/graveyard/schema.py (Sprint 8, FROZEN).
   A grave = an abandoned project. lesson is null when not recorded (never
   fabricated). Derived pattern stats (avgPeak) carry their inputs. render-only.
   ============================================================ */
export interface GraveProject {
  id: string;
  name: string;
  /** abandonedProgress; fallback progress; else 0. */
  peak: number;
  reason: string;
  /** status.md lesson, else null (never fabricated). */
  lesson: string | null;
  /** abandonedAt ISO-8601 UTC; FE formats. */
  died: string;
  users: number;
  /** commit-age health — DISPLAY ONLY (abandoned ≠ dead). */
  health: string;
  repo: string;
}

export interface ReasonCount {
  reason: string;
  count: number;
}

export interface GraveyardStats {
  graves: GraveProject[];
  count: number;
  avgPeak: number;
  commonReasons: ReasonCount[];
  /** graves with users>0 at abandon. */
  reachedUser: number;
  /** graves with users==0 (build-to-90/0-user pattern). */
  beforeUser: number;
  lessons: string[];
}

export interface ClaudeUsage {
  model: string;
  used: number;
  cap: number;
  pct: number;
  remaining: number;
  /** STUB: null unless manual override. */
  resetIn: string | null;
  /** STUB: null unless manual override. */
  weekly: number | null;
  series: DayBurn[];
  today: number;
  avgPerDay: number;
  peak: DayBurn;
  byModel: ModelBurn[];
  costUSD: number;
  /** STUB this sprint: always null (per-project not in stats-cache). */
  byProject: null;
  asOf: string;
  stale: boolean;
  /** 'stats-cache' | 'manual'. */
  source: string;
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

/** GET /market `data` envelope — `{quotes, triggers, macro, alertHistory}`. */
export interface MarketData {
  quotes: AssetQuote[];
  triggers: AlertTrigger[];
  macro: MacroSignal[];
  alertHistory: AlertEvent[];
}
