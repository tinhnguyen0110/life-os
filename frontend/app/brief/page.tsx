"use client";
/* ============================================================
   S11 — Daily Brief / Brief hôm nay. Ported from mock screens-overview.js .briefcard.
   Template-based roll-up (NO AI — header says "template", NOT opus; no "hỏi sâu" AI
   line this build). header (generatedAt/asOf/source) · 4 summary stat cards ·
   numbered severity-ordered priorities (severity-styled .pr) · brief history.
   RENDER-ONLY: summary numbers / priorities / severity backend-computed; null → "—".
   HONEST-EMPTY: priorities=[] → calm "ổn định" state (green), NOT an error.
   States: loading · error · ready(+calm).
   ============================================================ */
import { useBrief } from "@/lib/useBrief";
import { fmtClock, relativeTime, fmtUSD, fmtRate, orDash } from "@/lib/format";
import { apiBase } from "@/lib/api";
import type { Brief, Priority, Severity } from "@/lib/types";

/** severity → row tone class + Vietnamese label. */
const SEV: Record<Severity, { cls: string; label: string }> = {
  urgent: { cls: "urgent", label: "khẩn" },
  warn: { cls: "warn", label: "lưu ý" },
  info: { cls: "info", label: "thông tin" },
};

function PriorityRow({ p }: { p: Priority }) {
  const s = SEV[p.severity] ?? SEV.info;
  return (
    <div className={`pr ${s.cls}`} data-testid={`brief-priority-${p.n}`} data-severity={p.severity}>
      <span className="n">{String(p.n).padStart(2, "0")}</span>
      <span style={{ flex: 1 }}>
        {p.text}
        <span className="faint" style={{ marginLeft: 8, fontFamily: "var(--mono)", fontSize: 10.5 }}>
          {p.source} · {s.label}
        </span>
      </span>
    </div>
  );
}

/** the brief card (header + priorities or calm state) — reused for today + history. */
function BriefCard({ brief, history }: { brief: Brief; history?: boolean }) {
  const priorities = brief.priorities ?? [];
  return (
    <div className="card briefcard" data-testid={history ? "brief-history-card" : "brief-today-card"}>
      <div className="bh">
        <div className="ic">✦</div>
        <b>{history ? "Brief" : "Brief hôm nay"}</b>
        {/* "template" — honest: rule-based, NOT an AI model. + stale flag. */}
        <span className="t" data-testid={history ? undefined : "brief-meta"}>
          {fmtClock(brief.generatedAt)} · {orDash(brief.source, "template")}
          {brief.stale ? " · cũ" : ""}
        </span>
      </div>
      {priorities.length === 0 ? (
        <div className="pr-calm" data-testid={history ? undefined : "brief-calm"}>
          ✓ Ổn định — không có việc gì khẩn hôm nay. Cứ tiếp tục kế hoạch.
        </div>
      ) : (
        priorities.map((p) => <PriorityRow key={`${p.source}-${p.n}`} p={p} />)
      )}
    </div>
  );
}

export default function BriefPage() {
  const { brief, history, historyError, status, errMsg, warning, reload } = useBrief();

  return (
    <section className="view" data-screen="S11" data-testid="brief-screen">
      <div className="vtitle">
        <h1>Brief hôm nay</h1>
        <span className="sub">tóm tắt hằng ngày · template · không phải AI</span>
        <span className="sp" />
        {status === "ready" && brief && (
          <span className="hint" data-testid="brief-asof">
            cập nhật {relativeTime(brief.generatedAt)} · nguồn tới {orDash(brief.asOf)}
          </span>
        )}
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="brief-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="brief-loading">Đang tạo brief…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="brief-error">
          Không tạo được brief: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && brief && (
        <>
          {/* 4 summary stat cards (null source → "—", never a fabricated 0) */}
          <div className="grid g-4" data-testid="brief-summary">
            <div className="stat">
              <span className="sl">Tài sản ròng</span>
              <span className="sv">{fmtUSD(brief.summary.netWorth)}</span>
              <span className="sd faint">tổng portfolio</span>
            </div>
            <div className="stat">
              <span className="sl">Dự án active</span>
              <span className="sv pos">{brief.summary.projectsActive}</span>
              <span className="sd faint">đang chạy / chậm</span>
            </div>
            <div className="stat">
              <span className="sl">Claude quota</span>
              <span className="sv">{fmtRate(brief.summary.claudePct)}</span>
              <span className="sd faint">token đã đốt</span>
            </div>
            <div className="stat">
              <span className="sl">Cảnh báo hôm nay</span>
              <span className={`sv ${brief.summary.alertsToday > 0 ? "mid" : ""}`}>{brief.summary.alertsToday}</span>
              <span className="sd faint">giá kích hoạt</span>
            </div>
          </div>

          {/* numbered, severity-ordered priorities (or honest calm state) */}
          <div className="panel" style={{ padding: "15px 18px" }}>
            <div className="phead" style={{ padding: "0 0 11px", borderBottom: "1px solid var(--line)", marginBottom: 6 }}>
              <span className="kicker">Ưu tiên hôm nay</span>
              <span className="hint" style={{ marginLeft: "auto" }}>
                {(brief.priorities?.length ?? 0) > 0 ? `${brief.priorities.length} việc · xếp theo mức độ` : "không có việc khẩn"}
              </span>
            </div>
            <BriefCard brief={brief} />
          </div>

          {/* brief history (secondary — fail-open) */}
          <div className="panel" style={{ padding: "15px 18px" }} data-testid="brief-history">
            <div className="phead" style={{ padding: "0 0 11px", borderBottom: "1px solid var(--line)", marginBottom: 10 }}>
              <span className="kicker">Lịch sử brief</span>
            </div>
            {historyError ? (
              <span className="hint neg" data-testid="brief-history-error">Không tải được lịch sử: {historyError}</span>
            ) : history.length === 0 ? (
              <span className="hint" data-testid="brief-history-empty">Chưa có brief nào được lưu. Brief được lưu khi routine "morning-pull" chạy.</span>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {history.map((h, i) => (
                  <div key={h.generatedAt ?? i}>
                    <div className="hint" style={{ marginBottom: 4, fontFamily: "var(--mono)", fontSize: 10.5 }}>
                      {orDash(h.asOf)} · {relativeTime(h.generatedAt)}
                    </div>
                    <BriefCard brief={h} history />
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
