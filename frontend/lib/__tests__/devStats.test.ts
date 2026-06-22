import { describe, it, expect } from "vitest";
import {
  netLoc, commitsPerDay, peakHours, peakHour, totalActiveMinutes, fmtMinutes,
  velocityWindows, youVsOther, sortRepos, buildGithubHeatmap,
} from "../devStats";
import type { DayView, RepoDay, RepoSummary } from "../types";

/* #97 — the analyst-stats derivations (pure). The dispatch's core verification:
   net-LOC · commit-per-day · active-span · peak-hours dist · velocity windows ·
   you-vs-other (honest when other=0) · sortable table. honest-mirror: no-attribution
   → null/empty, NEVER a fabricated stat. */

const RD = (over: Partial<RepoDay> = {}): RepoDay => ({
  date: "2026-06-21", repo: "r", source: "you", commits: 1, locAdded: 0, locDeleted: 0,
  firstTs: null, lastTs: null, activeSpan: "", ...over,
});
const DAY = (over: Partial<DayView> = {}): DayView => ({
  date: "2026-06-21", repos: [], totalCommits: 0, activeRepos: 0, ...over,
});
const RS = (over: Partial<RepoSummary> = {}): RepoSummary => ({
  repo: "r", commits: 0, locAdded: 0, locDeleted: 0, activeDays: 0, lastActive: null, ...over,
});

describe("devStats — net-LOC + commit-per-day", () => {
  it("netLoc = added − deleted; both null → null (honest no-data)", () => {
    expect(netLoc(100, 30)).toBe(70);
    expect(netLoc(0, 50)).toBe(-50);
    expect(netLoc(null, null)).toBeNull();
    expect(netLoc(100, null)).toBe(100); // partial → treat missing as 0
  });
  it("commitsPerDay = total/activeDays; 0 active days → null (NOT a fake 0 / div0)", () => {
    expect(commitsPerDay(60, 20)).toBe(3);
    expect(commitsPerDay(703, 23)).toBeCloseTo(30.57, 1);
    expect(commitsPerDay(0, 0)).toBeNull(); // no attribution
    expect(commitsPerDay(5, 0)).toBeNull();
  });
});

describe("devStats — peak-hours (HONEST, real pattern not smoothed)", () => {
  const byDay: DayView[] = [
    DAY({ repos: [RD({ source: "you", firstTs: "00:10" }), RD({ source: "you", firstTs: "00:40" }), RD({ source: "other", firstTs: "09:00" })] }),
    DAY({ repos: [RD({ source: "you", firstTs: "11:00" }), RD({ source: "you", firstTs: "03:00" })] }),
  ];
  it("peakHours dist counts only YOUR start-hours (the real distribution)", () => {
    const d = peakHours(byDay);
    expect(d[0]).toBe(2);  // two 00:xx
    expect(d[11]).toBe(1);
    expect(d[3]).toBe(1);
    expect(d[9]).toBeUndefined(); // "other" excluded
  });
  it("peakHour = the mode; ties → earlier hour; empty → null (no fabrication)", () => {
    expect(peakHour(peakHours(byDay))).toBe(0); // 0:00 is the night-owl peak — surfaced honestly
    expect(peakHour({})).toBeNull();
    expect(peakHour({ 3: 2, 9: 2 })).toBe(3); // tie → earlier
  });
});

describe("devStats — active-span (firstTs→lastTs)", () => {
  it("totalActiveMinutes sums per-day YOUR first→last spans", () => {
    const byDay: DayView[] = [
      DAY({ repos: [RD({ source: "you", firstTs: "09:00", lastTs: "11:30" })] }), // 150m
      DAY({ repos: [RD({ source: "you", firstTs: "14:00", lastTs: "14:09" }), RD({ source: "you", firstTs: "20:00", lastTs: "22:00" })] }), // 14:00→22:00 = 480m
    ];
    expect(totalActiveMinutes(byDay)).toBe(150 + 480);
  });
  it("no YOUR data → null (honest), not 0", () => {
    expect(totalActiveMinutes([DAY({ repos: [RD({ source: "other", firstTs: "09:00", lastTs: "10:00" })] })])).toBeNull();
    expect(totalActiveMinutes([])).toBeNull();
  });
  it("fmtMinutes → 'Hh Mm' / 'Mm' / '—'", () => {
    expect(fmtMinutes(630)).toBe("10h 30m");
    expect(fmtMinutes(45)).toBe("45m");
    expect(fmtMinutes(null)).toBe("—");
  });
});

describe("devStats — velocity windows (feeds deltaGlyph)", () => {
  // 4 days newest-first: [5,3,2,1]
  const byDay: DayView[] = [
    DAY({ totalCommits: 5 }), DAY({ totalCommits: 3 }), DAY({ totalCommits: 2 }), DAY({ totalCommits: 1 }),
  ];
  it("recent vs prior window sums (win=2): recent=5+3=8, prior=2+1=3", () => {
    expect(velocityWindows(byDay, 2)).toEqual({ recent: 8, prior: 3 });
  });
  it("no prior window → prior null (deltaGlyph maps no-comparison honestly)", () => {
    expect(velocityWindows(byDay.slice(0, 2), 2)).toEqual({ recent: 8, prior: null });
  });
});

describe("devStats — you-vs-other (HONEST when other=0)", () => {
  it("normal split → youPct", () => {
    const r = youVsOther([RS({ commits: 75 })], [RD({ source: "other", commits: 25 })]);
    expect(r).toEqual({ you: 75, other: 25, youPct: 75 });
  });
  it("other=0 → youPct 100 (honest, post-#84/#85 double-count fix)", () => {
    expect(youVsOther([RS({ commits: 40 })], [])).toEqual({ you: 40, other: 0, youPct: 100 });
  });
  it("you=0 → youPct 0 (honest, not hidden)", () => {
    expect(youVsOther([], [RD({ source: "other", commits: 30 })])).toEqual({ you: 0, other: 30, youPct: 0 });
  });
  it("both 0 → youPct null (nothing to show, not a fake 0/100)", () => {
    expect(youVsOther([], [])).toEqual({ you: 0, other: 0, youPct: null });
  });
});

describe("devStats — sortable per-repo table", () => {
  const rows: RepoSummary[] = [
    RS({ repo: "beta", commits: 10, locAdded: 100, activeDays: 3, lastActive: "2026-06-01" }),
    RS({ repo: "alpha", commits: 50, locAdded: 20, activeDays: 9, lastActive: "2026-06-10" }),
    RS({ repo: "gamma", commits: 30, locAdded: 200, activeDays: 1, lastActive: null }),
  ];
  it("sort by commits desc", () => {
    expect(sortRepos(rows, "commits", "desc").map((r) => r.repo)).toEqual(["alpha", "gamma", "beta"]);
  });
  it("sort by commits asc", () => {
    expect(sortRepos(rows, "commits", "asc").map((r) => r.repo)).toEqual(["beta", "gamma", "alpha"]);
  });
  it("sort by repo name asc (lexicographic)", () => {
    expect(sortRepos(rows, "repo", "asc").map((r) => r.repo)).toEqual(["alpha", "beta", "gamma"]);
  });
  it("sort by lastActive — null ('never') sorts LAST both directions (honest)", () => {
    expect(sortRepos(rows, "lastActive", "desc").map((r) => r.repo)).toEqual(["alpha", "beta", "gamma"]); // gamma(null) last
    expect(sortRepos(rows, "lastActive", "asc").map((r) => r.repo)).toEqual(["beta", "alpha", "gamma"]); // gamma(null) STILL last
  });
  it("is pure (does not mutate input)", () => {
    const orig = rows.map((r) => r.repo);
    sortRepos(rows, "commits", "desc");
    expect(rows.map((r) => r.repo)).toEqual(orig);
  });
});

/* ---- #123 GitHub-style contribution heatmap (pure, deterministic on the data anchor) ---- */
describe("devStats — buildGithubHeatmap (GitHub-style contribution grid)", () => {
  // a small, deterministic byDay (newest-first). 2026-06-22 is a Monday.
  const BYDAY: DayView[] = [
    DAY({ date: "2026-06-22", totalCommits: 29 }), // Mon
    DAY({ date: "2026-06-21", totalCommits: 4 }),  // Sun
    DAY({ date: "2026-06-20", totalCommits: 0 }),  // Sat
    DAY({ date: "2026-06-19", totalCommits: 12 }), // Fri
    DAY({ date: "2026-06-15", totalCommits: 8 }),  // prev Mon
  ];

  it("returns N week-columns, each 7 cells Mon→Sun", () => {
    const hm = buildGithubHeatmap(BYDAY, 4);
    expect(hm.weeks).toHaveLength(4);
    for (const wk of hm.weeks) expect(wk).toHaveLength(7);
  });

  it("places each day's count on the correct (week-col, weekday-row) cell", () => {
    const hm = buildGithubHeatmap(BYDAY, 4);
    // flatten + index by date
    const byDate = new Map(hm.weeks.flat().map((c) => [c.date, c]));
    expect(byDate.get("2026-06-22")?.count).toBe(29); // Mon → row 0
    expect(byDate.get("2026-06-21")?.count).toBe(4);  // Sun → row 6
    expect(byDate.get("2026-06-19")?.count).toBe(12); // Fri → row 4
    // a day with no entry → count 0 (honest, not fabricated)
    expect(byDate.get("2026-06-18")?.count).toBe(0);
  });

  it("the last column is the newest date's week; Monday is row 0, Sunday row 6", () => {
    const hm = buildGithubHeatmap(BYDAY, 4);
    const lastCol = hm.weeks[hm.weeks.length - 1];
    expect(lastCol[0].date).toBe("2026-06-22"); // Mon row0
    expect(lastCol[6].date).toBe("2026-06-28"); // Sun row6 (this week's tail)
  });

  it("bands a count into 0–4 (0 = empty, max → band 4)", () => {
    const hm = buildGithubHeatmap(BYDAY, 4);
    const byDate = new Map(hm.weeks.flat().map((c) => [c.date, c]));
    expect(byDate.get("2026-06-20")?.band).toBe(0); // 0 commits → empty band
    expect(byDate.get("2026-06-22")?.band).toBe(4); // 29 = max → top band
    expect(byDate.get("2026-06-21")?.band).toBeGreaterThan(0); // 4 commits → some green
  });

  it("future-of-anchor cells (this week's tail) are inRange=false (blank pad)", () => {
    const hm = buildGithubHeatmap(BYDAY, 4);
    const byDate = new Map(hm.weeks.flat().map((c) => [c.date, c]));
    // anchor = 2026-06-22 (Mon); 06-23..06-28 are after it → out of range
    expect(byDate.get("2026-06-23")?.inRange).toBe(false);
    expect(byDate.get("2026-06-28")?.inRange).toBe(false);
    expect(byDate.get("2026-06-22")?.inRange).toBe(true);
  });

  it("emits month labels (one per month boundary, anchored at a week-col)", () => {
    const hm = buildGithubHeatmap(BYDAY, 53);
    expect(hm.monthLabels.length).toBeGreaterThan(0);
    // each label points at a valid column index + a Th* label
    for (const ml of hm.monthLabels) {
      expect(ml.col).toBeGreaterThanOrEqual(0);
      expect(ml.col).toBeLessThan(hm.weeks.length);
      expect(ml.label).toMatch(/^Th\d{1,2}$/);
    }
  });

  it("totalCommits + maxCount reflect the YOUR-commit data (render-only)", () => {
    const hm = buildGithubHeatmap(BYDAY, 53);
    expect(hm.maxCount).toBe(29);
    expect(hm.totalCommits).toBe(29 + 4 + 0 + 12 + 8);
  });

  it("empty byDay → empty grid (honest, no crash, no fabricated cells)", () => {
    const hm = buildGithubHeatmap([], 53);
    expect(hm.weeks).toEqual([]);
    expect(hm.monthLabels).toEqual([]);
    expect(hm.totalCommits).toBe(0);
    expect(hm.maxCount).toBe(0);
  });

  it("thresholds are monotonically increasing (distinct bands)", () => {
    const hm = buildGithubHeatmap(BYDAY, 4);
    const [t1, t2, t3, t4] = hm.thresholds;
    expect(t1).toBeLessThanOrEqual(t2);
    expect(t2).toBeLessThanOrEqual(t3);
    expect(t3).toBeLessThanOrEqual(t4);
  });
});
