"use client";
/* ============================================================
   HomeClaudeTile — the S1 Home Claude tile, LIVE (S9). Self-fetches
   /claude-usage via useClaudeUsage so it fails INDEPENDENTLY (per-tile fail-open).
   Mini gauge shows the LIVE 5h quota % (pct5h) when present — NOT today/cap (which
   overflows 100% once today = all-project tokens). Falls back to pct only without a
   snapshot. Sub-line: cost + project count. render-only.
   ============================================================ */
import { useClaudeUsage } from "@/lib/useClaudeUsage";
import { fmtUSD } from "@/lib/format";
import { gauge } from "@/lib/spark";
import { useSafeRouter } from "@/lib/useNav";

export function HomeClaudeTile() {
  const { data, status } = useClaudeUsage();
  const router = useSafeRouter();

  // LIVE 5h quota % when we have a snapshot; else fall back to the today/cap pct.
  const gaugePct = data ? (data.pct5h ?? data.pct) : 0;
  const gaugeLabel = data?.pct5h != null ? "5h" : "đã đốt";

  return (
    <div
      className="card"
      style={{ alignItems: "center", justifyContent: "center", gap: 6, cursor: "pointer" }}
      onClick={() => router.push("/claude-usage")}
      data-testid="home-claude-tile"
    >
      <div className="kicker" style={{ alignSelf: "flex-start" }}>Claude · usage</div>
      {status === "loading" && <div className="hint" style={{ padding: "18px 8px" }}>…</div>}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "18px 8px", textAlign: "center" }} data-testid="home-claude-error">
          usage không tải được
        </div>
      )}
      {status === "ready" && data && (
        <>
          <div className="gauge" style={{ width: 96, height: 96 }}>
            <span dangerouslySetInnerHTML={{ __html: gauge(gaugePct, "var(--accent)", 96, 9) }} />
            <div className="lab">
              <b style={{ fontSize: 20, color: "var(--accent)" }}>{gaugePct}%</b>
              <span style={{ fontSize: 9 }}>{gaugeLabel}</span>
            </div>
          </div>
          {/* LIVE 5h + 7d quota — each pill shows used % AND its reset countdown */}
          {data.quotaSource === "snapshot" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 4, width: "100%", alignItems: "center" }} data-testid="home-claude-quota">
              {data.pct5h != null && (
                <div className="num" style={{ fontSize: 10, display: "flex", gap: 6, alignItems: "baseline" }}>
                  <span className="faint">5h</span>
                  <b className="acc">{data.pct5h}%</b>
                  {data.resetIn && <span className="faint">↻ {data.resetIn}</span>}
                </div>
              )}
              {data.weekly != null && (
                <div className="num" style={{ fontSize: 10, display: "flex", gap: 6, alignItems: "baseline" }}>
                  <span className="faint">7d</span>
                  <b style={{ color: "var(--blue)" }}>{data.weekly}%</b>
                  {data.resetWeek && <span className="faint">↻ {data.resetWeek}</span>}
                </div>
              )}
            </div>
          )}
          {/* cost + project count — the headline numbers, not used/cap */}
          <div className="num acc" style={{ fontSize: 13, fontWeight: 600 }}>{fmtUSD(data.costUSD)}</div>
          <div className="num faint" style={{ fontSize: 9.5 }}>
            {data.byProject.length > 0 ? `${data.byProject.length} dự án` : data.tokenSource}
          </div>
        </>
      )}
    </div>
  );
}
