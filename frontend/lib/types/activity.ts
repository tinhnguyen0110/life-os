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
