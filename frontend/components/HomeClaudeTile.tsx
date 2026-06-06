"use client";
/* ============================================================
   HomeClaudeTile — the S1 Home Claude-quota tile, now LIVE (replaces the
   coming-soon stub). Self-fetches /claude-usage via useClaudeUsage so it fails
   INDEPENDENTLY (per-tile fail-open: if usage is down, this tile shows its own
   error; the rest of Home is unaffected). Mini gauge + pct + used/cap.
   render-only; resetIn stub → honest text, no fake countdown.
   ============================================================ */
import { useClaudeUsage } from "@/lib/useClaudeUsage";
import { fmtTokens } from "@/lib/format";
import { gauge } from "@/lib/spark";
import { useSafeRouter } from "@/lib/useNav";

export function HomeClaudeTile() {
  const { data, status } = useClaudeUsage();
  const router = useSafeRouter();

  return (
    <div
      className="card"
      style={{ alignItems: "center", justifyContent: "center", gap: 6, cursor: "pointer" }}
      onClick={() => router.push("/claude-usage")}
      data-testid="home-claude-tile"
    >
      <div className="kicker" style={{ alignSelf: "flex-start" }}>Claude · quota</div>
      {status === "loading" && <div className="hint" style={{ padding: "18px 8px" }}>…</div>}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "18px 8px", textAlign: "center" }} data-testid="home-claude-error">
          usage không tải được
        </div>
      )}
      {status === "ready" && data && (
        <>
          <div className="gauge" style={{ width: 96, height: 96 }}>
            <span dangerouslySetInnerHTML={{ __html: gauge(data.pct, "var(--accent)", 96, 9) }} />
            <div className="lab">
              <b style={{ fontSize: 20, color: "var(--accent)" }}>{data.pct}%</b>
              <span style={{ fontSize: 9 }}>đã đốt</span>
            </div>
          </div>
          <div className="num faint" style={{ fontSize: 10 }}>
            {fmtTokens(data.used)} / {fmtTokens(data.cap)}
          </div>
        </>
      )}
    </div>
  );
}
