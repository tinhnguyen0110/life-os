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

/* ============================================================
   Settings / AppConfig (S12) — MIRRORS backend modules/settings/schema.py (FROZEN).
   Global app-config the Settings screen edits + routines read. PATCH is partial
   (every field optional → AppConfigPatch); a bad field is a PER-FIELD 422 (FastAPI
   detail[] with loc:["body",<field>]). Defaults = current hardcoded behavior.
   ============================================================ */
export type ErrorChannel = "discord" | "inapp" | "none";

export interface AppConfig {
  automationEnabled: boolean;
  /** hour-of-day 0-23 (UTC) morning-pull + brief run. */
  briefHour: number;
  /** idle-hunter flags projects idle > this many days (≥1). */
  idleThresholdDays: number;
  patternCheckEnabled: boolean;
  errorChannel: ErrorChannel;
  /** display timezone label (stored-only this sprint), 1-64 chars. */
  timezone: string;
  /** owner display name (stored-only; may be empty), ≤80 chars. */
  displayName: string;
  /** W4d (USER-ORDERED, reverses D8 proposals-only): ON = agent writes land in the
   *  wiki vault DIRECTLY (auto-accepted at the create_proposal chokepoint, decidedBy
   *  "agent:auto", still fully audited); OFF (default) = proposals-only, human ratifies
   *  in P1. Optional in the TS type because the backend field lands in W4d-BE (parallel) —
   *  the FE treats a missing value as `false` (safe default) so it's robust pre-BE. */
  wikiAgentAutonomous?: boolean;
  /** FINANCE-ASSISTANT capital-tilt (user-configurable): the USD thresholds that pick
   *  the allocation capitalTier ("small" below smallUsd, scaling toward largeUsd). The
   *  decision/allocation tilt reads these — surfaced here so the user can tune them. */
  riskCapitalSmallUsd?: number;
  riskCapitalLargeUsd?: number;
}

/** Partial update — only provided keys change. extra=forbid (unknown key → 422). */
export type AppConfigPatch = Partial<AppConfig>;

/** One FastAPI validation error item (PATCH 422 → { detail: ValidationErrorItem[] }).
 *  loc is ["body", <fieldName>, ...]; loc[1] names the offending field. */
export interface ValidationErrorItem {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

/* ============================================================
   Brief (S11) — MIRRORS backend modules/brief/schema.py (S11, FROZEN).
   Template-based daily roll-up (NO AI — source is "template", NOT an opus/model
   label). priorities severity-ordered (urgent>warn>info), capped ~5; [] = honest
   "ổn định" calm state (nothing urgent, NOT a failure). summary numbers null where
   the source is down (honest no-data, not a fabricated 0).
   ============================================================ */
export type Severity = "info" | "warn" | "urgent";
export type PrioritySource = "market" | "projects" | "claude" | "finance" | "alerts";

export interface Priority {
  /** 1-based DISPLAY rank after the severity sort (1 = most severe; 0 = pre-sort placeholder). */
  n: number;
  text: string;
  source: PrioritySource;
  severity: Severity;
}

export interface BriefSummary {
  netWorth: number | null;
  projectsActive: number;
  claudePct: number | null;
  alertsToday: number;
}

export interface Brief {
  generatedAt: string;
  asOf: string;
  /** "template" — rule-based, NOT AI this build. */
  source: string;
  summary: BriefSummary;
  /** severity-ordered, capped ~5; [] = honest calm state. */
  priorities: Priority[];
  /** any source stale (claude cache old) → don't imply live. */
  stale: boolean;
  warnings: string[];
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

/* ============================================================
   OKX Exchange — mirrors modules/exchange/schema.py
   ============================================================ */

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

/* ============================================================
   Wiki / Knowledge vault (W1–W5) — MIRRORS backend modules/wiki/schema.py
   (Sprint W1a, FROZEN) + the W1c reader shapes (backlinks / inbox). Integer-ID
   PKM notes — SEPARATE from the string-ID `notes` module above. Frozen contract:
   end_sprint_W1c §3 (12 endpoints, envelope {success,data,warning?}).
   AI-derived fields (aiSuggest / suggestions) are null/empty at M1 — M4 (Claude
   Code via MCP) populates them. Render the empty state, never fabricate.
   ============================================================ */
export type WikiStatus = "fleeting" | "developing" | "evergreen";
export type WikiNoteType = "concept" | "literature";
export type WikiTrustTier = "verified" | "candidate";

/** A stored wiki note — mirrors `Note` (GET /wiki/notes/{id}). `id` is the
 *  immutable integer identity; `title` is mutable ("" for a raw fleeting capture).
 *  `contentHash` = sha256 of the body. Timestamps ISO-8601 UTC, server-set. */
export interface WikiNote {
  id: number;
  title: string;
  aliases: string[];
  status: WikiStatus;
  noteType: WikiNoteType;
  trustTier: WikiTrustTier;
  /** "human" | "agent:<name>". */
  author: string;
  tags: string[];
  /** markdown body (may contain `[[id|title]]` wikilinks). */
  content: string;
  created: string;
  updated: string;
  contentHash: string;
}

/** POST /wiki/notes body — mirrors `NoteCreateInput`. id/timestamps server-assigned.
 *  A fleeting capture legitimately has no title; links/title come at REFINE. */
export interface WikiNoteCreateInput {
  content?: string;
  title?: string;
  status?: WikiStatus;
  noteType?: WikiNoteType;
  tags?: string[];
  author?: string;
  /** command_bar | quick_add | mcp_agent | daily_note (free-form; default quick_add). */
  captureSource?: string;
}

/** PUT /wiki/notes/{id} (+ POST .../refine) body — mirrors `NoteUpdateInput`.
 *  Partial: a field left undefined is unchanged; a present field overwrites.
 *  Bad enum value → per-field 422 (ApiError.fieldErrors()). */
export interface WikiNoteUpdateInput {
  title?: string;
  content?: string;
  status?: WikiStatus;
  noteType?: WikiNoteType;
  trustTier?: WikiTrustTier;
  aliases?: string[];
  tags?: string[];
  /** WEXP: virtual folder path ("/"-delimited). Move = set this (no .md rewrite).
   *  Optional; the WEXP-BE PUT accepts it once that lands. */
  folder?: string;
}

/** One inbound linked mention (GET /wiki/notes/{id}/backlinks → linked[]). The
 *  `snippet` is body text around the mention, may carry `<b>`-highlight HTML.
 *  `anchor` = the `^block-id` the mention sits in, when present. */
export interface WikiLinkedMention {
  id: number;
  title: string;
  snippet: string;
  anchor?: string;
}

/** One unlinked mention (backlinks → unlinked[]) — a note that names this title/
 *  alias in prose but hasn't linked it (FTS-derived; "link nó" candidate). */
export interface WikiUnlinkedMention {
  id: number;
  title: string;
  snippet: string;
}

/** One outbound edge (backlinks → outbound[]). Resolved → {id,title,isResolved:true};
 *  ghost (target note doesn't exist yet) → {ghost,isResolved:false}. Discriminate
 *  on `isResolved` / presence of `id` vs `ghost`. */
export type WikiOutboundLink =
  | { id: number; title: string; isResolved: true; ghost?: undefined }
  | { ghost: string; isResolved: false; id?: undefined };

/** GET /wiki/notes/{id}/backlinks — mirrors reader.backlinks (W1c). */
export interface WikiBacklinks {
  linked: WikiLinkedMention[];
  unlinked: WikiUnlinkedMention[];
  outbound: WikiOutboundLink[];
}

/** One inbox (fleeting) item — mirrors reader.inbox (W1c). `aiSuggest` is null at
 *  M1 (no embedded AI); the shape is kept so M4 slots in unchanged. */
export interface WikiInboxItem {
  id: number;
  /** null = no title yet (raw fleeting capture). */
  title: string | null;
  status: WikiStatus;
  /** body snippet of the raw capture. */
  rawContent: string;
  /** ISO/display capture time. */
  captured: string;
  /** command_bar | quick_add | mcp_agent | daily_note. */
  captureSource: string;
  /** outbound resolved-link count (drives the ≥1-link refine gate, server-enforced). */
  linkCount: number;
  /** null at M1 — M4 populates {titleClaim,summary,atomicityFlag,dupeOf}. */
  aiSuggest: WikiAiSuggest | null;
}

/** GET /wiki/inbox payload — mirrors reader.inbox. */
export interface WikiInbox {
  items: WikiInboxItem[];
}

/** AI refine suggestion for an inbox item — null at M1, M4 populates. */
export interface WikiAiSuggest {
  titleClaim: string;
  summary: string;
  atomicityFlag: string;
  dupeOf: { id: number; title: string; similarity: number } | null;
}

/** One AI link-suggestion (GET /wiki/notes/{id}/suggestions). EMPTY at M1 (no
 *  embedded AI) — render the empty state, M4 populates via Claude Code. */
export interface WikiSuggestion {
  id: number;
  title: string;
  why: string;
  confidence: number;
  state: "candidate" | "accepted" | "rejected" | "pinned";
}

/* ---- W1 Vault Overview (GET /wiki/overview) — mirrors reader.overview ---- */

/** op-log op kind. M1 emits create/edit/link/refine/merge/delete; the agent kinds
 *  (link_candidate/moc_proposal) are in the enum for M4 but never produced now. */
export type WikiOpKind =
  | "create" | "edit" | "link" | "link_candidate"
  | "refine" | "merge" | "moc_proposal" | "delete";

/** Vault-wide counters. `pctWithLink` is null on an empty vault (no denominator). */
export interface WikiVaultStats {
  totalNotes: number;
  byStatus: { fleeting: number; developing: number; evergreen: number };
  totalLinks: number;
  orphanCount: number;
  ghostLinkCount: number;
  /** % of notes with ≥1 link; null when totalNotes==0 (avoid div-by-zero). */
  pctWithLink: number | null;
  asOf: string;
}

/** One orphan-sweep row (degree-0 / stale note). */
export interface WikiOrphan {
  id: number;
  title: string | null;
  status: WikiStatus;
  degree: number;
  lastTouched: string;
}

/** One op-log activity row (recentActivity[], newest→oldest). `detail`/`noteTitle`
 *  may be empty/null. `actor` = human | agent (agent never auto-writes at M1). */
export interface WikiActivity {
  ts: string;
  op: WikiOpKind;
  actor: "human" | "agent";
  noteId: number;
  noteTitle: string;
  detail: string | null;
}

/** GET /wiki/overview payload — mirrors reader.overview. `inbox`/`orphans` are
 *  short summaries (full lists live on W3 / W4). `proposalCount` is 0 at M1. */
export interface WikiOverview {
  stats: WikiVaultStats;
  inbox: WikiInboxItem[];
  orphans: WikiOrphan[];
  recentActivity: WikiActivity[];
  proposalCount: number;
}

/* ---- W4 Graph Explorer (GET /wiki/graph?note=X&depth=N) — mirrors reader.graph ---- */

/** One graph node. The API does NOT carry x/y — the FE computes a radial ego-layout
 *  client-side (center fixed, neighbors on rings by hop distance). */
export interface WikiGraphNode {
  id: number;
  title: string;
  status: WikiStatus;
  degree: number;
}

/** One typed edge. `type` ∈ relates|supports|contradicts|refines|example_of (M1
 *  typed graph). `isResolved=false` = ghost target (note not yet created). */
export interface WikiGraphEdge {
  source: number;
  target: number;
  type: string;
  isResolved: boolean;
}

/** One AI-detected cluster (MOC candidate). EMPTY at M1 (no embedded clustering);
 *  the shape is kept so M4/W5 slot in unchanged. */
export interface WikiGraphCluster {
  label: string;
  noteIds: number[];
  density: number;
  mocSuggestion: boolean;
}

/** GET /wiki/graph payload — mirrors reader.graph. Ego-graph around `center`.
 *  `clusters` uses the SAME shape the backend ego-graph emits (reader.detect_clusters
 *  → {members, size, density, importance, suggestedTitle}) — NOT the stale
 *  WikiGraphCluster ({label, noteIds}), which the backend never returns. */
export interface WikiGraph {
  /** ego center note id; null for the GLOBAL (whole-vault) graph. */
  center: number | null;
  nodes: WikiGraphNode[];
  edges: WikiGraphEdge[];
  clusters: WikiCluster[];
}

/** One FTS5 search hit (GET /wiki/search?q=). EMPTY array when no match. */
export interface WikiSearchHit {
  id: number;
  title: string | null;
  status: WikiStatus;
  snippet: string;
}

/* ---- P1 Proposal Queue (W4a) — MIRRORS backend modules/wiki/proposals_schema.py.
   The single review surface for every AI-proposed mutation. Trust boundary: AI
   write-back ALWAYS lands here as `pending` first; a human accepts/rejects — AI
   NEVER edits an evergreen note's body in place. ---- */

/** Proposal kind enum — frozen W4a (proposals_schema.ProposalKind). NOT the mock's
 *  aspirational link_candidate/moc_proposal set; build to the live contract. */
export type WikiProposalKind =
  | "note_create" | "note_edit" | "link_add" | "link_remove" | "merge" | "moc";

/** pending → accepted | rejected (terminal). */
export type WikiProposalStatus = "pending" | "accepted" | "rejected";

/** One stored proposal (GET /wiki/proposals → data.proposals[]). `payload` is a
 *  kind-specific dict (note_edit→{title?,content?,status?,...} · link_add→{target,display?}
 *  · merge→{sourceId,targetId} · …) rendered generically. `decided*`/`appliedNoteId`
 *  are set only once a human decides; `appliedNoteId` deep-links the applied note. */
export interface WikiProposal {
  id: number;
  kind: WikiProposalKind;
  /** the note the proposal acts on (edit/merge target); null for some link/create. */
  targetId: number | null;
  payload: Record<string, unknown>;
  rationale: string;
  /** "agent" | "agent:<name>" | "human". */
  actor: string;
  status: WikiProposalStatus;
  correlationId: string | null;
  created: string;
  decided: string | null;
  decidedBy: string | null;
  appliedNoteId: number | null;
}

/** GET /wiki/proposals payload — mirrors reader. `counts` drives the queue badge /
 *  filter chips. `proposals: []` on an empty queue (honest empty, never null). */
export interface WikiProposalList {
  proposals: WikiProposal[];
  counts: Partial<Record<WikiProposalStatus, number>>;
}

/** Accept/reject body (DecideInput) — `decidedBy` defaults to "human" server-side. */
export interface WikiDecideInput {
  decidedBy?: string;
}

/** Batch-accept body (BatchAcceptInput). `ids` must be non-empty. */
export interface WikiBatchAcceptInput {
  ids: number[];
  decidedBy?: string;
}

/** One per-id result from POST /wiki/proposals/accept-batch. `ok=false` carries
 *  `error` (e.g. "not found" / apply-failed); `ok=true` carries the applied proposal. */
export interface WikiBatchAcceptResultItem {
  id: number;
  ok: boolean;
  proposal?: WikiProposal;
  error?: string;
}

/** POST /wiki/proposals/accept-batch response. A batch can PARTIALLY succeed
 *  (200 envelope with accepted>0 AND failed>0) — the UI must surface failed, not
 *  treat the 200 as all-success. */
export interface WikiBatchAcceptResult {
  results: WikiBatchAcceptResultItem[];
  accepted: number;
  failed: number;
}

/* ---- W5 SYNTHESIZE / MOC (W5a) — MIRRORS backend reader.clusters / reader.mocs.
   Substrate only: clusters are detected by CODE (graph community detection,
   deterministic, NO vector/AI); MOC drafting + throughline + contradiction are the
   EXTERNAL Claude Code (MCP) job (ARCH §11, D-W5.4) — this screen lists the substrate
   + hints "ask Claude Code to draft", it does NOT fabricate an AI workspace. ---- */

/** One cluster member (id + title). title null = untitled note. */
export interface WikiClusterMember {
  id: number;
  title: string | null;
}

/** One detected cluster = MOC candidate (GET /wiki/clusters → data.clusters[]).
 *  `importance` = size×density is ADVISORY (D-W5.3) — ranks candidates, never gates.
 *  `suggestedTitle` is a deterministic hint, NOT an AI-generated title. */
export interface WikiCluster {
  members: WikiClusterMember[];
  size: number;
  density: number;
  importance: number;
  suggestedTitle: string | null;
}

/** GET /wiki/clusters payload. Empty = no cluster meets the size/density threshold. */
export interface WikiClusterList {
  clusters: WikiCluster[];
}

/** One MOC note (GET /wiki/mocs → data.items[]) — a noteType="moc" note. */
export interface WikiMoc {
  id: number;
  title: string | null;
  status: WikiStatus;
  created: string;
  updated: string;
  outboundLinks: number;
}

/** GET /wiki/mocs payload. Empty = no MOC notes yet (none ratified). */
export interface WikiMocList {
  items: WikiMoc[];
}

/* ---- A1b Citation verify (W7) — MIRRORS POST /wiki/citations/verify. The SPEC
   surface (L257): grounded Q&A is EXTERNAL Claude Code (MCP), NOT an in-app chat;
   the FE shows "answered via MCP, N citations verified" + click→note+span. This is
   the verify display, deterministic CODE post-verification of LLM-returned cites. ---- */

/** One claim to verify. `noteId`/`span` null = ungrounded (no citation given). */
export interface WikiCitation {
  claim: string;
  noteId?: number | null;
  span?: string | null;
}

/** POST /wiki/citations/verify body. */
export interface WikiCitationVerifyInput {
  claims: WikiCitation[];
}

/** verified = span found in the cited note · weaklyGrounded = note exists, span
 *  fuzzy/partial · rejected = cited note/span absent · ungrounded = no citation. */
export type WikiCitationStatus = "verified" | "weaklyGrounded" | "rejected" | "ungrounded";

/** One verify result. `resolvedNoteId` = the note the citation actually resolves to
 *  (for click→jump); `reason` = machine code (span_not_in_note / no_citation / …). */
export interface WikiCitationResult {
  claim: string;
  noteId: number | null;
  status: WikiCitationStatus;
  reason: string;
  resolvedNoteId: number | null;
}

export interface WikiCitationSummary {
  verified: number;
  rejected: number;
  ungrounded: number;
  weaklyGrounded: number;
  total: number;
}

/** POST /wiki/citations/verify response. */
export interface WikiCitationVerifyResult {
  results: WikiCitationResult[];
  summary: WikiCitationSummary;
}

/* ---- A1a M3 sync conflicts (W7, deferred from A1a) — MIRRORS reader sync_store.
   Block-level LWW convergence keeps EVERY version (0 data loss); a TRUE conflict
   (same note+block edited divergently) is surfaced here for human resolution. ---- */

/** One kept version of a conflicting block (the LWW loser is recoverable). */
export interface WikiConflictVersion {
  device: string;
  content: string;
  ts: string;
}

/** One detected conflict (GET /wiki/sync/conflicts → data.conflicts[]). */
export interface WikiConflict {
  id: number;
  noteId: number;
  blockIndex: number;
  versions: WikiConflictVersion[];
  status: "open" | "resolved";
  detected: string;
  resolved: string | null;
}

/** GET /wiki/sync/conflicts payload. Empty = no open conflicts (honest). */
export interface WikiConflictList {
  conflicts: WikiConflict[];
}

/** POST /wiki/sync/conflicts/{id}/resolve body — human picks the winning content,
 *  written THROUGH the single-writer queue (update_note) for one auditable path. */
export interface WikiConflictResolveInput {
  noteId: number;
  content: string;
}

/* ---- Wiki Explorer tree (WEXP) — GET /wiki/tree. MIRRORS the frozen WEXP-BE shape:
   a RECURSIVE nested node {name, path, folders[], notes[]} built from notes' virtual
   `folder` field (NOT physical folders — flat 47.md preserved). Root node has name/
   path "". The backend pre-nests the tree (the FE renders it directly, no flattening). */

export interface WikiTreeNote {
  id: number;
  title: string | null;
}

/** A recursive folder node. `path` = "/"-delimited virtual path ("" = vault root);
 *  `folders` = subfolders (same shape); `notes` = notes directly in this folder. */
export interface WikiTreeNode {
  name: string;
  path: string;
  folders: WikiTreeNode[];
  notes: WikiTreeNote[];
}

/** GET /wiki/tree payload = the root WikiTreeNode (data IS the node). */
export type WikiTree = WikiTreeNode;

/* ---- Decision Journal + Calibration (W7-A2 / F1-H1) — MIRRORS backend
   modules/decision_journal/schema.py. A GENERAL decision (not a trade): decision +
   thesis + falsification condition + confidence% (the probability claim) → on
   resolve, an outcome (right/wrong on the THESIS axis) drives calibration. Brier +
   confidence-band + rule-based domain bias-cluster. ---- */

export type DecisionStatus = "open" | "resolved";
export type DecisionOutcome = "right" | "wrong";

/** A stored decision (GET → data.entries[]). `id` is a STRING (slug-ish). `predicted`
 *  null → Brier derives it from confidence/100. `outcome` null while open. */
export interface DecisionEntry {
  id: string;
  decision: string;
  thesis: string | null;
  falsificationCondition: string | null;
  /** probability claim 0-100 (REQUIRED). */
  confidence: number;
  /** explicit 0-1 prob; null → derive confidence/100. */
  predicted: number | null;
  date: string;
  /** free-form bias-cluster key (investment/project/...). */
  domain: string;
  status: DecisionStatus;
  outcome: DecisionOutcome | null;
  lesson: string | null;
  createdAt: string;
  updatedAt: string;
}

/** POST body (DecisionInput) — id/timestamps server-set. confidence REQUIRED. */
export interface DecisionCreateInput {
  decision: string;
  thesis?: string | null;
  falsificationCondition?: string | null;
  confidence: number;
  predicted?: number | null;
  date?: string;
  domain: string;
  status?: DecisionStatus | null;
  outcome?: DecisionOutcome | null;
  lesson?: string | null;
  /** the EV thesis at decision time (e.g. "positive_asymmetric"); backend str ≤2000.
   *  Read-back across decision_journal/service.py (RL-reward / anti-resulting core). */
  expectedEv?: string | null;
  /** the accepted worst-case downside at decision time; backend str ≤2000. */
  worstCase?: string | null;
  /** the decision_weight W (∏q) logged at decision time, if any; backend float 0–1.
   *  Lets the user paste the W from the /decision cockpit → closes the read→log loop. */
  decisionWeight?: number | null;
}

/** PUT body (DecisionPatch) — ALL optional; a partial resolve is
 *  `{status:"resolved", outcome:"right"}` (no need to resend required fields). */
export interface DecisionPatchInput {
  decision?: string;
  thesis?: string | null;
  falsificationCondition?: string | null;
  confidence?: number | null;
  predicted?: number | null;
  date?: string;
  domain?: string | null;
  status?: DecisionStatus | null;
  outcome?: DecisionOutcome | null;
  lesson?: string | null;
}

/** One confidence band vs actual outcome-right rate (resolved+confident only). */
export interface DecisionCalibrationBand {
  band: string;
  predicted: number;
  /** %(outcome=='right') within the band — the THESIS axis. */
  actual: number;
  n: number;
}

/** A domain whose resolved-wrong-rate exceeds the threshold over the min sample
 *  (rule-based bias detection, min-n gated). */
export interface DecisionBiasFlag {
  domain: string;
  wrongRate: number;
  n: number;
}

/** GET /decision-journal payload — entries + derived calibration/bias stats.
 *  `brier` null if 0 resolved (lower=better). */
export interface DecisionJournalData {
  entries: DecisionEntry[];
  count: number;
  resolvedCount: number;
  brier: number | null;
  calibration: DecisionCalibrationBand[];
  biasFlags: DecisionBiasFlag[];
}

/* ============================================================
   Career cockpit (CAR-1) — MIRROR backend modules/career/schema.py EXACTLY.
   Three resources: living CV (parsed sections + proof), blog posts, demos.
   ============================================================ */

/** Which surface a CV proof chip points at. */
export type ProofKind = "case-study" | "blog" | "demo" | "repo" | "url";

/** A clickable evidence chip on a CV section. */
export interface ProofLink {
  kind: ProofKind;
  label: string;
  /** id (blog/demo) or url. */
  ref: string;
}

/** One parsed H2 section of the living CV (body = raw markdown). */
export interface CvSection {
  id: string;
  heading: string;
  level: number;
  body: string;
  proof: ProofLink[];
}

/** CV header block (name / title / contact line). */
export interface CvMeta {
  name: string;
  title: string;
  contact: string;
}

/** The full living CV. */
export interface Cv {
  meta: CvMeta;
  sections: CvSection[];
  updatedAt: string | null;
  /** True if still the seeded source CV (vs user-edited). */
  seeded: boolean;
}

export type BlogStatus = "draft" | "published";

/** A blog post's metadata (dek = the short description / notes, not full article). */
export interface BlogPost {
  id: string;
  title: string;
  subtitle: string;
  dek: string;
  status: BlogStatus;
  url: string | null;
  tags: string[];
  publishedDate: string | null;
  readMinutes: number | null;
  wordCount: number | null;
  createdAt: string;
  updatedAt: string;
}

/** POST/PUT body for a blog post (id + timestamps server-set). */
export interface BlogInput {
  title: string;
  subtitle?: string;
  dek?: string;
  status?: BlogStatus;
  url?: string | null;
  tags?: string[];
  publishedDate?: string | null;
  readMinutes?: number | null;
  wordCount?: number | null;
}

export type DemoStatus = "live" | "wip" | "offline";

/** A live demo / flagship project in the showcase. */
export interface DemoItem {
  id: string;
  name: string;
  tagline: string;
  desc: string;
  url: string | null;
  repo: string | null;
  status: DemoStatus;
  tags: string[];
  loc: number | null;
  createdAt: string;
  updatedAt: string;
}

/** POST/PUT body for a demo item (id + timestamps server-set). */
export interface DemoInput {
  name: string;
  tagline?: string;
  desc?: string;
  url?: string | null;
  repo?: string | null;
  status?: DemoStatus;
  tags?: string[];
  loc?: number | null;
}

/* ============================================================
   Decision tower (FINANCE-ASSISTANT P1–P4) — MIRRORS the LIVE /decision/* payloads
   (curled on :8686). The tower is NEUTRAL by backend design: it surfaces DATA + the
   guardian's QUESTIONS, never advice. SELF-DESCRIBING RAW: every q/W/delta is
   backend-computed (W = ∏ layer-q, pure product, NO clamp) — the FE renders + formats
   + colors, NEVER recomputes. Two distinct numbers (§116): `weight` = signal strength
   (∏ of layer q); `confidence` = trust in the measurement — render them as DISTINCT
   visuals, never one conflated "score".
   ============================================================ */

/** One layer of the W breakdown — its quality q + a self-describing note. */
export interface DecisionLayer {
  /** which layer: q_cycle | q_macro | q_flow | s_asset. */
  layer: string;
  /** the layer's quality 0–1 (the dimmest layer is the bindingConstraint). */
  q: number;
  /** human note: what the layer measured + why this q (source/coverage). */
  note: string;
}

/** GET /decision/weight — the decision-weight gauge. weight = ∏ layer-q (no clamp);
 *  verdict is a WORD (e.g. "thin") rendered verbatim; bindingConstraint names the
 *  dimmest layer; confidence is a SEPARATE trust number (weight≠confidence). */
export interface DecisionWeight {
  /** W = ∏ of the layers' q (pure product, no clamp). */
  weight: number;
  /** the verdict WORD (e.g. "thin") — render verbatim, NEVER editorialize to advice. */
  verdict: string;
  breakdown: DecisionLayer[];
  /** the layer name that's the limiting (dimmest) factor. */
  bindingConstraint: string;
  /** "W = q1 × q2 × … = W; dimmest layer = X" — the self-describing math. */
  explanation: string;
  /** trust in the measurement (0–1) — DISTINCT from weight. Low → "thin signal". */
  confidence: number;
  /** the two-number legend string (§116) — render it so the user sees the distinction. */
  legend: string;
}

/** One Investment-Clock axis (growth / inflation / yield_curve). */
export interface CycleAxis {
  axis: string;
  /** "up" | "down" | "flat". */
  direction: string;
  /** false = this axis is mock/missing (lowers coverage) → render honestly. */
  present: boolean;
  detail: string;
}

/** One indicator inside qCycle.breakdown (freshness/age provenance per input). */
export interface CycleQInput {
  name: string;
  present: boolean;
  value: number | null;
  ageDays: number | null;
  freshness: number | null;
  source: string;
}

/** qCycle — the cycle layer's quality decomposed (freshness×coverage×agreement). */
export interface CycleQ {
  q: number;
  freshness: number;
  coverage: number;
  agreement: number;
  breakdown: CycleQInput[];
  presentInputs: number;
  neededInputs: number;
}

/** GET /decision/macro-cycle — the Investment-Clock phase + axes + the cycle q. */
export interface MacroCycle {
  /** the clock phase (e.g. "overheat") — a DATA label, not an instruction. */
  phase: string;
  axes: CycleAxis[];
  qCycle: CycleQ;
}

/** Per-channel numeric maps for the allocation reference. */
export interface AllocTargets {
  crypto: number;
  etf: number;
  vn: number;
  dry: number;
}

/** GET /decision/allocation — REFERENCE weighting (clock + capital size) surfaced as
 *  DATA, not an instruction. targets = reference %, vsStaticGoldenPath = the delta (pp)
 *  vs the static golden-path, rationale = per-channel why. The `note` says "You decide". */
export interface DecisionAllocation {
  phase: string;
  /** "small" | "large" — which capital tier drove the tilt. */
  capitalTier: string;
  /** reference weighting % per channel. */
  targets: AllocTargets;
  /** per-channel rationale string (self-describing tilts). */
  rationale: Record<string, string>;
  /** delta in pp vs the static golden-path per channel. */
  vsStaticGoldenPath: AllocTargets;
  confidence: number;
  note: string;
}

/** One guardian alert — `msg` is a QUESTION (rendered verbatim, never an imperative);
 *  evidence carries the numbers behind the question; sources name the tools used. */
export interface GuardianAlert {
  /** "high" | "low" | ... — drives the card tone, NOT urgency-to-act. */
  severity: string;
  /** the alert text — a QUESTION the guardian raises. Render VERBATIM (NEUTRAL). */
  msg: string;
  /** the numbers behind the question (e.g. {stablePct, fearGreed}). */
  evidence: Record<string, unknown>;
  /** the tool(s) the guardian read to raise this. */
  sources: string[];
}

/** GET /decision/guardian — risk QUESTIONS (NOT advice). [] alerts = nothing to flag. */
export interface DecisionGuardian {
  alerts: GuardianAlert[];
  confidence: number;
  asOf: string;
  note: string | null;
}

/** One NAV point — the portfolio net-asset-value on a given day. */
export interface NavPoint {
  date: string;
  nav: number;
}

/** GET /decision/nav-history — the NAV series. SHORT-SERIES HONESTY: when `points` is
 *  small (only 2 live), `warning` says "still accumulating" + confidence is low → the
 *  UI must NOT draw a confident trend from 2 points. */
export interface NavHistory {
  series: NavPoint[];
  points: number;
  range: { from: string; to: string };
  confidence: number;
  /** short-series caveat (null when the series is long enough). */
  warning: string | null;
}
