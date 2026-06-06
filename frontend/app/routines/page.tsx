"use client";
/* ============================================================
   S13 — Automation / Routines. Ported from mock screens-active.js SCREENS.automation.
   4 stat cards · scheduler-status banner + trigger filter · routine cards (toggle/
   run/last-run/runs) · CONSTRAINED "Routine mới" (→ note, not a builder — north-star
   ~6 routines). RENDER-ONLY stats. toggle (PATCH) + run (POST) are FAIL-CLOSED.
   States: loading·error·data.
   ============================================================ */
import { useMemo, useState } from "react";
import { useRoutines } from "@/lib/useRoutines";
import { relativeTime } from "@/lib/format";
import { apiBase } from "@/lib/api";
import { Icon } from "@/lib/icons";
import type { RoutineInfo, Trigger } from "@/lib/types";

type FilterT = "all" | "scheduled" | "event";

/** trigger → display pill class + label (interval/cron=scheduled, event=event, date=ondemand). */
const TRIG: Record<Trigger, { cls: string; label: string }> = {
  interval: { cls: "scheduled", label: "Lịch" },
  cron: { cls: "scheduled", label: "Cron" },
  date: { cls: "ondemand", label: "Hẹn giờ" },
  event: { cls: "event", label: "Sự kiện" },
};

export default function RoutinesPage() {
  const { data, status, errMsg, warning, reload, toggle, run } = useRoutines();
  const [filter, setFilter] = useState<FilterT>("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [showNewNote, setShowNewNote] = useState(false);

  const routines = data.routines ?? [];
  const filtered = useMemo(() => {
    if (filter === "all") return routines;
    if (filter === "event") return routines.filter((r) => r.trigger === "event");
    return routines.filter((r) => r.trigger === "interval" || r.trigger === "cron");
  }, [routines, filter]);

  async function onToggle(r: RoutineInfo) {
    setActionMsg(null);
    setBusyId(r.id);
    try {
      await toggle(r.id, !r.enabled);
    } catch (e) {
      setActionMsg({ kind: "err", text: `Bật/tắt "${r.name}" thất bại: ${(e as Error).message}` });
    } finally {
      setBusyId(null);
    }
  }

  async function onRun(r: RoutineInfo) {
    setActionMsg(null);
    setBusyId(r.id);
    try {
      const res = await run(r.id);
      setActionMsg({ kind: res.status === "error" ? "err" : "ok", text: `${r.name}: ${res.status} — ${res.detail}` });
    } catch (e) {
      setActionMsg({ kind: "err", text: `Chạy "${r.name}" thất bại: ${(e as Error).message}` });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="view" data-screen="S13" data-testid="routines-screen">
      <div className="vtitle">
        <h1>Automation / Routines</h1>
        <span className="sub">{data.activeCount}/{data.total} active · bạn ra luật, AI thực thi</span>
        <span className="sp" />
        <button className="btn accent" type="button" onClick={() => setShowNewNote((v) => !v)} data-testid="routine-new">
          + Routine mới
        </button>
      </div>

      {/* CONSTRAINED "Routine mới" → note, NOT a builder (north-star ~6 routines) */}
      {showNewNote && (
        <div className="panel" style={{ padding: "12px 16px" }} data-testid="routine-new-note">
          <span className="hint">
            Sắp có · <b className="acc">giới hạn ~6 routine có chủ đích</b> — mỗi routine mới phải qua test "tiết kiệm thời gian thật, hay chỉ đẩy ra cho có?". Không xây marketplace skill.
          </span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setShowNewNote(false)}>đóng</span>
        </div>
      )}

      {warning && <div className="panel" style={{ padding: "10px 14px" }} data-testid="routines-warning"><span className="hint mid">⚠ {warning}</span></div>}
      {actionMsg && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="routines-action-msg">
          <span className={`hint ${actionMsg.kind === "err" ? "neg" : "pos"}`}>{actionMsg.kind === "err" ? "⚠" : "✓"} {actionMsg.text}</span>
          <span className="link" style={{ marginLeft: 10 }} onClick={() => setActionMsg(null)}>đóng</span>
        </div>
      )}

      {status === "loading" && <div className="hint" style={{ padding: "24px 4px" }} data-testid="routines-loading">Đang tải routines…</div>}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="routines-error">
          Không tải được routines: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <>
          {/* 4 stat cards */}
          <div className="grid g-4" data-testid="routines-stats">
            <div className="stat"><span className="sl">Routine active</span><span className="sv pos">{data.activeCount}</span><span className="sd faint">trên {data.total} đã định nghĩa</span></div>
            <div className="stat"><span className="sl">Chạy hôm nay</span><span className="sv">{data.runsToday}</span><span className="sd faint">run_log rows</span></div>
            <div className="stat"><span className="sl">Lần chạy gần nhất</span><span className="sv" style={{ fontSize: 16 }}>{data.lastRunAt ? relativeTime(data.lastRunAt) : "—"}</span><span className="sd faint">overall</span></div>
            {/* No live-running state this build → 0 (dispatch: "scheduler idle"). */}
            <div className="stat"><span className="sl">Đang chạy</span><span className="sv acc">0</span><span className="sd faint">scheduler idle</span></div>
          </div>

          {/* scheduler-status banner + trigger filter */}
          <div className="panel" style={{ padding: "13px 16px", display: "flex", gap: 12, alignItems: "center" }} data-testid="routines-banner">
            <span className="dot g" />
            <div style={{ flex: 1, fontSize: 12.5, color: "var(--tx-0)" }}>
              <b style={{ fontFamily: "var(--mono)" }}>Scheduler online.</b>{" "}
              <span className="mut">Cron + event listener đang lắng nghe. AI kích hoạt routine on-demand qua MCP — chỉ những routine bạn đã định nghĩa.</span>
            </div>
            <div className="seg" data-testid="routines-filter">
              <button className={filter === "all" ? "on" : ""} type="button" onClick={() => setFilter("all")}>Tất cả</button>
              <button className={filter === "scheduled" ? "on" : ""} type="button" onClick={() => setFilter("scheduled")}>Lịch</button>
              <button className={filter === "event" ? "on" : ""} type="button" onClick={() => setFilter("event")}>Sự kiện</button>
            </div>
          </div>

          {/* routine cards */}
          {filtered.length === 0 ? (
            <div className="hint" style={{ padding: "24px 4px" }} data-testid="routines-empty">Không có routine khớp bộ lọc.</div>
          ) : (
            <div className="grid g-2" style={{ alignItems: "start" }} data-testid="routines-cards">
              {filtered.map((r) => {
                const t = TRIG[r.trigger] ?? TRIG.interval;
                return (
                  <div className={`routine-card${r.enabled ? "" : " off"}`} key={r.id} data-testid={`routine-${r.id}`}>
                    <div className="rc-top">
                      <div className="rc-ic"><Icon name="i-bolt" /></div>
                      <div style={{ flex: 1 }}>
                        <div className="rc-name">{r.name}</div>
                        <div className="rc-trig"><span className={`trigpill ${t.cls}`}>{t.label}</span> {r.triggerLabel}</div>
                      </div>
                      <button
                        className={`toggle${r.enabled ? " on" : ""}`}
                        type="button"
                        aria-label={r.enabled ? "Tắt routine" : "Bật routine"}
                        onClick={() => onToggle(r)}
                        disabled={busyId === r.id}
                        data-testid={`toggle-${r.id}`}
                      />
                    </div>
                    <div className="rc-desc">{r.desc}</div>
                    <div className="rc-action"><span className="faint">→ </span>{r.action}</div>
                    <div className="rc-foot">
                      {/* lastResult chip: ok=✓ / warn=⚠ / error=✗ / null=no chip (never ran). */}
                      {r.lastResult != null && (
                        <span
                          className={`runi ${r.lastResult === "error" ? "err" : r.lastResult === "warn" ? "run" : "ok"}`}
                          style={{ width: 15, height: 15, fontSize: 9 }}
                          title={r.lastResult}
                          data-testid={`result-${r.id}`}
                        >
                          {r.lastResult === "error" ? "✗" : r.lastResult === "warn" ? "⚠" : "✓"}
                        </span>
                      )}
                      <span>chạy cuối {r.lastRun ? relativeTime(r.lastRun) : "chưa chạy"}</span>
                      <span style={{ marginLeft: "auto" }}>{r.runs.toLocaleString()} lần</span>
                      <button className="btn sm ghost" style={{ padding: "3px 9px" }} type="button" onClick={() => onRun(r)} disabled={busyId === r.id} data-testid={`run-${r.id}`}>
                        <Icon name="i-bolt" /> {busyId === r.id ? "…" : "Chạy"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* intentional-limit note */}
          <div className="panel" style={{ padding: "15px 17px", opacity: 0.85 }}>
            <span className="hint" style={{ fontSize: 13, lineHeight: 1.5 }}>
              <b style={{ color: "var(--tx-0)" }}>Giới hạn có chủ đích:</b> ~6 routine có mục đích rõ. Mỗi routine mới phải qua test <span className="acc">"tiết kiệm thời gian thật, hay chỉ đẩy ra cho có?"</span> — không xây marketplace 54 skill.
            </span>
          </div>
        </>
      )}
    </section>
  );
}
