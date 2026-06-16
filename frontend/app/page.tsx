"use client";
/* ============================================================
   S1 — Command Center (Home). Ported from mock screens-overview.js SCREENS.home.
   Aggregates 3 live sources via useHome with PER-TILE FAIL-OPEN: one endpoint
   down → that tile shows its own error, the rest render, a top warning names it.
   RENDER-ONLY: every number comes from the source endpoints (formatted, never
   recomputed). Claude-quota + Brief tiles = COMING-SOON STUBS — never fake
   numbers (the endpoints don't exist yet; show a placeholder, not invented data).
   Tiles click through to their detail screens.
   ============================================================ */
import { useHome } from "@/lib/useHome";
import { useSafeRouter } from "@/lib/useNav";
import { HealthChip } from "@/components/shared/HealthChip";
import { ProgressBar } from "@/components/shared/ProgressBar";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { HomeClaudeTile } from "@/components/HomeClaudeTile";
import { HomeActivityTile } from "@/components/HomeActivityTile";
import { HomeBriefTile } from "@/components/HomeBriefTile";
import { fmtUSD, fmtSign, fmtPct, orDash } from "@/lib/format";
import { spark } from "@/lib/spark";
import type { ProjectStatus } from "@/lib/types";

const CHANNEL_COLOR: Record<string, string> = {
  crypto: "var(--accent)",
  etf: "#4DA6FF",
  vn: "#a877ff",
  dry: "#4a3a2a",
};

function pnlCell(abs: number | null | undefined): { text: string; cls: string } {
  if (abs == null || !Number.isFinite(abs) || abs === 0) return { text: "—", cls: "faint" };
  return { text: fmtSign(abs), cls: abs < 0 ? "neg" : "pos" };
}

/** A tile that failed → compact inline error (fail-open: doesn't blank the screen). */
function TileError({ label, msg }: { label: string; msg: string }) {
  return (
    <div className="hint neg" style={{ padding: "14px 16px" }} data-testid="tile-error">
      {label} không tải được: {msg}
    </div>
  );
}

export default function HomePage() {
  const { finance, projects, market, status, warning, reload } = useHome();
  const router = useSafeRouter();

  const projectColumns: Column<ProjectStatus>[] = [
    { key: "name", header: "Dự án", className: "pn", cell: (p) => p.name },
    { key: "health", header: "Sức khỏe", cell: (p) => <HealthChip health={p.health} /> },
    { key: "progress", header: "Tiến độ", cell: (p) => <ProgressBar value={p.progress} health={p.health} /> },
    { key: "users", header: "Users", cell: (p) => <span className={p.users > 0 ? "pos" : "faint"}>{p.users}</span> },
    { key: "next", header: "Next", className: "mut", cell: (p) => orDash(p.next) },
  ];

  const fin = finance.data;
  const finSeries = fin?.series ?? [];
  const sparkHtml = finSeries.length >= 2 ? spark(finSeries, "var(--accent)", 640, 120) : "";
  const projectRows = projects.data?.projects ?? [];
  const projSummary = projects.data?.summary;
  const alertHistory = market.data?.alertHistory ?? [];

  return (
    <section className="view" data-screen="S1" data-testid="home-screen">
      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="home-loading">
          Đang tải command center…
        </div>
      )}

      {status === "ready" && (
        <>
          {warning && (
            <div className="panel" style={{ padding: "10px 14px" }} data-testid="home-warning">
              <span className="hint mid">⚠ {warning}</span>
              <span className="link" style={{ marginLeft: 10 }} onClick={reload}>thử lại</span>
            </div>
          )}

          {/* KPI strip: net-worth (finance) · P&L per channel (finance) · Claude quota (stub) */}
          <div className="grid" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
            {/* Net worth + allocation bar */}
            {finance.status === "error" ? (
              <div className="card glowcard"><TileError label="Tài chính" msg={finance.errMsg} /></div>
            ) : (
              <div
                className="card glowcard"
                style={{ minHeight: 150, cursor: "pointer" }}
                onClick={() => router.push("/finance")}
                data-testid="home-networth"
              >
                {sparkHtml && (
                  <div className="chartbg" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: "50%", opacity: 0.4 }}
                    dangerouslySetInnerHTML={{ __html: sparkHtml }} />
                )}
                <div className="kicker" style={{ position: "relative" }}>Tổng tài sản · USD</div>
                <div className="num" style={{ fontSize: 34, fontWeight: 700, position: "relative" }}>{fmtUSD(fin?.totalValue)}</div>
                <div className="nwd" style={{ position: "relative", marginTop: 4 }}>
                  <span className={`num ${(fin?.change?.abs ?? 0) < 0 ? "neg" : "pos"}`}>
                    {(fin?.change?.abs ?? 0) < 0 ? "▼" : "▲"} {fmtSign(fin?.change?.abs)} · {fmtPct(fin?.change?.pct ?? null)}
                  </span>
                </div>
                {/* allocation bar */}
                <div className="allocbar" style={{ position: "relative", display: "flex", height: 7, borderRadius: 4, overflow: "hidden", marginTop: 10 }}>
                  {(fin?.allocations ?? []).map((a) => (
                    <div key={a.channel} style={{ width: `${Math.max(0, a.pct)}%`, background: CHANNEL_COLOR[a.channel] ?? "var(--accent)" }} />
                  ))}
                </div>
              </div>
            )}

            {/* P&L per channel */}
            {finance.status === "error" ? (
              <div className="card"><TileError label="P&L" msg={finance.errMsg} /></div>
            ) : (
              <div className="card" data-testid="home-pnl">
                <div className="kicker" style={{ marginBottom: 4 }}>P&amp;L theo kênh</div>
                {(fin?.allocations ?? []).map((a) => {
                  const c = pnlCell(a.pnl?.abs);
                  return (
                    <div className="mrow" key={a.channel}>
                      <span className="k" style={{ textTransform: "capitalize" }}>{a.channel}</span>
                      <span className={`v num ${c.cls}`}>{c.text}</span>
                    </div>
                  );
                })}
                {(fin?.allocations ?? []).length === 0 && <span className="hint">Chưa có dữ liệu.</span>}
                {/* Total P&L row — pnlTotal.abs/pct from backend (render-only). The pct
                    carries its SCOPE (pnlScope) so −72.5% isn't misread as whole-portfolio
                    (it's on the ~2.2% with a basis). Null-safe: pnlScope null → bare pct. */}
                {fin?.pnlTotal && (
                  <div style={{ borderTop: "1px solid var(--line)", marginTop: 4, paddingTop: 6 }}>
                    <div className="mrow" style={{ borderBottom: 0, padding: 0 }} data-testid="home-pnl-total">
                      <span className="k"><b>Tổng</b></span>
                      <span className={`v num ${(fin.pnlTotal.abs ?? 0) < 0 ? "neg" : "pos"}`}>
                        {fmtSign(fin.pnlTotal.abs)} ({fmtPct(fin.pnlTotal.pct ?? null)})
                      </span>
                    </div>
                    {fin.pnlScope?.coveragePct != null && Number.isFinite(fin.pnlScope.coveragePct) && (
                      <div
                        className="hint faint"
                        style={{ fontSize: 10, marginTop: 2, lineHeight: 1.3 }}
                        title={fin.pnlScope.note}
                        data-testid="home-pnl-scope"
                      >
                        trên ~{fin.pnlScope.coveragePct.toFixed(1)}% danh mục có giá vốn
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Claude quota — LIVE tile (S9 shipped). Self-fetches /claude-usage,
                fails independently (per-tile fail-open). Click → S9. */}
            <HomeClaudeTile />
          </div>

          {/* mid: projects table (projects) + Brief stub */}
          <div className="grid" style={{ gridTemplateColumns: "1.7fr 1fr", alignItems: "start" }}>
            <div className="panel" style={{ overflow: "hidden" }}>
              <div className="phead">
                <span className="kicker">Dự án đang chạy</span>
                <span className="link" style={{ marginLeft: "auto" }} onClick={() => router.push("/projects")}>xem tất cả →</span>
              </div>
              {projects.status === "error" ? (
                <TileError label="Dự án" msg={projects.errMsg} />
              ) : (
                <>
                  <DataTable
                    columns={projectColumns}
                    rows={projectRows}
                    rowKey={(p) => p.id}
                    onRowClick={(p) => router.push(`/projects/${p.id}`)}
                    emptyLabel="Chưa có dự án nào."
                  />
                  {projSummary && (
                    <div className="hint" style={{ padding: "11px 16px", borderTop: "1px solid var(--line)", display: "flex", gap: 16 }}>
                      <span>
                        {projSummary.total} dự án · <span className="pos">{projSummary.act} active</span> ·{" "}
                        <span className="mid">{projSummary.slow} chậm</span> · <span className="neg">{projSummary.stall} đứng</span>
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Brief — LIVE (S11 built; top-N severity-ordered priorities, per-tile fail-open) */}
            <HomeBriefTile />
          </div>

          {/* bottom: alerts (market) + ticker note */}
          <div className="grid g-2" style={{ alignItems: "start" }}>
            <div className="panel" data-testid="home-alerts">
              <div className="phead">
                <span className="kicker">Cảnh báo</span>
                <span className="dot r" />
                <span className="link" style={{ marginLeft: "auto" }} onClick={() => router.push("/market")}>xem tất cả →</span>
              </div>
              <div style={{ padding: "8px 16px 14px" }}>
                {market.status === "error" ? (
                  <TileError label="Thị trường" msg={market.errMsg} />
                ) : alertHistory.length > 0 ? (
                  alertHistory.slice(0, 4).map((a, i) => (
                    <div className="mrow" key={`${a.symbol}-${a.ts}-${i}`}>
                      <span className="k">{a.symbol} {a.op === "above" ? "≥" : "≤"} {fmtUSD(a.threshold)}</span>
                      <span className="v mut" style={{ fontSize: 11 }}>@ {fmtUSD(a.price)}</span>
                    </div>
                  ))
                ) : (
                  <span className="hint">Chưa có cảnh báo nào kích hoạt.</span>
                )}
              </div>
            </div>

            {/* Activity Feed — LIVE (S14 built; recent runs, per-tile fail-open) */}
            <HomeActivityTile />
          </div>
        </>
      )}
    </section>
  );
}
