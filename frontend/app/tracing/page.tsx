"use client";
/* ============================================================
   /tracing (#65-P3 · S14 · G-HABIT) — the Daily Tracing habit board. The user
   sees today's per-activity cards (streak + progress), a 12-week heatmap, the
   score panel, and can LOG a session + add/archive activities.

   Ported from mock template/Life Command/app/screens-active.js (S14 block):
   per-activity card w/ streak badge (🔥≥7 / ✦≥3 / none), week bars, today
   progress; score KPI strip; 12-week heatmap (band by per-day COUNT). RENDER-ONLY
   — the backend computes ALL derived metrics (streak/pct/week/heatmap/score); the
   FE displays them + POSTs raw sessions, never recomputes.

   ADAPTATION (honest-mirror): the mock timeline shows per-session rows with
   timestamps, but the API exposes only a per-activity TODAY rollup (no per-session
   list) — so the timeline renders one row per activity that has today activity,
   from the real API, instead of fabricating session timestamps.
   Errors are the #46/#70 {error:{code,message,hint}} shape — message + hint shown.
   ============================================================ */
import { useMemo, useState } from "react";
import { useTracing } from "@/lib/useTracing";
import { apiBase, ApiError } from "@/lib/api";
import type { ActivityView, ActivityInput, TracingLogInput, RemindRepeat } from "@/lib/types";

const WEEK_DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]; // Mon→Sun

/** streak badge thresholds — ported EXACTLY from mock screens-active.js:80. */
function streakBadge(streak: number): string {
  return streak >= 7 ? "🔥" : streak >= 3 ? "✦" : "";
}

/** heatmap cell color by per-day COUNT (0 = empty; band by count/max where max =
 *  active-activity-count, capped so a 0-activity board doesn't divide-by-zero).
 *  Ours is COUNT (not the mock's capped 0-4) — band relative to max. */
function heatColor(count: number, max: number): string {
  if (count <= 0) return "var(--bg-3)";
  const denom = Math.max(1, max);
  const a = 0.18 + 0.82 * Math.min(1, count / denom); // 18%..100% opacity
  return `color-mix(in oklch, var(--accent) ${Math.round(a * 100)}%, var(--bg-3))`;
}

type LogForm = { id: string; name: string; unit: string; val: string; durMin: string; note: string };
type AddForm = {
  id: string; name: string; goal: string; unit: string; emoji: string; color: string;
  // #75: optional habit-reminder nudge. remindOn drives the toggle; when on, remindTime
  // + remindRepeat become the activity's remindAt/remindRepeat (BE creates the reminder).
  remindOn: boolean; remindTime: string; remindRepeat: RemindRepeat;
};

const EMPTY_ADD: AddForm = {
  id: "", name: "", goal: "", unit: "", emoji: "", color: "#FF6A33",
  remindOn: false, remindTime: "07:00", remindRepeat: "daily",
};

export default function TracingPage() {
  const { data, status, errMsg, warning, reload, log, add, archive } = useTracing();
  const [logForm, setLogForm] = useState<LogForm | null>(null);
  const [adding, setAdding] = useState<AddForm | null>(null);
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [rowErr, setRowErr] = useState("");

  const acts = data.activities ?? [];
  const sc = data.score;
  // max per-day count across the heatmap (for relative banding); fall back to active count.
  const heatMax = useMemo(
    () => Math.max(sc.total, ...data.heatmap12w),
    [data.heatmap12w, sc.total],
  );
  // timeline (adapted): one row per activity that has any today activity.
  const todayRows = useMemo(() => acts.filter((a) => a.today.sessions > 0), [acts]);

  async function onLog(e: React.FormEvent) {
    e.preventDefault();
    if (!logForm) return;
    setFormErr("");
    const val = Number(logForm.val);
    if (logForm.val.trim() === "" || !Number.isFinite(val) || val < 0) {
      setFormErr("Cần một giá trị ≥ 0.");
      return;
    }
    const durMin = logForm.durMin.trim() === "" ? null : Number(logForm.durMin);
    if (durMin != null && (!Number.isInteger(durMin) || durMin < 0)) {
      setFormErr("Thời lượng (phút) phải là số nguyên ≥ 0.");
      return;
    }
    const body: TracingLogInput = { val, dur_min: durMin, note: logForm.note.trim() || null };
    setBusy(true);
    try {
      await log(logForm.id, body);
      setLogForm(null);
    } catch (err) {
      setFormErr(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!adding) return;
    setFormErr("");
    if (!adding.id.trim() || !adding.name.trim()) {
      setFormErr("Cần id + tên hoạt động.");
      return;
    }
    const goal = Number(adding.goal);
    if (adding.goal.trim() === "" || !Number.isFinite(goal) || goal <= 0) {
      setFormErr("Mục tiêu phải là số > 0.");
      return;
    }
    const body: ActivityInput = {
      id: adding.id.trim(),
      name: adding.name.trim(),
      goal,
      unit: adding.unit.trim() || undefined,
      emoji: adding.emoji.trim() || undefined,
      color: adding.color || undefined,
      // #75: send remindAt/remindRepeat (CAMEL — the tracing module's wire convention,
      // like durMin) ONLY when the toggle is on — the BE creates the linked reminder.
      // Off → remindAt null (no reminder). FE just sends it.
      remindAt: adding.remindOn ? adding.remindTime : null,
      remindRepeat: adding.remindOn ? adding.remindRepeat : "off",
    };
    setBusy(true);
    try {
      await add(body);
      setAdding(null);
    } catch (err) {
      setFormErr(errText(err));
    } finally {
      setBusy(false);
    }
  }

  async function onArchive(id: string) {
    setRowErr("");
    setBusy(true);
    try {
      await archive(id);
    } catch (err) {
      setRowErr(errText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="view" data-screen="S14" data-testid="tracing-screen">
      <div className="vtitle">
        <h1>Daily Tracing</h1>
        <span className="sub">
          {data.date || "—"} · {sc.done}/{sc.total} activities · {sc.timeActive || "0m"} active
        </span>
        <span className="sp" />
        <button
          className="btn accent"
          type="button"
          onClick={() => { setAdding({ ...EMPTY_ADD }); setFormErr(""); }}
          data-testid="add-activity"
        >
          + Hoạt động
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="tracing-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {/* KPI strip — render-only from the backend score. */}
      {status === "ready" && (
        <div className="grid g-4" data-testid="tracing-score">
          <div className="stat">
            <span className="sl">Thời gian active</span>
            <span className="sv acc">{sc.timeActive || "0m"}</span>
            <span className="sd faint">hôm nay · {sc.done}/{sc.total} done</span>
          </div>
          <div className="stat">
            <span className="sl">Streak tốt nhất</span>
            <span className="sv pos">{sc.topStreak}</span>
            <span className="sd faint">ngày liên tiếp</span>
          </div>
          <div className="stat">
            <span className="sl">Hoàn thành hôm nay</span>
            <span className="sv">{sc.pct}%</span>
            <span className="sd faint">{sc.done}/{sc.total} đạt mục tiêu</span>
          </div>
          <div className="stat">
            <span className="sl">Còn lại hôm nay</span>
            <span className="sv mid">{Math.max(0, sc.total - sc.done)}</span>
            <span className="sd faint">hoạt động chưa đạt</span>
          </div>
        </div>
      )}

      {/* Add-activity form */}
      {adding && (
        <div className="panel" data-testid="add-form">
          <div className="phead"><span className="kicker">Hoạt động mới</span></div>
          <form onSubmit={onAdd} style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div className="field"><span className="flabel">ID (không dấu, vd water)</span>
              <input className="finput" value={adding.id} onChange={(e) => setAdding({ ...adding, id: e.target.value })} data-testid="a-id" placeholder="water" /></div>
            <div className="field"><span className="flabel">Tên</span>
              <input className="finput" value={adding.name} onChange={(e) => setAdding({ ...adding, name: e.target.value })} data-testid="a-name" placeholder="Uống nước" /></div>
            <div className="field"><span className="flabel">Mục tiêu / ngày</span>
              <input className="finput num" inputMode="decimal" value={adding.goal} onChange={(e) => setAdding({ ...adding, goal: e.target.value })} data-testid="a-goal" placeholder="8" /></div>
            <div className="field"><span className="flabel">Đơn vị</span>
              <input className="finput" value={adding.unit} onChange={(e) => setAdding({ ...adding, unit: e.target.value })} data-testid="a-unit" placeholder="ly" /></div>
            <div className="field"><span className="flabel">Emoji</span>
              <input className="finput" value={adding.emoji} onChange={(e) => setAdding({ ...adding, emoji: e.target.value })} data-testid="a-emoji" placeholder="💧" /></div>
            <div className="field"><span className="flabel">Màu</span>
              <input className="finput" type="color" value={adding.color} onChange={(e) => setAdding({ ...adding, color: e.target.value })} data-testid="a-color" /></div>

            {/* #75: habit-reminder nudge. Toggle on → time + cadence → sets the
                activity's remindAt/remindRepeat; the BE creates the reminder. */}
            <div className="field" style={{ gridColumn: "1 / 3" }}>
              <span className="flabel">Nhắc nhở (tùy chọn)</span>
              <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className={`tab${adding.remindOn ? " on" : ""}`}
                  onClick={() => setAdding({ ...adding, remindOn: !adding.remindOn })}
                  data-testid="a-remind-toggle"
                  aria-pressed={adding.remindOn}
                >
                  🔔 {adding.remindOn ? "Bật" : "Tắt"}
                </button>
                {adding.remindOn && (
                  <>
                    <input
                      className="finput num"
                      type="time"
                      style={{ width: 120 }}
                      value={adding.remindTime}
                      onChange={(e) => setAdding({ ...adding, remindTime: e.target.value })}
                      data-testid="a-remind-time"
                    />
                    <select
                      className="finput"
                      style={{ width: 150 }}
                      value={adding.remindRepeat}
                      onChange={(e) => setAdding({ ...adding, remindRepeat: e.target.value as RemindRepeat })}
                      data-testid="a-remind-repeat"
                    >
                      <option value="daily">Hằng ngày</option>
                      <option value="weekdays">Ngày thường (T2–T6)</option>
                    </select>
                  </>
                )}
              </div>
              {adding.remindOn && <span className="fhint">BE sẽ tạo một nhắc nhở "{adding.remindTime} {adding.remindRepeat === "daily" ? "hằng ngày" : "ngày thường"}" cho thói quen này.</span>}
            </div>

            {formErr && <span className="hint neg" style={{ gridColumn: "1 / 3" }} data-testid="add-error">{formErr}</span>}
            <div className="row" style={{ gap: 8, gridColumn: "1 / 3" }}>
              <button className="btn accent" type="submit" disabled={busy} data-testid="a-submit">{busy ? "Đang lưu…" : "Tạo hoạt động"}</button>
              <button className="btn" type="button" onClick={() => setAdding(null)} disabled={busy}>Hủy</button>
            </div>
          </form>
        </div>
      )}

      {/* Log-session form */}
      {logForm && (
        <div className="panel" data-testid="log-form">
          <div className="phead"><span className="kicker">Log · {logForm.name}</span></div>
          <form onSubmit={onLog} style={{ padding: "12px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <div className="field"><span className="flabel">Giá trị{logForm.unit ? ` (${logForm.unit})` : ""}</span>
              <input className="finput num" inputMode="decimal" value={logForm.val} onChange={(e) => setLogForm({ ...logForm, val: e.target.value })} data-testid="log-val" placeholder="3" autoFocus /></div>
            <div className="field"><span className="flabel">Thời lượng (phút, tùy chọn)</span>
              <input className="finput num" inputMode="numeric" value={logForm.durMin} onChange={(e) => setLogForm({ ...logForm, durMin: e.target.value })} data-testid="log-dur" placeholder="15" /></div>
            <div className="field" style={{ gridColumn: "1 / 3" }}><span className="flabel">Ghi chú (tùy chọn)</span>
              <input className="finput" value={logForm.note} onChange={(e) => setLogForm({ ...logForm, note: e.target.value })} data-testid="log-note" placeholder="sáng" /></div>
            {formErr && <span className="hint neg" style={{ gridColumn: "1 / 3" }} data-testid="log-error">{formErr}</span>}
            <div className="row" style={{ gap: 8, gridColumn: "1 / 3" }}>
              <button className="btn accent" type="submit" disabled={busy} data-testid="log-submit">{busy ? "Đang lưu…" : "Ghi session"}</button>
              <button className="btn" type="button" onClick={() => setLogForm(null)} disabled={busy}>Hủy</button>
            </div>
          </form>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="tracing-loading">Đang tải tracing…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="tracing-error">
          Không tải được tracing: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <>
          {rowErr && (
            <div className="panel" style={{ padding: "10px 14px" }}>
              <span className="hint neg" data-testid="row-error">⚠ {rowErr}</span>
            </div>
          )}

          {acts.length === 0 ? (
            <div className="panel" data-testid="tracing-empty">
              <div style={{ padding: "30px 18px", textAlign: "center" }}>
                <div className="hint" style={{ fontSize: 13 }}>Chưa có hoạt động nào.</div>
                <div className="hint faint" style={{ marginTop: 6 }}>
                  Thêm một hoạt động (vd: uống nước, tập thể dục, đọc sách) để bắt đầu theo dõi mỗi ngày.
                </div>
                <button className="btn accent" type="button" style={{ marginTop: 12 }} onClick={() => { setAdding({ ...EMPTY_ADD }); setFormErr(""); }} data-testid="empty-add">
                  + Thêm hoạt động đầu tiên
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Activity cards */}
              <div className="grid g-4" data-testid="activity-cards">
                {acts.map((a) => <ActivityCard key={a.id} a={a} onLog={() => { setLogForm({ id: a.id, name: a.name, unit: a.unit, val: "", durMin: "", note: "" }); setFormErr(""); }} onArchive={() => onArchive(a.id)} busy={busy} />)}
              </div>

              {/* Timeline + heatmap */}
              <div className="grid" style={{ gridTemplateColumns: "1fr 320px", gap: 14 }}>
                {/* today timeline (adapted: per-activity today rollup) */}
                <div className="panel" style={{ overflow: "hidden" }} data-testid="tracing-timeline">
                  <div className="phead">
                    <span className="kicker">Hôm nay</span>
                    <span className="hint" style={{ marginLeft: "auto" }}>{todayRows.length} hoạt động có session</span>
                  </div>
                  <div className="tl-list">
                    {todayRows.length === 0 ? (
                      <div style={{ padding: "26px", textAlign: "center" }}><span className="hint faint">Chưa có session nào hôm nay.</span></div>
                    ) : (
                      todayRows.map((a) => (
                        <div className="tl-row" key={a.id} data-testid={`tl-${a.id}`}>
                          <div className="tl-time" style={{ color: a.today.done ? a.color : "var(--tx-2)" }}>{a.today.pct}%</div>
                          <div className="tl-dot" style={{ background: a.color }} />
                          <div className="tl-body">
                            <span style={{ fontSize: 11, marginRight: 4 }}>{a.emoji}</span>
                            <b style={{ color: "var(--tx-0)", fontFamily: "var(--mono)", fontSize: 12 }}>{a.name}</b>
                            <span className="faint" style={{ fontSize: 11.5, marginLeft: 4 }}>· {a.today.val} {a.unit} · {a.today.dur} · {a.today.sessions} session</span>
                            {a.today.note && <div className="faint" style={{ fontSize: 11, marginTop: 2 }}>{a.today.note}</div>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>

                {/* heatmap */}
                <div className="panel" style={{ overflow: "hidden" }} data-testid="tracing-heatmap">
                  <div className="phead"><span className="kicker">Activity heatmap</span><span className="hint" style={{ marginLeft: "auto" }}>12 tuần qua</span></div>
                  <div style={{ padding: "10px 14px 14px" }}>
                    <div className="heatmap-wrap">
                      <div className="hm-days">{WEEK_DAYS.map((d) => <div className="hm-day" key={d}>{d}</div>)}</div>
                      <div className="hm-grid" data-testid="heatmap-grid" role="img" aria-label="Lịch sử 12 tuần — số hoạt động đạt mục tiêu mỗi ngày">
                        {data.heatmap12w.map((v, i) => (
                          <div className="hc" key={i} style={{ background: heatColor(v, heatMax) }} title={`${v} hoạt động đạt`} aria-label={`${v} hoạt động đạt`} data-testid={`hc-${i}`} data-count={v} />
                        ))}
                      </div>
                    </div>
                    <div className="hm-legend" aria-hidden="true">
                      <span className="faint">Ít</span>
                      {[0, 1, 2, 3, 4].map((v) => <div className="hc" key={v} style={{ background: heatColor(v, 4) }} />)}
                      <span className="faint">Nhiều</span>
                    </div>
                    <div className="hm-acts" style={{ marginTop: 14 }}>
                      {acts.map((a) => (
                        <div className="hma-row" key={a.id}>
                          <span style={{ fontSize: 11 }}>{a.emoji}</span>
                          <span style={{ fontSize: 12, flex: 1 }}>{a.name}</span>
                          <span className="num" style={{ fontSize: 11.5, color: a.color }}>{a.streak}d streak {streakBadge(a.streak)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}

/** ApiError message + hint (hint shown when present — #46/#70 agent-error). */
function errText(err: unknown): string {
  if (err instanceof ApiError) {
    return err.hint ? `${err.message} (${err.hint})` : err.message;
  }
  return (err as Error).message;
}

/** One activity card — ported from mock actCard (streak badge, today, bar, week bars). */
function ActivityCard({ a, onLog, onArchive, busy }: { a: ActivityView; onLog: () => void; onArchive: () => void; busy: boolean }) {
  const done = a.today.done;
  const barW = Math.min(100, a.today.pct);
  const badge = streakBadge(a.streak);
  return (
    <div className={`act-card${done ? "" : " pending"}`} data-act={a.id} data-testid={`act-${a.id}`} data-done={done}>
      <div className="ac-head">
        <div className="ac-emoji">{a.emoji || "•"}</div>
        <div className="ac-meta">
          <div className="ac-name">{a.name}</div>
          <div className="ac-goal faint">target <span className="num">{a.goal} {a.unit}</span> / ngày</div>
          {/* #75: show the habit's reminder when set (defensive — field absent pre-#75-BE). */}
          {a.remindAt && a.remindRepeat && a.remindRepeat !== "off" && (
            <div className="ac-goal acc" data-testid={`remind-${a.id}`} title="Nhắc nhở từ thói quen này">
              🔔 <span className="num">{a.remindAt}</span> {a.remindRepeat === "daily" ? "hằng ngày" : "ngày thường"}
            </div>
          )}
        </div>
        <div className="ac-streak" title={`Streak: ${a.streak} ngày liên tiếp`} data-testid={`streak-${a.id}`}>
          <span className="num" style={{ fontSize: 20, color: a.color }}>{a.streak}</span>
          <span className="faint" style={{ fontSize: 9, display: "block", textAlign: "center" }} data-testid={`badge-${a.id}`}>ngày {badge}</span>
        </div>
      </div>
      <div className="ac-today">
        <span className="num" style={{ fontSize: 18, fontWeight: 700, color: done ? a.color : "var(--tx-2)" }}>
          {a.today.val} {a.unit}
        </span>
        <span className="faint" style={{ fontSize: 11 }}>{a.today.pct}% · {a.today.dur}</span>
      </div>
      <div className="bar" style={{ marginTop: 8, height: 5 }}>
        <i style={{ width: `${barW}%`, background: done ? a.color : "var(--tx-2)", boxShadow: done ? `0 0 8px -2px ${a.color}` : undefined }} />
      </div>
      {a.today.note && (
        <div className="faint" style={{ fontSize: 11, marginTop: 5, fontFamily: "var(--mono)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.today.note}</div>
      )}
      <div className="ac-week" data-testid={`week-${a.id}`}>
        {a.week.map((v, i) => {
          const pct = Math.min(100, Math.round((v / (a.goal || 1)) * 100));
          const isToday = i === 6; // index 6 = today (Mon→Sun)
          return (
            <div className="ac-wbar" key={i}>
              <div className="ac-wbar-fill" style={{ height: `${Math.max(4, pct)}%`, background: pct >= 100 ? a.color : "var(--bg-3)", outline: isToday ? `1px solid ${a.color}` : undefined }} />
              <div className={`ac-wday${isToday ? " today" : ""}`}>{WEEK_DAYS[i]}</div>
            </div>
          );
        })}
      </div>
      <div className="row ac-logbtn" style={{ gap: 7 }}>
        <button className="btn sm accent" type="button" onClick={onLog} disabled={busy} data-testid={`log-${a.id}`}>+ Log</button>
        <button className="btn sm ghost" type="button" onClick={onArchive} disabled={busy} data-testid={`archive-${a.id}`} title="Lưu trữ">✕</button>
      </div>
    </div>
  );
}
