/* ============================================================
   #97 — dev-activity analyst stats (PURE, testable, render-only). All derived from the
   EXISTING /dev_activity fields (summary/byRepo/byDay) — NO backend, NO faked numbers.
   honest-mirror: a no-attribution range → the derivations return null/empty, never a
   fabricated stat. Keep these pure so the editor logic is unit-tested without a DOM.
   ============================================================ */
import type { DayView, RepoDay, RepoSummary, DevActivitySummary } from "@/lib/types";

/** net LOC = added − deleted. null when both inputs are null/undefined (no data). */
export function netLoc(added: number | null | undefined, deleted: number | null | undefined): number | null {
  if (added == null && deleted == null) return null;
  return (added ?? 0) - (deleted ?? 0);
}

/** commits per ACTIVE day = totalCommits / activeDays. null when 0 active days (no
 *  attribution) — NOT a fake 0 or a divide-by-zero. */
export function commitsPerDay(totalCommits: number, activeDays: number): number | null {
  if (activeDays <= 0) return null;
  return totalCommits / activeDays;
}

/** The YOUR-commit start-hour distribution (0–23 → count), derived from byDay's
 *  source="you" RepoDays' firstTs. HONEST — we surface the real pattern (incl a
 *  night-owl 0:00 peak) and do NOT smooth/normalize it away. Empty map when no "you". */
export function peakHours(byDay: DayView[]): Record<number, number> {
  const dist: Record<number, number> = {};
  for (const day of byDay) {
    for (const rd of day.repos) {
      if (rd.source === "you" && rd.firstTs) {
        const h = parseInt(rd.firstTs.split(":")[0], 10);
        if (Number.isFinite(h) && h >= 0 && h <= 23) dist[h] = (dist[h] ?? 0) + 1;
      }
    }
  }
  return dist;
}

/** The single busiest start-hour (the mode of the distribution), or null when empty.
 *  Ties → the EARLIER hour (stable). Honest: null when no "you" attribution. */
export function peakHour(dist: Record<number, number>): number | null {
  const entries = Object.entries(dist).map(([h, c]) => [Number(h), c] as [number, number]);
  if (entries.length === 0) return null;
  entries.sort((a, b) => (b[1] - a[1]) || (a[0] - b[0])); // count desc, then hour asc
  return entries[0][0];
}

/** Total active-span across the range — the sum of YOUR per-day first→last spans, in
 *  MINUTES. Derived from firstTs/lastTs of source="you" RepoDays (one span per day =
 *  the day's earliest first → latest last). null when no "you" attribution. */
export function totalActiveMinutes(byDay: DayView[]): number | null {
  let total = 0;
  let any = false;
  for (const day of byDay) {
    let dayFirst: number | null = null;
    let dayLast: number | null = null;
    for (const rd of day.repos) {
      if (rd.source !== "you") continue;
      if (rd.firstTs) { const m = toMinutes(rd.firstTs); if (m != null) dayFirst = dayFirst == null ? m : Math.min(dayFirst, m); }
      if (rd.lastTs) { const m = toMinutes(rd.lastTs); if (m != null) dayLast = dayLast == null ? m : Math.max(dayLast, m); }
    }
    if (dayFirst != null && dayLast != null && dayLast >= dayFirst) { total += dayLast - dayFirst; any = true; }
  }
  return any ? total : null;
}

function toMinutes(hhmm: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm);
  if (!m) return null;
  const h = Number(m[1]), mi = Number(m[2]);
  if (h < 0 || h > 23 || mi < 0 || mi > 59) return null;
  return h * 60 + mi;
}

/** "Hh Mm" / "Mm" from minutes. null → "—". */
export function fmtMinutes(min: number | null): string {
  if (min == null) return "—";
  const h = Math.floor(min / 60), m = Math.round(min % 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/** Velocity = recent-window commits vs prior-window commits. Splits byDay (newest-first)
 *  into the last `win` days vs the `win` days before. Returns {recent, prior} sums of
 *  YOUR commits, for the caller to feed deltaGlyph(recent − prior). null prior → the
 *  caller's deltaGlyph maps the "no comparison" honestly. */
export function velocityWindows(byDay: DayView[], win: number): { recent: number; prior: number | null } {
  // byDay is newest-first.
  const recent = byDay.slice(0, win).reduce((s, d) => s + d.totalCommits, 0);
  const priorSlice = byDay.slice(win, win * 2);
  const prior = priorSlice.length > 0 ? priorSlice.reduce((s, d) => s + d.totalCommits, 0) : null;
  return { recent, prior };
}

/** you-vs-other ratio: YOUR commits (byRepo sum) vs TEAM commits (otherRepos sum).
 *  Returns {you, other, youPct}. Honest when other=0 (youPct=100) AND when you=0
 *  (youPct=0) — never a fabricated split. both 0 → youPct null (nothing to show). */
export function youVsOther(byRepo: RepoSummary[], otherRepos: RepoDay[]): { you: number; other: number; youPct: number | null } {
  const you = byRepo.reduce((s, r) => s + r.commits, 0);
  const other = otherRepos.reduce((s, r) => s + r.commits, 0);
  const total = you + other;
  return { you, other, youPct: total > 0 ? (you / total) * 100 : null };
}

/* ---- #123 GitHub-style contribution heatmap (pure, testable) ---- */

/** one heatmap cell. date "YYYY-MM-DD", count = YOUR commits that day, band 0–4
 *  (0 = empty, 1–4 = intensity), inRange=false for the leading pad cells before the
 *  window start (rendered blank so week 1 aligns to its weekday row). */
export interface HeatCell {
  date: string;
  count: number;
  band: 0 | 1 | 2 | 3 | 4;
  inRange: boolean;
}
/** a week column = 7 cells, Mon(row0)→Sun(row6). */
export type HeatWeek = HeatCell[];
/** a month label anchored at a week-column index (for the strip along the top). */
export interface HeatMonthLabel { col: number; label: string }
export interface GithubHeatmap {
  weeks: HeatWeek[];
  monthLabels: HeatMonthLabel[];
  maxCount: number;
  totalCommits: number;
  /** the 5-band thresholds actually used (for the legend), [t1,t2,t3,t4]. */
  thresholds: [number, number, number, number];
}

const MONTHS_VI = ["Th1", "Th2", "Th3", "Th4", "Th5", "Th6", "Th7", "Th8", "Th9", "Th10", "Th11", "Th12"];

/** band a per-day count into 0–4 by quartile-ish thresholds of the max (GitHub-style:
 *  0 empty; then 4 increasing greens). Honest: 0 stays band 0. */
function bandFor(count: number, t: [number, number, number, number]): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0) return 0;
  if (count >= t[3]) return 4;
  if (count >= t[2]) return 3;
  if (count >= t[1]) return 2;
  return 1;
}

/** Build a GitHub-style contribution grid from byDay (newest-first). `weeks` columns,
 *  each Mon→Sun. Anchors the grid to END on the newest byDay date (its week), going
 *  `weeks` columns back. Leading cells before the earliest data day are inRange=false
 *  (blank pad) so the first real week sits on the correct weekday row.
 *  PURE — given the same byDay it returns the same grid (no Date.now); the anchor is the
 *  data's newest date, not "today", so it's deterministic + testable. */
export function buildGithubHeatmap(byDay: DayView[], weeks = 53): GithubHeatmap {
  const counts = new Map<string, number>();
  let maxCount = 0;
  let totalCommits = 0;
  for (const d of byDay) {
    counts.set(d.date, d.totalCommits);
    if (d.totalCommits > maxCount) maxCount = d.totalCommits;
    totalCommits += d.totalCommits;
  }
  // thresholds for the 5 bands (1..4): split the max into quarters (≥1 each, monotone).
  const q = (f: number) => Math.max(1, Math.ceil(maxCount * f));
  const thresholds: [number, number, number, number] = maxCount <= 0
    ? [1, 1, 1, 1]
    : [1, q(0.25), q(0.5), q(0.75)];
  // dedupe identical thresholds upward so bands stay distinct-ish (cheap monotone fix).
  for (let i = 1; i < 4; i++) if (thresholds[i] <= thresholds[i - 1]) thresholds[i] = thresholds[i - 1] + 1;

  // anchor: the newest byDay date (fallback: empty grid).
  const newest = byDay[0]?.date;
  if (!newest) {
    return { weeks: [], monthLabels: [], maxCount: 0, totalCommits: 0, thresholds };
  }
  const end = new Date(newest + "T00:00:00Z");
  // walk back to the Monday of the newest date's week (UTC, Mon=0 convention).
  const endDow = (end.getUTCDay() + 6) % 7; // 0=Mon .. 6=Sun
  // last column's Monday:
  const lastMon = new Date(end);
  lastMon.setUTCDate(end.getUTCDate() - endDow);
  // first column's Monday = lastMon − (weeks-1)*7 days.
  const firstMon = new Date(lastMon);
  firstMon.setUTCDate(lastMon.getUTCDate() - (weeks - 1) * 7);

  const out: HeatWeek[] = [];
  const monthLabels: HeatMonthLabel[] = [];
  let lastLabeledMonth = -1;
  for (let w = 0; w < weeks; w++) {
    const week: HeatWeek = [];
    const colMon = new Date(firstMon);
    colMon.setUTCDate(firstMon.getUTCDate() + w * 7);
    // a month label when this column's Monday begins a new month (and there's room).
    const mo = colMon.getUTCMonth();
    if (mo !== lastLabeledMonth) {
      monthLabels.push({ col: w, label: MONTHS_VI[mo] });
      lastLabeledMonth = mo;
    }
    for (let r = 0; r < 7; r++) {
      const cell = new Date(colMon);
      cell.setUTCDate(colMon.getUTCDate() + r);
      const key = cell.toISOString().slice(0, 10);
      const inRange = cell <= end; // future-of-anchor cells (this week's tail) → out
      const count = counts.get(key) ?? 0;
      week.push({ date: key, count, band: inRange ? bandFor(count, thresholds) : 0, inRange });
    }
    out.push(week);
  }
  return { weeks: out, monthLabels, maxCount, totalCommits, thresholds };
}

/* ---- sortable per-repo table ---- */
export type RepoSortKey = "repo" | "commits" | "locAdded" | "locDeleted" | "activeDays" | "lastActive";
export type SortDir = "asc" | "desc";

/** Sort byRepo rows by a column. Strings (repo/lastActive) lexicographic; numbers
 *  numeric. null lastActive sorts LAST regardless of dir (honest — "never" is not a
 *  small date). Stable. Returns a NEW array (pure). */
export function sortRepos(rows: RepoSummary[], key: RepoSortKey, dir: SortDir): RepoSummary[] {
  const out = [...rows];
  const mul = dir === "asc" ? 1 : -1;
  out.sort((a, b) => {
    if (key === "repo") return mul * a.repo.localeCompare(b.repo);
    if (key === "lastActive") {
      // null ("never active") always sorts last, both dirs
      if (a.lastActive == null && b.lastActive == null) return 0;
      if (a.lastActive == null) return 1;
      if (b.lastActive == null) return -1;
      return mul * a.lastActive.localeCompare(b.lastActive);
    }
    const av = (a[key] as number) ?? 0, bv = (b[key] as number) ?? 0;
    return mul * (av - bv);
  });
  return out;
}
