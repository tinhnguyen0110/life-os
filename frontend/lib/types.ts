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

/** One asset balance on OKX — mirrors `OkxBalance`. */
export interface OkxBalance {
  symbol: string;
  available: number;
  frozen: number;
  total: number;
  usdValue: number | null;
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
