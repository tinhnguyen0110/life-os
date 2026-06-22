
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

/* ---- Reminders (#27–#31 · GAP-4) — the single-user alarm/agenda module ----
   Mirrors the FROZEN backend reminders/schema.py (#28/#31 schema-freeze-gate).
   The UI is RENDER-ONLY: the backend computes `overdue` (un-done AND past-due),
   notified_count, done_at — the FE never date-compares to derive state. */
