"use client";
/* ============================================================
   /dev-activity (#63-P3 · DEVACT) — git-contribution view: "what did I code, which
   project, when", derived FROM git. NOT /activity (that's the automation run-log feed).

   No mock (net-new #63 feature) → built from the FROZEN schema + the /tracing heatmap
   pattern (#65 hm-grid/heatColor, a11y-labeled). RENDER-ONLY — the backend computes
   everything (commits/LOC/active-span/summary); the FE displays.

   HONEST-"you": DEV_TRACING_EMAILS unset → summary all-0, byRepo [], everything in
   otherRepos (tagged "other"). The screen shows an empty-state-for-you + the
   "set DEV_TRACING_EMAILS" hint + warnings, and STILL renders otherRepos as team
   context (never blank/crash). LOC is informational (Goodhart) — secondary, NOT the
   headline; commits + active-span + by-repo distribution are the primary signals.
   ============================================================ */
import { useMemo, useState } from "react";
import { useDevActivity } from "@/lib/useDevActivity";
import { apiBase, ApiError } from "@/lib/api";
import { fmtTokens, fmtSign, deltaGlyph } from "@/lib/format";
import {
  netLoc, commitsPerDay, peakHours, peakHour, totalActiveMinutes, fmtMinutes,
  velocityWindows, youVsOther, sortRepos, type RepoSortKey, type SortDir,
} from "@/lib/devStats";
import type { DayView, RepoDay } from "@/lib/types";

const WEEK_DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]; // Mon→Sun
// #97 — analyst range filter (was [30,90,180]). 7/14/30/90 per the user ask.
const RANGES = [7, 14, 30, 90];

/** heatmap cell color by a day's commit COUNT, banded relative to the range max
 *  (0 = empty). Same approach as the /tracing heatmap. */
function heatColor(count: number, max: number): string {
  if (count <= 0) return "var(--bg-3)";
  const a = 0.18 + 0.82 * Math.min(1, count / Math.max(1, max));
  return `color-mix(in oklch, var(--accent) ${Math.round(a * 100)}%, var(--bg-3))`;
}

/** a byDay[] (newest-first) → 84 trailing cells (12w×7), oldest→newest, each = that
 *  day's YOUR commit count (0 when no "you" attribution / no activity). */
function buildHeatmap(byDay: DayView[]): { date: string; count: number }[] {
  const byDate = new Map(byDay.map((d) => [d.date, d.totalCommits]));
  const cells: { date: string; count: number }[] = [];
  // derive the 84-day window ending at the newest byDay date (or today's first entry).
  const newest = byDay[0]?.date;
  if (!newest) return [];
  const end = new Date(newest + "T00:00:00Z");
  for (let i = 83; i >= 0; i--) {
    const dt = new Date(end);
    dt.setUTCDate(end.getUTCDate() - i);
    const key = dt.toISOString().slice(0, 10);
    cells.push({ date: key, count: byDate.get(key) ?? 0 });
  }
  return cells;
}

export default function DevActivityPage() {
  const { data, status, errMsg, days, setDays, reload, scan } = useDevActivity(90);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState("");
  const [scanErr, setScanErr] = useState("");

  const sc = data.summary;
  const hasYou = sc.totalCommits > 0; // honest: "you" attribution present?
  const heatCells = useMemo(() => buildHeatmap(data.byDay), [data.byDay]);
  const heatMax = useMemo(() => Math.max(1, ...heatCells.map((c) => c.count)), [heatCells]);
  // team-context: aggregate otherRepos by repo (commits-desc) for a compact list.
  const otherByRepo = useMemo(() => aggregateByRepo(data.otherRepos), [data.otherRepos]);
  // recent days with ANY activity (you or other) for the per-day bars.
  const recentDays = useMemo(() => data.byDay.slice(0, 14), [data.byDay]);

  /* ---- #97 analyst stats (render-only derivations; honest null when no "you") ---- */
  const cpd = useMemo(() => commitsPerDay(sc.totalCommits, sc.activeDays), [sc.totalCommits, sc.activeDays]);
  const net = useMemo(() => netLoc(sc.locAdded, sc.locDeleted), [sc.locAdded, sc.locDeleted]);
  const activeMin = useMemo(() => totalActiveMinutes(data.byDay), [data.byDay]);
  const hourDist = useMemo(() => peakHours(data.byDay), [data.byDay]);
  const peak = useMemo(() => peakHour(hourDist), [hourDist]);
  // velocity: a window sized to the range (¼ of the days, ≥3), recent vs prior.
  const velWin = Math.max(3, Math.round(days / 4));
  const vel = useMemo(() => velocityWindows(data.byDay, velWin), [data.byDay, velWin]);
  const velGlyph = deltaGlyph(vel.prior == null ? null : vel.recent - vel.prior);
  const yvo = useMemo(() => youVsOther(data.byRepo, data.otherRepos), [data.byRepo, data.otherRepos]);

  // sortable per-repo table state + derived sorted rows.
  const [sortKey, setSortKey] = useState<RepoSortKey>("commits");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const sortedRepos = useMemo(() => sortRepos(data.byRepo, sortKey, sortDir), [data.byRepo, sortKey, sortDir]);
  function toggleSort(key: RepoSortKey) {
    if (key === sortKey) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir(key === "repo" || key === "lastActive" ? "asc" : "desc"); }
  }

  async function onScan() {
    setScanErr(""); setScanMsg("");
    setScanning(true);
    try {
      const res = await scan();
      setScanMsg(`Quét ${res.scannedRepos} repo · ${res.rowsUpserted} dòng · ${res.yourCommits} commit của bạn`);
    } catch (err) {
      setScanErr(err instanceof ApiError ? (err.hint ? `${err.message} (${err.hint})` : err.message) : (err as Error).message);
    } finally {
      setScanning(false);
    }
  }

  return (
    <section className="view" data-screen="DEVACT" data-testid="dev-activity-screen">
      <div className="vtitle">
        <h1>Dev Activity</h1>
        <span className="sub">git · bạn đã code gì, dự án nào, khi nào · {data.scannedRepos} repo quét</span>
        <span className="sp" />
        <div className="seg" data-testid="dev-range">
          {RANGES.map((d) => (
            <button key={d} type="button" className={days === d ? "on" : ""} onClick={() => setDays(d)} data-testid={`range-${d}`}>{d}n</button>
          ))}
        </div>
        <button className="btn" type="button" onClick={onScan} disabled={scanning} data-testid="dev-scan">{scanning ? "Đang quét…" : "Quét lại"}</button>
      </div>

      {scanMsg && <div className="hint pos" data-testid="scan-ok">{scanMsg}</div>}
      {scanErr && <div className="hint neg" data-testid="scan-error">⚠ {scanErr}</div>}

      {/* warnings from the API (honest — e.g. DEV_TRACING_EMAILS not set) */}
      {data.warnings.length > 0 && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="dev-warnings">
          {data.warnings.map((w, i) => <div className="hint mid" key={i} data-testid={`warn-${i}`}>⚠ {w}</div>)}
        </div>
      )}

      {/* #71-lesson: GET /dev_activity scans git repos → can take ~20s+ COLD (warm ~0.2s).
          A skeleton (not a blank "loading" line) so the layout appears immediately + a
          hint that the scan is running, so the long cold scan doesn't read as a hang. */}
      {status === "loading" && (
        <div data-testid="dev-loading" aria-busy="true">
          <div className="hint faint" style={{ padding: "4px 4px 10px" }}>Đang quét git (lần đầu có thể mất ~20s)…</div>
          <div className="grid g-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div className="card macro-skeleton" key={i} style={{ padding: "14px 16px", minHeight: 84 }} aria-hidden="true">
                <div className="sk-line" style={{ width: "55%" }} />
                <div className="sk-line" style={{ width: "35%", height: 20, marginTop: 10 }} />
              </div>
            ))}
          </div>
          <div className="panel" style={{ marginTop: 14, padding: "14px 16px" }} aria-hidden="true">
            <div className="sk-line" style={{ width: "30%" }} />
            <div className="sk-line" style={{ width: "100%", height: 80, marginTop: 12 }} />
          </div>
        </div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="dev-error">
          Không tải được dev activity: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <>
          {/* KPI strip — YOUR activity (commits primary; LOC secondary/informational) */}
          <div className="grid g-4" data-testid="dev-summary">
            <div className="stat">
              <span className="sl">Commit của bạn</span>
              <span className="sv acc">{sc.totalCommits}</span>
              <span className="sd faint">{sc.activeDays} ngày · {sc.activeRepos} repo</span>
            </div>
            <div className="stat">
              <span className="sl">Ngày active</span>
              <span className="sv">{sc.activeDays}</span>
              <span className="sd faint">trong {data.rangeDays} ngày</span>
            </div>
            <div className="stat">
              <span className="sl">Repo của bạn</span>
              <span className="sv">{sc.activeRepos}</span>
              <span className="sd faint">{data.scannedRepos} repo đã quét</span>
            </div>
            {/* LOC secondary — labeled informational, NOT a score (Goodhart) */}
            <div className="stat">
              <span className="sl">LOC (tham khảo)</span>
              <span className="sv faint" style={{ fontSize: 18 }} data-testid="dev-loc">
                <span className="pos">+{fmtTokens(sc.locAdded)}</span> / <span className="neg">−{fmtTokens(sc.locDeleted)}</span>
              </span>
              <span className="sd faint">chỉ tham khảo — không phải thước đo</span>
            </div>
          </div>

          {/* #97 analyst-stats row — derived from existing data, honest null when no "you" */}
          {hasYou && (
            <div className="panel" data-testid="dev-analyst" style={{ padding: "12px 16px" }}>
              <div className="phead"><span className="kicker">Phân tích · {days} ngày</span></div>
              <div className="grid g-4" style={{ marginTop: 8 }}>
                <div className="stat">
                  <span className="sl">Commit / ngày active</span>
                  <span className="sv acc" data-testid="stat-cpd">{cpd != null ? cpd.toFixed(1) : "—"}</span>
                  <span className="sd faint">{sc.totalCommits} commit · {sc.activeDays} ngày</span>
                </div>
                <div className="stat">
                  <span className="sl">Net LOC</span>
                  <span className={`sv ${net == null ? "faint" : net < 0 ? "neg" : "pos"}`} data-testid="stat-netloc">
                    {net == null ? "—" : `${net >= 0 ? "+" : "−"}${fmtTokens(Math.abs(net))}`}
                  </span>
                  <span className="sd faint">+{fmtTokens(sc.locAdded)} / −{fmtTokens(sc.locDeleted)}</span>
                </div>
                <div className="stat">
                  <span className="sl">Active span</span>
                  <span className="sv" data-testid="stat-span">{fmtMinutes(activeMin)}</span>
                  <span className="sd faint">tổng first→last mỗi ngày</span>
                </div>
                <div className="stat">
                  <span className="sl">Giờ hay code</span>
                  {/* HONEST — surface the real start-hour (incl a night-owl 0h), not smoothed */}
                  <span className="sv" data-testid="stat-peak">{peak != null ? `${String(peak).padStart(2, "0")}:00` : "—"}</span>
                  <span className="sd faint">{peak != null ? `${hourDist[peak]} lần bắt đầu giờ này` : "chưa có dữ liệu giờ"}</span>
                </div>
              </div>

              {/* velocity-trend (3-way honest deltaGlyph) + you-vs-other ratio */}
              <div style={{ display: "flex", gap: 20, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                <div data-testid="dev-velocity">
                  <span className="sl">Velocity ({velWin}n gần / {velWin}n trước)</span>{" "}
                  <span className={`num ${velGlyph.cls}`} data-testid="vel-glyph">{velGlyph.arrow}</span>{" "}
                  <span className="num faint" data-testid="vel-nums">
                    {vel.recent}{vel.prior != null ? ` vs ${vel.prior}` : " (chưa đủ lịch sử so sánh)"}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 220 }} data-testid="dev-yvo">
                  <span className="sl">Bạn vs team</span>
                  {yvo.youPct == null ? (
                    <span className="hint faint" data-testid="yvo-empty"> — chưa có commit</span>
                  ) : (
                    <div className="barc" style={{ marginTop: 4, height: 9, position: "relative" }} title={`Bạn ${yvo.you} · team ${yvo.other}`}>
                      <i style={{ width: `${yvo.youPct}%`, background: "var(--accent)" }} data-testid="yvo-bar" />
                      <span className="num faint" style={{ marginLeft: 8, fontSize: 11 }} data-testid="yvo-label">
                        {yvo.youPct.toFixed(0)}% bạn ({yvo.you}) · {yvo.other} team
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* honest empty-state for "you" (no attribution) — STILL show team context below */}
          {!hasYou && (
            <div className="panel" data-testid="dev-empty-you">
              <div style={{ padding: "22px 18px", textAlign: "center" }}>
                <div className="hint" style={{ fontSize: 13 }}>Chưa có commit nào được gán cho bạn.</div>
                <div className="hint faint" style={{ marginTop: 6, lineHeight: 1.5 }}>
                  Đặt biến môi trường <span className="num acc">DEV_TRACING_EMAILS</span> = email git của bạn để quy commit về "bạn".
                  Hiện tất cả commit đang ở mục <b>Team context</b> bên dưới.
                </div>
              </div>
            </div>
          )}

          {/* contribution heatmap — YOUR commits by VN-day (honest-empty when no "you") */}
          <div className="panel" style={{ overflow: "hidden" }} data-testid="dev-heatmap-panel">
            <div className="phead">
              <span className="kicker">Contribution heatmap · commit của bạn theo ngày</span>
              <span className="hint" style={{ marginLeft: "auto" }}>{heatCells.length ? "12 tuần qua" : "—"}</span>
            </div>
            <div style={{ padding: "12px 16px 16px" }}>
              {heatCells.length === 0 ? (
                <span className="hint faint" data-testid="dev-heatmap-empty">Chưa có dữ liệu ngày.</span>
              ) : (
                <div className="heatmap-wrap">
                  <div className="hm-days">{WEEK_DAYS.map((d) => <div className="hm-day" key={d}>{d}</div>)}</div>
                  <div className="hm-grid" data-testid="dev-heatmap-grid" role="img" aria-label="Heatmap commit của bạn — 12 tuần qua">
                    {heatCells.map((c, i) => (
                      <div className="hc" key={i} style={{ background: heatColor(c.count, heatMax) }} title={`${c.date}: ${c.count} commit`} aria-label={`${c.date}: ${c.count} commit`} data-testid={`dev-hc-${i}`} data-count={c.count} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* by-repo — YOUR repos as a SORTABLE table (#97), the PRIMARY signal */}
          <div className="panel" data-testid="dev-byrepo">
            <div className="phead"><span className="kicker">Repo của bạn · bấm cột để sắp xếp</span><span className="hint" style={{ marginLeft: "auto" }}>{data.byRepo.length} repo</span></div>
            <div style={{ padding: "10px 16px 14px" }}>
              {data.byRepo.length === 0 ? (
                <span className="hint faint" data-testid="dev-byrepo-empty">Chưa có repo nào của bạn (xem Team context bên dưới).</span>
              ) : (
                <table className="dev-repo-table" data-testid="dev-repo-table">
                  <thead>
                    <tr>
                      {([
                        ["repo", "Repo"], ["commits", "Commit"], ["locAdded", "+LOC"],
                        ["locDeleted", "−LOC"], ["activeDays", "Ngày"], ["lastActive", "Gần nhất"],
                      ] as [RepoSortKey, string][]).map(([key, label]) => (
                        <th
                          key={key}
                          onClick={() => toggleSort(key)}
                          data-testid={`sort-${key}`}
                          aria-sort={sortKey === key ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                          className={`dev-th ${key === "repo" ? "" : "num-col"} ${sortKey === key ? "sorted" : ""}`}
                        >
                          {label}{sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRepos.map((r) => (
                      <tr key={r.repo} data-testid={`repo-row-${r.repo}`}>
                        <td className="dev-repo-name">{r.repo}</td>
                        <td className="num-col" data-testid={`repo-commits-${r.repo}`}>{r.commits}</td>
                        <td className="num-col pos">+{fmtTokens(r.locAdded)}</td>
                        <td className="num-col neg">−{fmtTokens(r.locDeleted)}</td>
                        <td className="num-col">{r.activeDays}</td>
                        <td className="num-col faint">{r.lastActive ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          {/* recent-day commit bars (you) — velocity-ish over recent days */}
          {hasYou && recentDays.some((d) => d.totalCommits > 0) && (
            <div className="panel" data-testid="dev-recent">
              <div className="phead"><span className="kicker">Commit gần đây · theo ngày</span></div>
              <div style={{ padding: "12px 16px", display: "flex", alignItems: "flex-end", gap: 4, height: 90 }}>
                {[...recentDays].reverse().map((d) => {
                  const max = Math.max(1, ...recentDays.map((x) => x.totalCommits));
                  const h = Math.max(3, Math.round((d.totalCommits / max) * 100));
                  return (
                    <div key={d.date} title={`${d.date}: ${d.totalCommits} commit`} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center", gap: 4 }} data-testid={`dev-day-${d.date}`}>
                      <div style={{ width: "100%", height: `${h}%`, background: d.totalCommits > 0 ? "var(--accent)" : "var(--bg-3)", borderRadius: 2 }} />
                      <span className="faint" style={{ fontSize: 8.5, fontFamily: "var(--mono)" }}>{d.date.slice(8)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TEAM CONTEXT — otherRepos (tagged "other", NOT in your totals) */}
          <div className="panel" data-testid="dev-team-context">
            <div className="phead">
              <span className="kicker">Team context · không tính vào của bạn</span>
              <span className="tagchip" style={{ marginLeft: 8 }}>other</span>
              <span className="hint" style={{ marginLeft: "auto" }}>{otherByRepo.length} repo</span>
            </div>
            <div style={{ padding: "10px 16px 14px" }}>
              {otherByRepo.length === 0 ? (
                <span className="hint faint" data-testid="dev-team-empty">Không có hoạt động team nào.</span>
              ) : (
                otherByRepo.map((r) => (
                  <div key={r.repo} className="mrow" style={{ alignItems: "center", gap: 10, padding: "6px 0" }} data-testid={`other-${r.repo}`}>
                    <span className="k" style={{ minWidth: 150 }}>{r.repo}</span>
                    <span className="barc" style={{ flex: 1, width: "auto" }}>
                      <i style={{ width: `${Math.max(2, Math.min(100, Math.round((r.commits / Math.max(1, ...otherByRepo.map((x) => x.commits))) * 100)))}%`, background: "var(--tx-2)" }} />
                    </span>
                    <span className="num" style={{ width: 70, textAlign: "right" }}>{r.commits} commit</span>
                    <span className="faint num" style={{ width: 110, textAlign: "right", fontSize: 10.5 }}>+{fmtTokens(r.locAdded)}/−{fmtTokens(r.locDeleted)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

/** aggregate otherRepos (RepoDay[]) → per-repo totals, commits-desc (render-only roll-up). */
function aggregateByRepo(rows: RepoDay[]): { repo: string; commits: number; locAdded: number; locDeleted: number }[] {
  const map = new Map<string, { repo: string; commits: number; locAdded: number; locDeleted: number }>();
  for (const row of rows) {
    const e = map.get(row.repo) ?? { repo: row.repo, commits: 0, locAdded: 0, locDeleted: 0 };
    e.commits += row.commits;
    e.locAdded += row.locAdded;
    e.locDeleted += row.locDeleted;
    map.set(row.repo, e);
  }
  return Array.from(map.values()).sort((a, b) => b.commits - a.commits);
}
