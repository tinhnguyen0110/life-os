"use client";
/* ============================================================
   HomeActivityTile — the S1 Home Activity-feed tile, now LIVE (replaces the
   coming-soon stub). Self-fetches /activity via useActivity so it fails
   INDEPENDENTLY (per-tile fail-open: activity down → this tile shows its own
   error, the rest of Home is unaffected). Shows the recent N runs (status chip +
   routine name + relative time). render-only; click-through → /activity.
   ============================================================ */
import { useActivity } from "@/lib/useActivity";
import { relativeTime, orDash } from "@/lib/format";
import { useSafeRouter } from "@/lib/useNav";
import type { RunStatus } from "@/lib/types";

const CHIP: Record<RunStatus, { cls: string; glyph: string }> = {
  ok: { cls: "ok", glyph: "✓" },
  warn: { cls: "run", glyph: "⚠" },
  error: { cls: "err", glyph: "✗" },
};

const RECENT_N = 5;

export function HomeActivityTile() {
  const { data, status, errMsg } = useActivity();
  const router = useSafeRouter();
  const recent = (data.runs ?? []).slice(0, RECENT_N);

  return (
    <div className="panel" data-testid="home-activity-tile">
      <div className="phead">
        <span className="kicker">Activity</span>
        <span className="dot g" />
        <span className="link" style={{ marginLeft: "auto" }} onClick={() => router.push("/activity")}>xem tất cả →</span>
      </div>
      <div style={{ padding: "8px 16px 14px" }}>
        {status === "loading" && <span className="hint" data-testid="home-activity-loading">Đang tải…</span>}
        {status === "error" && (
          <div className="hint neg" data-testid="home-activity-error">Activity không tải được: {errMsg}</div>
        )}
        {status === "ready" && (
          recent.length === 0 ? (
            <span className="hint" data-testid="home-activity-empty">Chưa có run nào hôm nay.</span>
          ) : (
            recent.map((r) => {
              const c = CHIP[r.status] ?? CHIP.ok;
              return (
                <div className="mrow" key={r.id} data-testid={`home-activity-row-${r.id}`}>
                  <span className="k" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className={`runi ${c.cls}`} style={{ width: 15, height: 15, fontSize: 9 }}>{c.glyph}</span>
                    {orDash(r.routineName)}
                  </span>
                  <span className="v mut" style={{ fontSize: 11 }}>{relativeTime(r.startedAt)}</span>
                </div>
              );
            })
          )
        )}
      </div>
    </div>
  );
}
