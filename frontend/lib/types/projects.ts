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
  /** #113 — how this project entered the registry: "config" (explicit config),
   *  "registered" (manual register), "auto" (auto-discovered from DEV_TRACING_ROOTS). */
  source: ProjectSource;
  /** #113 — hidden from the default list (≠ abandoned; a soft UI-hide). include=hidden
   *  surfaces it. */
  hidden: boolean;
}
/** #113 — project registry source. */
export type ProjectSource = "config" | "registered" | "auto";
/** #112 — per-project git dev-activity (GET /projects/{id}/dev-activity?days=N).
 *  honest-mirror: found:false → the repo isn't in the dev_activity scan; render an
 *  honest "chưa track git" with `reason`, NEVER a fake commits:0-as-real. */
export interface ProjectDevActivity {
  projectId: string;
  /** false → not in the scan (DEV_TRACING_ROOTS) → honest "untracked", not real 0s. */
  found: boolean;
  commits: number;
  /** net LOC (added − deleted) over the window. */
  locNet: number;
  /** VN-day of the last commit, null when none/untracked. */
  lastActiveDay: string | null;
  days: number;
  activeDays: number;
  /** the matched repo(s) for this project. */
  matches: { repo: string; commits: number; locNet: number; lastActiveDay: string | null; activeDays: number }[];
  /** when found:false — why (e.g. "repo not in the dev_activity scan…"). */
  reason: string | null;
  warning: string | null;
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
