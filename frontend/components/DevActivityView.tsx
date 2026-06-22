"use client";
/* ============================================================
   DevActivityView (#120 · #63-P3 · #97 · #123 DEVACT) — the git-contribution body,
   rendered in the /projects "Dev Activity" sub-tab.

   #123 user-CHỐT redesign: YOU-ONLY (drop the you-vs-team comparison + the team-context
   render — only YOUR byRepo + your totals), default sort = lastActive-desc (most-recent
   repo first), a real GitHub-style contribution heatmap (week-cols × T2→CN, 5 green
   bands, month labels, per-cell tooltip, legend, ~1yr via days=365). KEPT: KPI strip,
   the #97 analyst row (YOUR cpd / net-LOC / span / peak-hour / velocity), the sortable
   by-repo table, the scan trigger.

   git-contribution view: "what did I code, which project, when", derived FROM git.
   NOT /activity (the automation run-log feed). RENDER-ONLY — the backend computes
   everything; the FE displays. HONEST-"you": DEV_TRACING_EMAILS unset → summary all-0,
   byRepo [] → an empty-state-for-you + the "set DEV_TRACING_EMAILS" hint + warnings
   (never blank/crash). LOC is informational (Goodhart) — secondary, NOT the headline.
   ============================================================ */
import { useMemo, useState } from "react";
import { useDevActivity } from "@/lib/useDevActivity";
import { apiBase, ApiError } from "@/lib/api";
import { fmtTokens, deltaGlyph } from "@/lib/format";
import {
  netLoc, commitsPerDay, peakHours, peakHour, totalActiveMinutes, fmtMinutes,
  velocityWindows, sortRepos, buildGithubHeatmap, type RepoSortKey, type SortDir,
} from "@/lib/devStats";

const WEEK_DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]; // Mon→Sun (rows)
// #123 — range filter; default 365 (the GitHub-style ~1yr heatmap). Smaller ranges
// still re-scope the KPIs/analyst/table (the heatmap simply shows fewer filled weeks).
const RANGES = [30, 90, 180, 365];

/** GitHub-style 5-band green for a cell (band 0–4). band 0 = the empty cell color. */
function bandColor(band: 0 | 1 | 2 | 3 | 4): string {
  if (band <= 0) return "var(--bg-3)";
  // 4 increasing greens (GitHub-like) built off the data --green token.
  const a = [0, 0.30, 0.52, 0.74, 1][band];
  return `color-mix(in oklch, var(--green) ${Math.round(a * 100)}%, var(--bg-3))`;
}

export function DevActivityView() {
  const { data, status, errMsg, days, setDays, reload, scan } = useDevActivity(365);
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState("");
  const [scanErr, setScanErr] = useState("");

  const sc = data.summary;
  const hasYou = sc.totalCommits > 0; // honest: "you" attribution present?

  // #123 — GitHub-style contribution grid from YOUR per-day commits (byDay.totalCommits).
  const heat = useMemo(() => buildGithubHeatmap(data.byDay, 53), [data.byDay]);

  /* ---- #97 analyst stats (YOUR — render-only; honest null when no "you") ---- */
  const cpd = useMemo(() => commitsPerDay(sc.totalCommits, sc.activeDays), [sc.totalCommits, sc.activeDays]);
  const net = useMemo(() => netLoc(sc.locAdded, sc.locDeleted), [sc.locAdded, sc.locDeleted]);
  const activeMin = useMemo(() => totalActiveMinutes(data.byDay), [data.byDay]);
  const hourDist = useMemo(() => peakHours(data.byDay), [data.byDay]);
  const peak = useMemo(() => peakHour(hourDist), [hourDist]);
  const velWin = Math.max(3, Math.round(days / 4));
  const vel = useMemo(() => velocityWindows(data.byDay, velWin), [data.byDay, velWin]);
  const velGlyph = deltaGlyph(vel.prior == null ? null : vel.recent - vel.prior);

  // #123 — sortable per-repo table; DEFAULT = lastActive-desc (most-recently-worked first).
  const [sortKey, setSortKey] = useState<RepoSortKey>("lastActive");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const sortedRepos = useMemo(() => sortRepos(data.byRepo, sortKey, sortDir), [data.byRepo, sortKey, sortDir]);
  function toggleSort(key: RepoSortKey) {
    if (key === sortKey) setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    else { setSortKey(key); setSortDir(key === "repo" ? "asc" : "desc"); }
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
        <span className="sub">git · commit của bạn theo dự án &amp; thời gian · {data.scannedRepos} repo quét</span>
        <span className="sp" />
        <div className="seg" data-testid="dev-range">
          {RANGES.map((d) => (
            <button key={d} type="button" className={days === d ? "on" : ""} onClick={() => setDays(d)} data-testid={`range-${d}`}>
              {d === 365 ? "1 năm" : `${d}n`}
            </button>
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
          A skeleton (not a blank "loading" line) so the layout appears immediately. */}
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
            <div className="stat">
              <span className="sl">LOC (tham khảo)</span>
              <span className="sv faint" style={{ fontSize: 18 }} data-testid="dev-loc">
                <span className="pos">+{fmtTokens(sc.locAdded)}</span> / <span className="neg">−{fmtTokens(sc.locDeleted)}</span>
              </span>
              <span className="sd faint">chỉ tham khảo — không phải thước đo</span>
            </div>
          </div>

          {/* #123 — GitHub-style contribution heatmap (YOUR commits, ~1 year).
              NO overflow:hidden on the panel — the wide grid would clip the panel to a
              sliver (the grid-blowout collapse); the inner div owns overflowX:auto. */}
          <div className="panel" data-testid="dev-heatmap-panel">
            <div className="phead">
              <span className="kicker">{heat.totalCommits} commit của bạn · 1 năm qua</span>
              <span className="hint" style={{ marginLeft: "auto" }}>mỗi ô = 1 ngày</span>
            </div>
            <div style={{ padding: "12px 16px 14px", overflowX: "auto" }}>
              {heat.weeks.length === 0 ? (
                <span className="hint faint" data-testid="dev-heatmap-empty">Chưa có dữ liệu ngày.</span>
              ) : (
                <div className="gh-heatmap" data-testid="gh-heatmap">
                  {/* month labels along the top, anchored to week columns */}
                  <div className="gh-months" data-testid="gh-months" aria-hidden="true"
                    style={{ display: "grid", gridTemplateColumns: `28px repeat(${heat.weeks.length}, 13px)`, gap: 3, marginBottom: 4 }}>
                    <span />
                    {heat.weeks.map((_, col) => {
                      const ml = heat.monthLabels.find((m) => m.col === col);
                      return <span key={col} className="gh-mlabel faint" style={{ fontSize: 9.5, fontFamily: "var(--mono)", whiteSpace: "nowrap" }}>{ml ? ml.label : ""}</span>;
                    })}
                  </div>
                  {/* the grid: a weekday-label gutter + week columns */}
                  <div style={{ display: "flex", gap: 3 }}>
                    {/* weekday gutter (Mon→Sun; show alt rows like GitHub) */}
                    <div className="gh-days" style={{ display: "grid", gridTemplateRows: "repeat(7, 13px)", gap: 3, width: 25 }}>
                      {WEEK_DAYS.map((d, r) => (
                        <span key={d} className="faint" style={{ fontSize: 9, lineHeight: "13px", fontFamily: "var(--mono)", visibility: r % 2 === 1 ? "visible" : "hidden" }}>{d}</span>
                      ))}
                    </div>
                    <div className="gh-grid" data-testid="gh-grid" role="img" aria-label={`Contribution heatmap — ${heat.totalCommits} commit của bạn trong 1 năm qua`}
                      style={{ display: "grid", gridTemplateColumns: `repeat(${heat.weeks.length}, 13px)`, gap: 3 }}>
                      {heat.weeks.map((week, col) => (
                        <div key={col} style={{ display: "grid", gridTemplateRows: "repeat(7, 13px)", gap: 3 }}>
                          {week.map((cell, r) => (
                            <div
                              key={r}
                              className="gh-cell"
                              data-testid={`gh-cell-${cell.date}`}
                              data-count={cell.count}
                              data-band={cell.band}
                              title={cell.inRange ? `${cell.date}: ${cell.count} commit` : ""}
                              aria-label={cell.inRange ? `${cell.date}: ${cell.count} commit` : undefined}
                              style={{
                                width: 13, height: 13, borderRadius: 3,
                                background: cell.inRange ? bandColor(cell.band) : "transparent",
                                outline: cell.inRange ? "1px solid color-mix(in oklch, var(--line) 40%, transparent)" : "none",
                                outlineOffset: -1,
                              }}
                            />
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                  {/* legend — less → more */}
                  <div className="gh-legend" data-testid="gh-legend" style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 10, justifyContent: "flex-end" }}>
                    <span className="faint" style={{ fontSize: 9.5, fontFamily: "var(--mono)" }}>Ít</span>
                    {[0, 1, 2, 3, 4].map((b) => (
                      <div key={b} style={{ width: 13, height: 13, borderRadius: 3, background: bandColor(b as 0 | 1 | 2 | 3 | 4), outline: "1px solid color-mix(in oklch, var(--line) 40%, transparent)", outlineOffset: -1 }} />
                    ))}
                    <span className="faint" style={{ fontSize: 9.5, fontFamily: "var(--mono)" }}>Nhiều</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* #97 analyst-stats row — YOUR derived numbers, honest null when no "you" */}
          {hasYou && (
            <div className="panel" data-testid="dev-analyst" style={{ padding: "12px 16px" }}>
              <div className="phead"><span className="kicker">Phân tích · {days === 365 ? "1 năm" : `${days} ngày`}</span></div>
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
                  <span className="sv" data-testid="stat-peak">{peak != null ? `${String(peak).padStart(2, "0")}:00` : "—"}</span>
                  <span className="sd faint">{peak != null ? `${hourDist[peak]} lần bắt đầu giờ này` : "chưa có dữ liệu giờ"}</span>
                </div>
              </div>

              {/* velocity-trend (3-way honest deltaGlyph) — YOUR recent vs prior window */}
              <div style={{ display: "flex", gap: 20, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
                <div data-testid="dev-velocity">
                  <span className="sl">Velocity ({velWin}n gần / {velWin}n trước)</span>{" "}
                  <span className={`num ${velGlyph.cls}`} data-testid="vel-glyph">{velGlyph.arrow}</span>{" "}
                  <span className="num faint" data-testid="vel-nums">
                    {vel.recent}{vel.prior != null ? ` vs ${vel.prior}` : " (chưa đủ lịch sử so sánh)"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* honest empty-state for "you" (no attribution) */}
          {!hasYou && (
            <div className="panel" data-testid="dev-empty-you">
              <div style={{ padding: "22px 18px", textAlign: "center" }}>
                <div className="hint" style={{ fontSize: 13 }}>Chưa có commit nào được gán cho bạn.</div>
                <div className="hint faint" style={{ marginTop: 6, lineHeight: 1.5 }}>
                  Đặt biến môi trường <span className="num acc">DEV_TRACING_EMAILS</span> = email git của bạn để quy commit về "bạn".
                </div>
              </div>
            </div>
          )}

          {/* by-repo — YOUR repos as a SORTABLE table (default lastActive-desc, the PRIMARY signal) */}
          <div className="panel" data-testid="dev-byrepo">
            <div className="phead"><span className="kicker">Repo của bạn · mới nhất trước · bấm cột để sắp xếp</span><span className="hint" style={{ marginLeft: "auto" }}>{data.byRepo.length} repo</span></div>
            <div style={{ padding: "10px 16px 14px" }}>
              {data.byRepo.length === 0 ? (
                <span className="hint faint" data-testid="dev-byrepo-empty">Chưa có repo nào của bạn.</span>
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
                        <td className="num-col faint" data-testid={`repo-last-${r.repo}`}>{r.lastActive ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
