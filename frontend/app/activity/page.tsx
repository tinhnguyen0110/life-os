"use client";
/* ============================================================
   S14 — Activity Feed / Run Log. Ported from mock screens-active.js SCREENS.activity.
   3 stat cards (run-today / success+breakdown / avg-dur) · filter tabs (all/ok/err)
   + today/week segment (SERVER-side re-fetch) · feed rows (status chip ✓/⚠/✗ + name +
   detail + time/ago/dur) · click-row → expand full detail.
   RENDER-ONLY: successRate/avgDurationMs backend-computed; successRate null → "—"
   (NOT 0%). CAP: runs=newest-100, count=full total → "100 gần nhất / tổng N".
   States: loading · error · empty · data.
   ============================================================ */
import { useState } from "react";
import { useActivity } from "@/lib/useActivity";
import { relativeTime, fmtClock, fmtDuration, fmtRate, orDash } from "@/lib/format";
import { apiBase } from "@/lib/api";
import type { ActivityRun, RunStatus } from "@/lib/types";

/** status → feed-icon class + glyph + tone. warn shares the "run" (amber) chip. */
const STAT: Record<RunStatus, { cls: string; glyph: string; tone: string; label: string }> = {
  ok: { cls: "ok", glyph: "✓", tone: "pos", label: "thành công" },
  warn: { cls: "run", glyph: "⚠", tone: "mid", label: "cảnh báo" },
  error: { cls: "err", glyph: "✗", tone: "neg", label: "lỗi" },
};

function FeedRow({ run }: { run: ActivityRun }) {
  const [open, setOpen] = useState(false);
  const s = STAT[run.status] ?? STAT.ok;
  return (
    <div
      className={`feed-row${open ? " open" : ""}`}
      onClick={() => setOpen((v) => !v)}
      data-testid={`feed-row-${run.id}`}
      data-open={open}
    >
      <span className={`runi ${s.cls} fr-ic`} style={{ width: 17, height: 17, fontSize: 10 }}>{s.glyph}</span>
      <div className="fr-body">
        <div className="fr-t"><b>{orDash(run.routineName)}</b>{orDash(run.detail, "")}</div>
        <div className="fr-s">
          <span>{fmtClock(run.startedAt)}</span>
          <span>{relativeTime(run.startedAt)}</span>
          <span>{fmtDuration(run.durationMs)}</span>
          <span className={s.tone}>{s.label}</span>
        </div>
        {/* full detail revealed on click — backend gives one detail line; show it fuller + ids */}
        <div className="fr-out" data-testid={`feed-out-${run.id}`}>
          {`routine: ${run.routineId} (${run.routineName})\n`}
          {`status:  ${run.status}\n`}
          {`bắt đầu: ${run.startedAt}\n`}
          {`kết thúc: ${orDash(run.finishedAt)}\n`}
          {`thời lượng: ${fmtDuration(run.durationMs)}\n`}
          {`chi tiết: ${orDash(run.detail, "(không có)")}`}
        </div>
      </div>
      <span className="fr-chev">{open ? "▾" : "▸"}</span>
    </div>
  );
}

export default function ActivityPage() {
  const { data, status, errMsg, warning, statusFilter, rangeFilter, setStatusFilter, setRangeFilter, reload } =
    useActivity();

  const runs = data.runs ?? [];
  const capped = data.count > runs.length; // >100 in window → show cap message
  const routineCount = data.byRoutine?.length ?? 0;

  return (
    <section className="view" data-screen="S14" data-testid="activity-screen">
      <div className="vtitle">
        <h1>Activity Feed</h1>
        <span className="sub">run log · minh bạch mọi hành động tự động</span>
        <span className="sp" />
        {/* status filter tabs — SERVER-side re-fetch (cap + count stay correct per filter) */}
        <div className="tabs" data-testid="activity-tabs">
          <button type="button" className={`tab${statusFilter === "all" ? " on" : ""}`} onClick={() => setStatusFilter("all")} data-testid="tab-all">Tất cả</button>
          <button type="button" className={`tab${statusFilter === "ok" ? " on" : ""}`} onClick={() => setStatusFilter("ok")} data-testid="tab-ok">Thành công</button>
          <button type="button" className={`tab${statusFilter === "error" ? " on" : ""}`} onClick={() => setStatusFilter("error")} data-testid="tab-err">Lỗi</button>
        </div>
        <div className="seg" data-testid="activity-range">
          <button className={rangeFilter === "today" ? "on" : ""} type="button" onClick={() => setRangeFilter("today")}>Hôm nay</button>
          <button className={rangeFilter === "week" ? "on" : ""} type="button" onClick={() => setRangeFilter("week")}>Tuần</button>
        </div>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="activity-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="activity-loading">Đang tải activity…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="activity-error">
          Không tải được activity: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <>
          {/* 3 stat cards: run-today · success (+breakdown) · avg-dur */}
          <div className="grid g-3" data-testid="activity-stats">
            <div className="stat">
              <span className="sl">Run {rangeFilter === "today" ? "hôm nay" : "tuần này"}</span>
              <span className="sv">{data.count}</span>
              <span className="sd faint">qua {routineCount} routine{capped ? ` · ${runs.length} gần nhất hiển thị` : ""}</span>
            </div>
            <div className="stat">
              <span className="sl">Tỉ lệ thành công</span>
              {/* successRate null when count==0 → "—", never "0%" */}
              <span className={`sv ${data.successRate == null ? "" : data.successRate >= 80 ? "pos" : "mid"}`}>{fmtRate(data.successRate)}</span>
              <span className="sd faint" data-testid="activity-breakdown">{data.okCount} ok · {data.warnCount} warn · {data.errorCount} lỗi</span>
            </div>
            <div className="stat">
              <span className="sl">Thời gian TB</span>
              <span className="sv" style={{ fontSize: 20 }}>{fmtDuration(data.avgDurationMs)}</span>
              <span className="sd faint">mỗi run</span>
            </div>
          </div>

          {/* run-log feed */}
          <div className="panel" style={{ overflow: "hidden" }}>
            <div className="phead">
              <span className="kicker">Run log</span>
              <span className="dot g" />
              <span className="hint">live · tail -f</span>
              <span className="link" style={{ marginLeft: "auto", fontFamily: "var(--mono)", fontSize: 10.5 }} data-testid="activity-cap">
                {capped ? `hiển thị ${runs.length} gần nhất / tổng ${data.count}` : `${data.count} run`}
              </span>
            </div>
            {runs.length === 0 ? (
              <div className="hint" style={{ padding: "28px 16px", textAlign: "center" }} data-testid="activity-empty">
                Chưa có run nào trong khoảng này. {statusFilter !== "all" || rangeFilter !== "today" ? "Thử bỏ bộ lọc." : "Scheduler sẽ ghi log khi routine chạy."}
              </div>
            ) : (
              <div className="feed" data-testid="activity-feed">
                {runs.map((r) => <FeedRow key={r.id} run={r} />)}
              </div>
            )}
          </div>

          <div className="hint" style={{ textAlign: "center", padding: 4 }}>
            Bấm vào một dòng để xem log đầy đủ + output của run đó.
          </div>
        </>
      )}
    </section>
  );
}
