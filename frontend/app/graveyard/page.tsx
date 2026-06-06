"use client";
/* ============================================================
   S4 — Nghĩa địa dự án (Graveyard). Ported from mock screens-projects.js
   SCREENS.graveyard. Abandoned projects + honest pattern mirror (avgPeak,
   reached-vs-before, common reasons, lessons). RENDER-ONLY: stats backend-
   computed; lesson null → honest text (never fabricated). Restore per grave →
   POST /projects/{id}/restore → refetch (FAIL-CLOSED). "Xuất bài học" =
   client-side download of the lessons. States: loading·error·empty·data.
   ============================================================ */
import { useState } from "react";
import { useGraveyard } from "@/lib/useGraveyard";
import { fmtMonthYear } from "@/lib/format";
import { apiBase, ApiError } from "@/lib/api";
import type { GraveProject } from "@/lib/types";

type View = "grid" | "timeline";

export default function GraveyardPage() {
  const { data, status, errMsg, warning, reload, restore } = useGraveyard();
  const [view, setView] = useState<View>("grid");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState("");

  const graves = data.graves ?? [];

  async function onRestore(g: GraveProject) {
    setActionErr("");
    setBusyId(g.id);
    try {
      await restore(g.id);
    } catch (e) {
      // fail-closed: surface the error; the grave stays (not optimistically removed).
      setActionErr(`Khôi phục "${g.name}" thất bại: ${e instanceof ApiError ? e.message : (e as Error).message}`);
    } finally {
      setBusyId(null);
    }
  }

  function exportLessons() {
    // client-side download of the lessons (no server round-trip).
    const lines = [
      `# Bài học từ nghĩa địa dự án (${data.count} dự án)`,
      "",
      ...data.lessons.map((l, i) => `${i + 1}. ${l}`),
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "bai-hoc-nghia-dia.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  const sortedGraves =
    view === "timeline"
      ? [...graves].sort((a, b) => (b.died > a.died ? 1 : b.died < a.died ? -1 : 0))
      : graves;

  return (
    <section className="view" data-screen="S4" data-testid="graveyard-screen">
      <div className="vtitle">
        <h1>Nghĩa địa dự án</h1>
        <span className="sub">{data.count} dự án đã chôn · honest mirror</span>
        <span className="sp" />
        <button
          className="btn"
          type="button"
          onClick={exportLessons}
          disabled={data.lessons.length === 0}
          data-testid="export-lessons"
        >
          Xuất bài học
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="graveyard-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}
      {actionErr && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="graveyard-action-error">
          <span className="hint neg">⚠ {actionErr}</span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setActionErr("")}>đóng</span>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="graveyard-loading">Đang tải nghĩa địa…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="graveyard-error">
          Không tải được nghĩa địa: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <>
          {/* Pattern summary bar — avgPeak + reached-vs-before (render-only) */}
          <div className="panel" style={{ padding: "15px 17px", display: "flex", gap: 14, alignItems: "center" }} data-testid="graveyard-pattern">
            <div className="num" style={{ fontSize: 30, fontWeight: 700, color: "var(--accent)" }} data-testid="graveyard-avgpeak">
              {data.avgPeak}%
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, color: "var(--tx-0)" }} data-testid="graveyard-pattern-text">
                {data.avgPeak > 0 ? (
                  <>
                    Trung bình bạn bỏ dự án ở mức <b className="acc">{data.avgPeak}% hoàn thành</b>.{" "}
                  </>
                ) : (
                  <>
                    Các dự án bị bỏ <b className="acc">chưa ghi mức hoàn thành</b>.{" "}
                  </>
                )}
                <b>{data.reachedUser}</b> đã có user · <b>{data.beforeUser}</b> bỏ trước khi có user đầu tiên.
              </div>
              <div className="hint" style={{ marginTop: 3 }}>
                {data.commonReasons.length > 0
                  ? `Lý do hay gặp: ${data.commonReasons.map((r) => `${r.reason} (${r.count})`).join(" · ")}.`
                  : "Tấm gương thật, không phải để trách."}
              </div>
            </div>
            <div className="seg" data-testid="graveyard-toggle">
              <button className={view === "grid" ? "on" : ""} onClick={() => setView("grid")} type="button">Lưới</button>
              <button className={view === "timeline" ? "on" : ""} onClick={() => setView("timeline")} type="button">Dòng thời gian</button>
            </div>
          </div>

          {/* Grave cards */}
          {graves.length === 0 ? (
            <div className="hint" style={{ padding: "24px 4px" }} data-testid="graveyard-empty">
              Chưa có dự án nào trong nghĩa địa. 🎉
            </div>
          ) : (
            <div className="grid g-4" data-testid="graveyard-graves">
              {sortedGraves.map((g) => (
                <div className="grave-card" key={g.id} data-testid={`grave-${g.id}`}>
                  <div className="gname">{g.name}</div>
                  <div className="bar" style={{ opacity: 0.5 }}>
                    <i style={{ width: `${Math.max(0, Math.min(100, g.peak))}%`, background: "var(--tx-2)" }} />
                  </div>
                  <div className="greason">{g.reason}</div>
                  {/* lesson null → SKIP the 💡 line entirely (dispatch: never fabricate,
                      mock only renders 💡 when a lesson exists). */}
                  {g.lesson && <div className="glesson">💡 {g.lesson}</div>}
                  <div className="gmeta">
                    <span>peak {g.peak}% · {g.users > 0 ? `${g.users} user` : "0 user"}</span>
                    <span>† {fmtMonthYear(g.died)}</span>
                  </div>
                  <button
                    className="btn sm"
                    type="button"
                    onClick={() => onRestore(g)}
                    disabled={busyId === g.id}
                    data-testid={`restore-${g.id}`}
                  >
                    {busyId === g.id ? "Đang khôi phục…" : "↩ Khôi phục"}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Bài học rút ra */}
          <div className="panel" data-testid="graveyard-lessons">
            <div className="phead"><span className="kicker">Bài học rút ra</span></div>
            <div style={{ padding: "6px 8px 12px" }}>
              {data.lessons.length > 0 ? (
                data.lessons.map((l, i) => (
                  <div className="al" key={i}>
                    <span className="ad" style={{ background: "var(--accent)" }} />
                    <div className="at">{l}</div>
                  </div>
                ))
              ) : (
                <span className="hint" style={{ padding: "8px 10px", display: "block" }}>
                  Chưa có bài học nào được ghi lại (ghi `lesson:` trong status.md khi abandon).
                </span>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
