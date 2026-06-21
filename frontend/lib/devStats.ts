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
