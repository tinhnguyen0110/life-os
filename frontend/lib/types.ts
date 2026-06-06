/* ============================================================
   Shared client types — MIRROR backend schema.py (do NOT invent shapes).
   C3 (ROADMAP §6) — the common status shape every reader returns.
   Locked Sprint 0; backend modules/projects/schema.py mirrors this in Sprint 1.
   Source of truth on divergence = backend schema.py.
   ============================================================ */

/** Project health state — ARCH §5 / mock data.js. */
export type ProjectHealth = "act" | "slow" | "stall" | "dead";

/** Per-project derived metrics (backend computes from git reader). */
export interface ProjectMetrics {
  commits: number;
  stars: number;
  lang: string;
  test_pass: number; // percent 0..100
}

/**
 * C3 — common ProjectStatus shape. Every project reader returns exactly this.
 * Verbatim from ROADMAP §6 / ARCH §5 / mock data.js (D2 in plan_sprint_0.md).
 */
export interface ProjectStatus {
  id: string;
  name: string;
  desc: string;
  health: ProjectHealth;
  progress: number; // percent 0..100
  users: number;
  last: string; // human "2h trước"
  lastDays: number; // idle days, derived
  next: string; // NEXT step
  repo: string;
  metrics: ProjectMetrics;
  routines: string[];
  lastAuto: string; // last auto-refresh, human
}

/** C4 — every endpoint answers this envelope (ROADMAP §6). */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  warning?: string;
}

/** /health payload (Sprint 0 — the only endpoint this sprint). */
export interface HealthData {
  status: string;
  modules: string[];
}
