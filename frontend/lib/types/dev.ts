/** One repo's activity on one VN-day. source "you" = attributed to you, "other" = team. */
export interface RepoDay {
  /** VN-day "YYYY-MM-DD". */
  date: string;
  repo: string;
  source: "you" | "other";
  commits: number;
  locAdded: number;
  locDeleted: number;
  /** first commit time "HH:MM" (VN), else null. */
  firstTs: string | null;
  /** last commit time "HH:MM" (VN), else null. */
  lastTs: string | null;
  /** first→last span "Hh Mm", "" when <2 commits. */
  activeSpan: string;
}
/** One VN-day's roll-up — repos active that day + YOUR totals (your-only). */
export interface DayView {
  date: string;
  /** every repo with activity that day (you + other). */
  repos: RepoDay[];
  /** YOUR commits that day (source="you" only). 0 when none attributed. */
  totalCommits: number;
  /** count of YOUR active repos that day. */
  activeRepos: number;
}
/** A repo's roll-up over the whole range (YOUR activity). */
export interface RepoSummary {
  repo: string;
  commits: number;
  locAdded: number;
  locDeleted: number;
  activeDays: number;
  /** last VN-day you touched it, else null. */
  lastActive: string | null;
}
/** The whole-range YOUR-activity summary (the KPI strip). */
export interface DevActivitySummary {
  totalCommits: number;
  activeDays: number;
  activeRepos: number;
  locAdded: number;
  locDeleted: number;
  /** ≤5 repos by your commits, desc. [] when no "you" attribution. */
  topRepos: RepoSummary[];
}
/** GET /dev_activity → the dev-activity board (render-only). honest-empty "you":
 *  DEV_TRACING_EMAILS unset → summary all-0, byRepo [], everything in otherRepos
 *  (tagged "other") + a warning. Render the empty-state-for-you + STILL show
 *  otherRepos as team context. */
export interface DevActivityOverview {
  /** the range covered (days), e.g. 90. */
  rangeDays: number;
  /** per-day, newest-first. */
  byDay: DayView[];
  /** YOUR repos, commits-desc. [] when no attribution. */
  byRepo: RepoSummary[];
  /** team-context rows (source "other") — tagged, NOT in your totals. */
  otherRepos: RepoDay[];
  summary: DevActivitySummary;
  scannedRepos: number;
  /** honest notices (e.g. "DEV_TRACING_EMAILS not set …"). Shown verbatim. */
  warnings: string[];
}
/** POST /dev_activity/scan → re-scan result. */
export interface DevScanResult {
  scannedRepos: number;
  days: number;
  rowsUpserted: number;
  yourCommits: number;
  warnings: string[];
}

/* ============================================================================
   #64 Repo Memory (REPOMEM) — per-repo durable knowledge surface. Two reads:
   code_insight (fresh-NOW git read: structure/README/commits/stack) + repo_memory
   (the durable curated Repos/<name> wiki note an agent writes as it learns the
   repo). RENDER-ONLY: the backend computes both; the FE displays. Mirrors the
   FROZEN #64 BE schema (code_insight + repo_memory, P1/P2 on origin).
   ============================================================================ */
/** One recent commit in a code_insight read. */
export interface RepoCommit {
  sha: string;
  msg: string;
  /** ISO date (YYYY-MM-DD). */
  date: string;
}
/** GET /code_insight?repo=<name|path> → a fresh-now structural read of a repo.
 *  honest: found:false → empty structure + a warning naming WHY (not crash/blank).
 *  asOf = the freshness stamp ("read just now"). readme is null when none readable. */
export interface CodeInsight {
  repo: string;
  /** the resolved root path on disk. */
  root: string;
  found: boolean;
  /** top-level entries (bounded by the backend). [] when not found. */
  structure: string[];
  /** README excerpt (markdown) or null when none. */
  readme: string | null;
  /** recent commits, newest-first. */
  recentCommits: RepoCommit[];
  /** detected stack tags, e.g. ["docker", "python"]. */
  stack: string[];
  /** ISO-8601 freshness stamp of this read. */
  asOf: string;
  /** honest notices (e.g. "repo 'x' not found under the configured roots"). */
  warnings: string[];
}
/** The durable repo_memory note (the Repos/<repo> wiki note). null when none yet. */
export interface RepoMemoryNote {
  id: string;
  title: string;
  /** markdown body. */
  body: string;
  /** ISO-8601 last-updated. */
  updated: string;
}
/** GET /code_insight/memory?repo=<name> → the curated durable memory note for a
 *  repo. honest: found:false + note:null → "no memory note yet for this repo"
 *  (an agent writes it over time) — an empty-state, NOT an error/blank. */
export interface RepoMemory {
  repo: string;
  note: RepoMemoryNote | null;
  found: boolean;
}

/* ============================================================================
   #6 / #88 MCP key scoping — per-key tool visibility. A key sees the UNION of:
   the tools of each whole DOMAIN (mount label) it's scoped to + each explicit TOOL
   name. Mirrors the FROZEN #86 CRUD schema (Scope/KeyCreate/KeyUpdate + the row).
   ============================================================================ */
