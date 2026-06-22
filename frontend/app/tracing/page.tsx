"use client";
/* ============================================================
   /daily-tracing (#65-P3 · S14 · G-HABIT → #122 TRACING-UX2 redesign)

   USER-CHỐT 2-column redesign — track daily todos → notice/nudge if not ticked. SIMPLE:
   text + action + optional-remind. The old chip-row / emoji / color / goal / heavy
   multi-field form / template-picker are INTENTIONALLY DROPPED (user rejected them).

   • LEFT  — Hoạt động (todos): add-via-text (type → Enter → adds an activity), each
     todo = text + a tick checkbox + an optional inline 🔔-remind (time + repeat +
     #111 channel). A "todo" is an activity with a hidden goal=1; ticking = logging one
     completing session (val=1) → today.done flips (verified live). RENDER-ONLY: done/
     streak from the backend.
   • RIGHT — Note (day-note, #121): a text card + optional 🔔-remind. Wired to
     GET/POST/PUT/DELETE /tracing/notes. A note WITH a remind links a reminder (BE-side).
   • Streak + heatmap KEPT but SMALL / collapsed (a <details>, not the focus).

   RENDER-ONLY: the backend computes everything (done/streak/heatmap/score); the FE
   displays + POSTs raw todos/sessions/notes. Errors = the #46/#70 {error:{code,message,
   hint}} shape — message + hint shown.
   ============================================================ */
import { useEffect, useMemo, useState } from "react";
import { useTracing } from "@/lib/useTracing";
import { useTracingNotes } from "@/lib/useTracingNotes";
import { apiBase, ApiError, getReminderChannels } from "@/lib/api";
import { slugifyVi } from "@/lib/format";
import type {
  ActivityView, ActivityInput, TracingNote, TracingNoteInput,
  RemindRepeat, RemindChannel, ReminderChannelOption,
} from "@/lib/types";

const WEEK_DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]; // Mon→Sun

/** streak badge thresholds — ported EXACTLY from mock screens-active.js:80. */
function streakBadge(streak: number): string {
  return streak >= 7 ? "🔥" : streak >= 3 ? "✦" : "";
}

/** heatmap cell color by per-day COUNT (0 = empty; band by count/max). */
function heatColor(count: number, max: number): string {
  if (count <= 0) return "var(--bg-3)";
  const denom = Math.max(1, max);
  const a = 0.18 + 0.82 * Math.min(1, count / denom);
  return `color-mix(in oklch, var(--accent) ${Math.round(a * 100)}%, var(--bg-3))`;
}

/** ApiError message + hint (hint shown when present — #46/#70 agent-error). */
function errText(err: unknown): string {
  if (err instanceof ApiError) return err.hint ? `${err.message} (${err.hint})` : err.message;
  return (err as Error).message;
}

/** a small, reusable inline 🔔-remind control: a toggle + (when on) time + repeat +
 *  #111 channel. Used by BOTH the todo-add row and the note card. Controlled. */
type RemindState = { on: boolean; time: string; repeat: RemindRepeat; channel: RemindChannel };
const EMPTY_REMIND: RemindState = { on: false, time: "07:00", repeat: "daily", channel: "in_app" };

function RemindControls({
  value, onChange, channels, idPrefix,
}: {
  value: RemindState;
  onChange: (next: RemindState) => void;
  channels: ReminderChannelOption[];
  idPrefix: string;
}) {
  return (
    <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <button
        type="button"
        className={`tab${value.on ? " on" : ""}`}
        onClick={() => onChange({ ...value, on: !value.on })}
        data-testid={`${idPrefix}-remind-toggle`}
        aria-pressed={value.on}
      >
        🔔 {value.on ? "Bật" : "Nhắc nhở"}
      </button>
      {value.on && (
        <>
          <input
            className="finput num" type="time" style={{ width: 110 }}
            value={value.time}
            onChange={(e) => onChange({ ...value, time: e.target.value })}
            data-testid={`${idPrefix}-remind-time`}
            aria-label="Giờ nhắc"
          />
          <select
            className="finput" style={{ width: 140 }}
            value={value.repeat}
            onChange={(e) => onChange({ ...value, repeat: e.target.value as RemindRepeat })}
            data-testid={`${idPrefix}-remind-repeat`}
            aria-label="Lặp lại"
          >
            <option value="daily">Hằng ngày</option>
            <option value="weekdays">Ngày thường (T2–T6)</option>
          </select>
          <select
            className="finput" style={{ width: 130 }}
            value={value.channel}
            onChange={(e) => onChange({ ...value, channel: e.target.value as RemindChannel })}
            data-testid={`${idPrefix}-remind-channel`}
            aria-label="Kênh nhắc nhở"
          >
            {channels.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.available} data-testid={`${idPrefix}-channel-opt-${c.id}`}>
                {c.label}{c.available ? "" : " (chưa cấu hình)"}
              </option>
            ))}
          </select>
        </>
      )}
    </div>
  );
}

/** a compact remind chip shown on a todo/note that has a remind set. */
function RemindChip({ at, repeat, testid }: { at: string; repeat: RemindRepeat; testid: string }) {
  return (
    <span className="tagchip acc" data-testid={testid} title="Nhắc nhở">
      🔔 <span className="num">{at}</span> {repeat === "daily" ? "hằng ngày" : repeat === "weekdays" ? "ngày thường" : ""}
    </span>
  );
}

export default function TracingPage() {
  const { data, status, errMsg, warning, reload, log, add, archive } = useTracing();
  const notesApi = useTracingNotes();

  // #111 — reminder channels (in_app/email/discord). Fetched once; render-safe fallback.
  const IN_APP_ONLY: ReminderChannelOption[] = [{ id: "in_app", label: "In-app", available: true }];
  const [channels, setChannels] = useState<ReminderChannelOption[]>(IN_APP_ONLY);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getReminderChannels();
        if (!alive) return;
        const list = res?.data?.channels;
        if (Array.isArray(list) && list.length > 0) setChannels(list);
      } catch { /* fallback already = in_app-only */ }
    })();
    return () => { alive = false; };
  }, []);

  // ---- LEFT: add-a-todo (text + optional remind) ----
  const [todoText, setTodoText] = useState("");
  const [todoRemind, setTodoRemind] = useState<RemindState>({ ...EMPTY_REMIND });
  const [addBusy, setAddBusy] = useState(false);
  const [addErr, setAddErr] = useState("");
  const [rowErr, setRowErr] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  // ---- RIGHT: add-a-note (text + optional remind) ----
  const [noteText, setNoteText] = useState("");
  const [noteRemind, setNoteRemind] = useState<RemindState>({ ...EMPTY_REMIND });
  const [noteBusy, setNoteBusy] = useState(false);
  const [noteErr, setNoteErr] = useState("");
  const [noteRowErr, setNoteRowErr] = useState("");
  const [noteBusyId, setNoteBusyId] = useState<string | null>(null);

  const acts = data.activities ?? [];
  const sc = data.score;
  const heatMax = useMemo(() => Math.max(sc.total, ...data.heatmap12w), [data.heatmap12w, sc.total]);

  async function onAddTodo(e: React.FormEvent) {
    e.preventDefault();
    setAddErr("");
    const text = todoText.trim();
    if (!text) { setAddErr("Nhập nội dung việc cần làm."); return; }
    const id = slugifyVi(text);
    if (!id) { setAddErr("Nội dung không tạo được id — thử chữ có dấu cách / chữ cái."); return; }
    // a "todo" = an activity with a hidden goal=1 (tick = log one completing session).
    const body: ActivityInput = {
      id, name: text, goal: 1,
      remindAt: todoRemind.on ? todoRemind.time : null,
      remindRepeat: todoRemind.on ? todoRemind.repeat : "off",
      remindChannel: todoRemind.on ? todoRemind.channel : undefined,
    };
    setAddBusy(true);
    try {
      await add(body);
      setTodoText("");
      setTodoRemind({ ...EMPTY_REMIND });
    } catch (err) {
      setAddErr(errText(err));
    } finally {
      setAddBusy(false);
    }
  }

  // tick a todo = log one completing session (val=1 ≥ goal=1 → today.done flips).
  async function onTickTodo(a: ActivityView) {
    if (a.today.done) return; // already done — no un-tick (sessions are append-only)
    setRowErr(""); setBusyId(a.id);
    try {
      await log(a.id, { val: 1, dur_min: null, note: null });
    } catch (err) {
      setRowErr(errText(err));
    } finally {
      setBusyId(null);
    }
  }

  async function onArchiveTodo(id: string) {
    setRowErr(""); setBusyId(id);
    try {
      await archive(id);
    } catch (err) {
      setRowErr(errText(err));
    } finally {
      setBusyId(null);
    }
  }

  async function onAddNote(e: React.FormEvent) {
    e.preventDefault();
    setNoteErr("");
    const text = noteText.trim();
    if (!text) { setNoteErr("Nhập nội dung ghi chú."); return; }
    const body: TracingNoteInput = {
      text,
      remindAt: noteRemind.on ? noteRemind.time : null,
      remindRepeat: noteRemind.on ? noteRemind.repeat : "off",
      remindChannel: noteRemind.on ? noteRemind.channel : undefined,
    };
    setNoteBusy(true);
    try {
      await notesApi.create(body);
      setNoteText("");
      setNoteRemind({ ...EMPTY_REMIND });
    } catch (err) {
      setNoteErr(errText(err));
    } finally {
      setNoteBusy(false);
    }
  }

  async function onDeleteNote(n: TracingNote) {
    setNoteRowErr(""); setNoteBusyId(n.id);
    try {
      await notesApi.remove(n.id);
    } catch (err) {
      setNoteRowErr(errText(err));
    } finally {
      setNoteBusyId(null);
    }
  }

  return (
    <section className="view" data-screen="S14" data-testid="tracing-screen">
      <div className="vtitle">
        <h1>Daily Tracing</h1>
        <span className="sub">
          {data.date || "—"} · {sc.done}/{sc.total} việc xong{sc.timeActive ? ` · ${sc.timeActive} active` : ""}
        </span>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="tracing-warning">
          <span className="hint mid">⚠ {warning}</span>
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
          {/* ===== 2-COLUMN: todos (left) | note (right) ===== */}
          <div className="grid tracing-2col" style={{ gridTemplateColumns: "1fr 1fr", gap: 14, alignItems: "start" }} data-testid="tracing-2col">

            {/* ---------- LEFT — Hoạt động (todos) ---------- */}
            <div className="panel" data-testid="tracing-todos" style={{ overflow: "hidden" }}>
              <div className="phead">
                <span className="kicker">Hoạt động hôm nay</span>
                <span className="hint" style={{ marginLeft: "auto" }}>{sc.done}/{sc.total} xong</span>
              </div>

              {/* add-via-text row */}
              <form onSubmit={onAddTodo} style={{ padding: "12px 16px 6px", display: "flex", flexDirection: "column", gap: 8 }} data-testid="todo-add-form">
                <div className="row" style={{ gap: 8 }}>
                  <input
                    className="finput"
                    style={{ flex: 1 }}
                    value={todoText}
                    onChange={(e) => setTodoText(e.target.value)}
                    placeholder="Thêm việc cần làm hôm nay…"
                    data-testid="todo-input"
                    aria-label="Việc cần làm"
                  />
                  <button className="btn accent" type="submit" disabled={addBusy} data-testid="todo-submit">
                    {addBusy ? "…" : "Thêm"}
                  </button>
                </div>
                <RemindControls value={todoRemind} onChange={setTodoRemind} channels={channels} idPrefix="todo" />
                {addErr && <span className="hint neg" data-testid="todo-add-error">{addErr}</span>}
              </form>

              {rowErr && <div style={{ padding: "0 16px" }}><span className="hint neg" data-testid="todo-row-error">⚠ {rowErr}</span></div>}

              {/* todo list */}
              <div className="tl-list" style={{ padding: "6px 8px 10px" }}>
                {acts.length === 0 ? (
                  <div style={{ padding: "22px 12px", textAlign: "center" }} data-testid="todos-empty">
                    <div className="hint" style={{ fontSize: 13 }}>Chưa có việc nào hôm nay.</div>
                    <div className="hint faint" style={{ marginTop: 4 }}>Gõ ở trên + Enter để thêm việc đầu tiên.</div>
                  </div>
                ) : (
                  acts.map((a) => (
                    <div className="todo-row" key={a.id} data-testid={`todo-${a.id}`} data-done={a.today.done}
                      style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 8px", borderBottom: "1px solid var(--bg-2)" }}>
                      <button
                        type="button"
                        className={`todo-tick${a.today.done ? " on" : ""}`}
                        onClick={() => onTickTodo(a)}
                        disabled={busyId === a.id || a.today.done}
                        data-testid={`tick-${a.id}`}
                        aria-pressed={a.today.done}
                        aria-label={a.today.done ? "Đã xong" : "Đánh dấu xong"}
                        title={a.today.done ? "Đã xong hôm nay" : "Đánh dấu xong"}
                        style={{
                          width: 20, height: 20, borderRadius: 5, flexShrink: 0, cursor: a.today.done ? "default" : "pointer",
                          border: `1.5px solid ${a.today.done ? "var(--green)" : "var(--tx-2)"}`,
                          background: a.today.done ? "var(--green)" : "transparent",
                          color: "var(--bg-0)", fontSize: 12, lineHeight: 1, fontWeight: 700,
                        }}
                      >
                        {a.today.done ? "✓" : ""}
                      </button>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <span data-testid={`todo-text-${a.id}`} style={{
                          fontSize: 13, color: a.today.done ? "var(--tx-2)" : "var(--tx-0)",
                          textDecoration: a.today.done ? "line-through" : "none",
                        }}>{a.name}</span>
                        <div className="row" style={{ gap: 6, marginTop: 3, alignItems: "center", flexWrap: "wrap" }}>
                          {a.streak > 0 && (
                            <span className="num faint" style={{ fontSize: 10.5 }} data-testid={`todo-streak-${a.id}`}>
                              {a.streak}d {streakBadge(a.streak)}
                            </span>
                          )}
                          {a.remindAt && a.remindRepeat && a.remindRepeat !== "off" && (
                            <RemindChip at={a.remindAt} repeat={a.remindRepeat} testid={`todo-remind-${a.id}`} />
                          )}
                        </div>
                      </div>
                      <button className="btn sm ghost" type="button" onClick={() => onArchiveTodo(a.id)}
                        disabled={busyId === a.id} data-testid={`todo-archive-${a.id}`} title="Xóa khỏi danh sách">✕</button>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* ---------- RIGHT — Note (day-note) ---------- */}
            <div className="panel" data-testid="tracing-notes" style={{ overflow: "hidden" }}>
              <div className="phead">
                <span className="kicker">Ghi chú trong ngày</span>
                <span className="hint" style={{ marginLeft: "auto" }}>{notesApi.notes.length} ghi chú</span>
              </div>

              {/* add-a-note */}
              <form onSubmit={onAddNote} style={{ padding: "12px 16px 6px", display: "flex", flexDirection: "column", gap: 8 }} data-testid="note-add-form">
                <textarea
                  className="finput"
                  rows={2}
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Ghi lại điều cần nhớ / một suy nghĩ trong ngày…"
                  data-testid="note-input"
                  aria-label="Nội dung ghi chú"
                  style={{ resize: "vertical" }}
                />
                <RemindControls value={noteRemind} onChange={setNoteRemind} channels={channels} idPrefix="note" />
                <div className="row" style={{ gap: 8 }}>
                  <button className="btn accent" type="submit" disabled={noteBusy} data-testid="note-submit">
                    {noteBusy ? "Đang lưu…" : "Lưu ghi chú"}
                  </button>
                </div>
                {noteErr && <span className="hint neg" data-testid="note-add-error">{noteErr}</span>}
              </form>

              {noteRowErr && <div style={{ padding: "0 16px" }}><span className="hint neg" data-testid="note-row-error">⚠ {noteRowErr}</span></div>}
              {notesApi.status === "error" && (
                <div style={{ padding: "0 16px 8px" }}><span className="hint neg" data-testid="notes-load-error">Không tải được ghi chú: {notesApi.errMsg}.</span></div>
              )}

              {/* note list */}
              <div className="tl-list" style={{ padding: "6px 8px 10px" }}>
                {notesApi.notes.length === 0 ? (
                  <div style={{ padding: "22px 12px", textAlign: "center" }} data-testid="notes-empty">
                    <div className="hint faint" style={{ fontSize: 12.5 }}>Chưa có ghi chú nào.</div>
                  </div>
                ) : (
                  notesApi.notes.map((n) => (
                    <div className="note-row" key={n.id} data-testid={`note-${n.id}`}
                      style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "9px 8px", borderBottom: "1px solid var(--bg-2)" }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div data-testid={`note-text-${n.id}`} style={{ fontSize: 13, color: "var(--tx-0)", whiteSpace: "pre-wrap" }}>{n.text}</div>
                        {n.remindAt && n.remindRepeat !== "off" && (
                          <div style={{ marginTop: 4 }}>
                            <RemindChip at={n.remindAt} repeat={n.remindRepeat} testid={`note-remind-${n.id}`} />
                          </div>
                        )}
                      </div>
                      <button className="btn sm ghost" type="button" onClick={() => onDeleteNote(n)}
                        disabled={noteBusyId === n.id} data-testid={`note-delete-${n.id}`} title="Xóa ghi chú">✕</button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* ===== streak + heatmap — KEPT but SMALL / collapsed (not the focus) ===== */}
          <details className="panel" data-testid="tracing-stats" style={{ marginTop: 14 }}>
            <summary className="phead" style={{ cursor: "pointer", listStyle: "revert" }} data-testid="tracing-stats-summary">
              <span className="kicker">Streak &amp; lịch sử 12 tuần</span>
              <span className="hint" style={{ marginLeft: "auto" }}>streak tốt nhất {sc.topStreak}d · mở để xem</span>
            </summary>
            <div style={{ padding: "12px 16px 16px" }}>
              {/* compact streak list */}
              {acts.length > 0 && (
                <div className="hm-acts" data-testid="streak-list" style={{ marginBottom: 14 }}>
                  {acts.map((a) => (
                    <div className="hma-row" key={a.id} data-testid={`streak-${a.id}`}>
                      <span style={{ fontSize: 12, flex: 1 }}>{a.name}</span>
                      <span className="num" style={{ fontSize: 11.5, color: "var(--accent)" }}>{a.streak}d streak {streakBadge(a.streak)}</span>
                    </div>
                  ))}
                </div>
              )}
              {/* 12-week heatmap */}
              <div className="heatmap-wrap">
                <div className="hm-days">{WEEK_DAYS.map((d) => <div className="hm-day" key={d}>{d}</div>)}</div>
                <div className="hm-grid" data-testid="heatmap-grid" role="img" aria-label="Lịch sử 12 tuần — số việc xong mỗi ngày">
                  {data.heatmap12w.map((v, i) => (
                    <div className="hc" key={i} style={{ background: heatColor(v, heatMax) }} title={`${v} việc xong`} aria-label={`${v} việc xong`} data-testid={`hc-${i}`} data-count={v} />
                  ))}
                </div>
              </div>
              <div className="hm-legend" aria-hidden="true">
                <span className="faint">Ít</span>
                {[0, 1, 2, 3, 4].map((v) => <div className="hc" key={v} style={{ background: heatColor(v, 4) }} />)}
                <span className="faint">Nhiều</span>
              </div>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
