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
