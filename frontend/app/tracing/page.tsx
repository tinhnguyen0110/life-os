"use client";
/* ============================================================
   /daily-tracing (#65-P3 · S14 · G-HABIT → #122 → #126 TRACING-UX2 timeline redesign)

   #126 user-CHỐT — REVISES the #122 VIEW (the base model STAYS):
   • base (KEPT): a todo = an activity with hidden goal=1; tick = log one completing
     session (val=1) → today.done flips. note → #121 /tracing/notes. #111 channels.
     streak + heatmap KEPT (collapsed). NO BE change.
   • 🔴 DEFAULT = a TIMELINE read-view — a vertical time-rail: rows = giờ · color-dot ·
     việc · chi tiết. Activities placed BY TIME (their remindAt); un-timed todos group in
     a "Cả ngày" (anytime) bucket. Read-only + 1-click tick (ticking is NOT gated behind
     edit — it's the core daily action).
   • EDIT-mode toggle ("Sửa"/"Xong") → reveals add-via-text, archive, the remind controls,
     and the "+ Từ mẫu" template picker (#124).
   • NOTE = a MULTI-LIST (not a single textarea): multiple note cards, add-multiple,
     per-note 🔔-remind (#111) + per-note delete (#121 store is already a list).

   RENDER-ONLY: the backend computes everything (done/streak/heatmap/time). Errors = the
   #46/#70 {error:{code,message,hint}} shape.
   ============================================================ */
import { useEffect, useMemo, useState } from "react";
import { useTracing } from "@/lib/useTracing";
import { useTracingNotes } from "@/lib/useTracingNotes";
import {
  apiBase, ApiError, getReminderChannels,
  getTracingTemplates, addTemplateToToday, addAllTemplates,
} from "@/lib/api";
import { slugifyVi } from "@/lib/format";
import type {
  ActivityView, ActivityInput, TracingNote, TracingNoteInput,
  RemindRepeat, RemindChannel, ReminderChannelOption, TracingTemplate,
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

/** a reusable inline 🔔-remind control: a toggle + (when on) time + repeat/date + #111
 *  channel. Used by the todo-add row (recurring-only) and each note card (allowOnce →
 *  also a #125 ONE-SHOT future-date kind). Controlled.
 *  - kind="recurring": time + repeat(daily/weekdays) → remindAt + remindRepeat.
 *  - kind="once" (notes only): a future DATE + time → remindDate + remindAt (BE makes a
 *    repeat="once" reminder). */
type RemindKind = "recurring" | "once";
type RemindState = { on: boolean; kind: RemindKind; time: string; repeat: RemindRepeat; date: string; channel: RemindChannel };
const EMPTY_REMIND: RemindState = { on: false, kind: "recurring", time: "07:00", repeat: "daily", date: "", channel: "in_app" };

/** today (VN) as YYYY-MM-DD — the client-side min for the one-shot date picker (the BE
 *  also 422s a past date; this is just a friendly guard). */
function todayVnDate(): string {
  // toISOString is UTC; for the date-input min a UTC date is close enough (the BE is the
  // authority on "past" in VN time — it 422s, we surface the hint).
  return new Date().toISOString().slice(0, 10);
}

function RemindControls({ value, onChange, channels, idPrefix, allowOnce = false }: {
  value: RemindState; onChange: (next: RemindState) => void; channels: ReminderChannelOption[]; idPrefix: string;
  allowOnce?: boolean;
}) {
  return (
    <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <button type="button" className={`tab${value.on ? " on" : ""}`} onClick={() => onChange({ ...value, on: !value.on })}
        data-testid={`${idPrefix}-remind-toggle`} aria-pressed={value.on}>
        🔔 {value.on ? "Bật" : "Nhắc nhở"}
      </button>
      {value.on && (
        <>
          {/* #125 — note-only: a "Một lần" (one-shot future date) vs "Lặp lại" (recurring) segment */}
          {allowOnce && (
            <div className="seg" data-testid={`${idPrefix}-remind-kind`}>
              <button type="button" className={value.kind === "recurring" ? "on" : ""} data-testid={`${idPrefix}-kind-recurring`}
                onClick={() => onChange({ ...value, kind: "recurring" })} aria-pressed={value.kind === "recurring"}>Lặp lại</button>
              <button type="button" className={value.kind === "once" ? "on" : ""} data-testid={`${idPrefix}-kind-once`}
                onClick={() => onChange({ ...value, kind: "once", date: value.date || todayVnDate() })} aria-pressed={value.kind === "once"}>Một lần</button>
            </div>
          )}
          {/* one-shot: a future DATE; recurring: a repeat select */}
          {allowOnce && value.kind === "once" ? (
            <input className="finput num" type="date" style={{ width: 150 }} value={value.date} min={todayVnDate()}
              onChange={(e) => onChange({ ...value, date: e.target.value })} data-testid={`${idPrefix}-remind-date`} aria-label="Ngày nhắc" />
          ) : (
            <select className="finput" style={{ width: 140 }} value={value.repeat}
              onChange={(e) => onChange({ ...value, repeat: e.target.value as RemindRepeat })} data-testid={`${idPrefix}-remind-repeat`} aria-label="Lặp lại">
              <option value="daily">Hằng ngày</option>
              <option value="weekdays">Ngày thường (T2–T6)</option>
            </select>
          )}
          <input className="finput num" type="time" style={{ width: 110 }} value={value.time}
            onChange={(e) => onChange({ ...value, time: e.target.value })} data-testid={`${idPrefix}-remind-time`} aria-label="Giờ nhắc" />
          <select className="finput" style={{ width: 130 }} value={value.channel}
            onChange={(e) => onChange({ ...value, channel: e.target.value as RemindChannel })} data-testid={`${idPrefix}-remind-channel`} aria-label="Kênh nhắc nhở">
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

/** a compact remind chip shown on a timed todo/note. #125: when `date` is set it's a
 *  ONE-SHOT (date @ time); otherwise it's the recurring (repeat) chip. */
function RemindChip({ at, repeat, date, testid }: { at: string; repeat: RemindRepeat; date?: string | null; testid: string }) {
  return (
    <span className="tagchip acc" data-testid={testid} title={date ? "Nhắc một lần" : "Nhắc nhở"}>
      🔔 {date ? (
        <><span className="num">{date}</span> lúc <span className="num">{at}</span></>
      ) : (
        <><span className="num">{at}</span> {repeat === "daily" ? "hằng ngày" : repeat === "weekdays" ? "ngày thường" : ""}</>
      )}
    </span>
  );
}

/** Order activities for the timeline rail: TIMED (remindAt set) ascending by time first,
 *  then UN-TIMED (anytime) in their given order. Pure. */
function timelineOrder(acts: ActivityView[]): { timed: ActivityView[]; anytime: ActivityView[] } {
  const timed = acts.filter((a) => !!a.remindAt).slice().sort((a, b) => (a.remindAt! < b.remindAt! ? -1 : a.remindAt! > b.remindAt! ? 1 : 0));
  const anytime = acts.filter((a) => !a.remindAt);
  return { timed, anytime };
}

export default function TracingPage() {
  const { data, status, errMsg, warning, reload, log, add, archive } = useTracing();
  const notesApi = useTracingNotes();

  // #126 — edit-mode (default = read-only timeline). Toggling reveals the add/edit affordances.
  const [editMode, setEditMode] = useState(false);

  // #111 — reminder channels; fetched once; render-safe fallback.
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

  // ---- add-a-todo (edit-mode) ----
  const [todoText, setTodoText] = useState("");
  const [todoRemind, setTodoRemind] = useState<RemindState>({ ...EMPTY_REMIND });
  const [addBusy, setAddBusy] = useState(false);
  const [addErr, setAddErr] = useState("");
  const [rowErr, setRowErr] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  // ---- "+ Từ mẫu" template picker (#124, edit-mode) ----
  const [tplOpen, setTplOpen] = useState(false);
  const [templates, setTemplates] = useState<TracingTemplate[]>([]);
  const [tplStatus, setTplStatus] = useState<"idle" | "loading" | "error">("idle");
  const [tplBusy, setTplBusy] = useState<string | null>(null); // template id or "__all__"
  const [tplErr, setTplErr] = useState("");

  // ---- add-a-note (multi-list) ----
  const [noteText, setNoteText] = useState("");
  const [noteRemind, setNoteRemind] = useState<RemindState>({ ...EMPTY_REMIND });
  const [noteBusy, setNoteBusy] = useState(false);
  const [noteErr, setNoteErr] = useState("");
  const [noteRowErr, setNoteRowErr] = useState("");
  const [noteBusyId, setNoteBusyId] = useState<string | null>(null);

  const acts = data.activities ?? [];
  const sc = data.score;
  const heatMax = useMemo(() => Math.max(sc.total, ...data.heatmap12w), [data.heatmap12w, sc.total]);
  const { timed, anytime } = useMemo(() => timelineOrder(acts), [acts]);

  async function loadTemplates() {
    setTplStatus("loading"); setTplErr("");
    try {
      const res = await getTracingTemplates();
      setTemplates(res.data.templates ?? []);
      setTplStatus("idle");
    } catch (err) {
      setTplErr(errText(err)); setTplStatus("error");
    }
  }
  function openTemplates() {
    setTplOpen((o) => {
      const next = !o;
      if (next && templates.length === 0 && tplStatus !== "loading") void loadTemplates();
      return next;
    });
  }
  async function onAddTemplate(t: TracingTemplate) {
    setTplErr(""); setTplBusy(t.id);
    try {
      await addTemplateToToday(t.id); // {activity, added} — idempotent (added=false = already there)
      reload();
    } catch (err) {
      setTplErr(errText(err));
    } finally { setTplBusy(null); }
  }
  async function onAddAllTemplates() {
    setTplErr(""); setTplBusy("__all__");
    try {
      await addAllTemplates(); // {created, skipped}
      reload();
    } catch (err) {
      setTplErr(errText(err));
    } finally { setTplBusy(null); }
  }

  async function onAddTodo(e: React.FormEvent) {
    e.preventDefault();
    setAddErr("");
    const text = todoText.trim();
    if (!text) { setAddErr("Nhập nội dung việc cần làm."); return; }
    const id = slugifyVi(text);
    if (!id) { setAddErr("Nội dung không tạo được id — thử chữ có dấu cách / chữ cái."); return; }
    const body: ActivityInput = {
      id, name: text, goal: 1,
      remindAt: todoRemind.on ? todoRemind.time : null,
      remindRepeat: todoRemind.on ? todoRemind.repeat : "off",
      remindChannel: todoRemind.on ? todoRemind.channel : undefined,
    };
    setAddBusy(true);
    try {
      await add(body);
      setTodoText(""); setTodoRemind({ ...EMPTY_REMIND });
    } catch (err) { setAddErr(errText(err)); } finally { setAddBusy(false); }
  }

  // tick = log one completing session (val=1 ≥ goal=1). 1-click, works in READ mode.
  async function onTickTodo(a: ActivityView) {
    if (a.today.done) return; // append-only; no un-tick
    setRowErr(""); setBusyId(a.id);
    try {
      await log(a.id, { val: 1, dur_min: null, note: null });
    } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
  }

  async function onArchiveTodo(id: string) {
    setRowErr(""); setBusyId(id);
    try { await archive(id); } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
  }

  async function onAddNote(e: React.FormEvent) {
    e.preventDefault();
    setNoteErr("");
    const text = noteText.trim();
    if (!text) { setNoteErr("Nhập nội dung ghi chú."); return; }
    // #125 — two remind kinds: one-shot (a future DATE + time → remindDate) vs recurring
    // (time + repeat → remindRepeat). Off → no reminder at all.
    const isOnce = noteRemind.on && noteRemind.kind === "once";
    if (isOnce && !noteRemind.date) { setNoteErr("Chọn ngày cho nhắc một lần."); return; }
    const body: TracingNoteInput = {
      text,
      remindAt: noteRemind.on ? noteRemind.time : null,
      // one-shot → remindDate set, remindRepeat "off" (BE makes a repeat="once" reminder).
      remindDate: isOnce ? noteRemind.date : null,
      remindRepeat: noteRemind.on && !isOnce ? noteRemind.repeat : "off",
      remindChannel: noteRemind.on ? noteRemind.channel : undefined,
    };
    setNoteBusy(true);
    try {
      await notesApi.create(body); // a PAST remindDate → BE 422 (note_remind_in_past) → errText shows the hint
      setNoteText(""); setNoteRemind({ ...EMPTY_REMIND }); // cleared → add-multiple
    } catch (err) { setNoteErr(errText(err)); } finally { setNoteBusy(false); }
  }

  async function onDeleteNote(n: TracingNote) {
    setNoteRowErr(""); setNoteBusyId(n.id);
    try { await notesApi.remove(n.id); } catch (err) { setNoteRowErr(errText(err)); } finally { setNoteBusyId(null); }
  }

  /** one timeline row — giờ · dot · việc (tick + name) · chi tiết. */
  function TimelineRow({ a }: { a: ActivityView }) {
    return (
      <div className="tlx-row" data-testid={`tl-${a.id}`} data-done={a.today.done}
        style={{ display: "grid", gridTemplateColumns: "54px 16px 1fr auto", alignItems: "center", gap: 10, padding: "9px 6px", borderBottom: "1px solid var(--bg-2)" }}>
        {/* giờ */}
        <span className="num faint" data-testid={`tl-time-${a.id}`} style={{ fontSize: 12, textAlign: "right" }}>
          {a.remindAt ?? "—"}
        </span>
        {/* color-dot */}
        <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: "50%", background: a.today.done ? "var(--green)" : (a.color || "var(--tx-2)"), justifySelf: "center", boxShadow: a.today.done ? "0 0 6px -1px var(--green)" : undefined }} />
        {/* việc — 1-click tick + name */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
          <button type="button" className={`todo-tick${a.today.done ? " on" : ""}`} onClick={() => onTickTodo(a)}
            disabled={busyId === a.id || a.today.done} data-testid={`tick-${a.id}`} aria-pressed={a.today.done}
            aria-label={a.today.done ? "Đã xong" : "Đánh dấu xong"} title={a.today.done ? "Đã xong hôm nay" : "Đánh dấu xong"}
            style={{ width: 20, height: 20, borderRadius: 5, flexShrink: 0, cursor: a.today.done ? "default" : "pointer",
              border: `1.5px solid ${a.today.done ? "var(--green)" : "var(--tx-2)"}`, background: a.today.done ? "var(--green)" : "transparent",
              color: "var(--bg-0)", fontSize: 12, lineHeight: 1, fontWeight: 700 }}>
            {a.today.done ? "✓" : ""}
          </button>
          <span data-testid={`tl-name-${a.id}`} style={{ fontSize: 13, color: a.today.done ? "var(--tx-2)" : "var(--tx-0)", textDecoration: a.today.done ? "line-through" : "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {a.name}
          </span>
        </div>
        {/* chi tiết — streak / remind chip / archive(edit) */}
        <div className="row" style={{ gap: 6, alignItems: "center", justifyContent: "flex-end", flexWrap: "wrap" }}>
          {a.streak > 0 && <span className="num faint" data-testid={`tl-streak-${a.id}`} style={{ fontSize: 10.5 }}>{a.streak}d {streakBadge(a.streak)}</span>}
          {a.remindAt && a.remindRepeat && a.remindRepeat !== "off" && (
            <RemindChip at={a.remindAt} repeat={a.remindRepeat} testid={`tl-remind-${a.id}`} />
          )}
          {editMode && (
            <button className="btn sm ghost" type="button" onClick={() => onArchiveTodo(a.id)} disabled={busyId === a.id}
              data-testid={`tl-archive-${a.id}`} title="Xóa khỏi danh sách">✕</button>
          )}
        </div>
      </div>
    );
  }

  return (
    <section className="view" data-screen="S14" data-testid="tracing-screen">
      <div className="vtitle">
        <h1>Daily Tracing</h1>
        <span className="sub">{data.date || "—"} · {sc.done}/{sc.total} việc xong{sc.timeActive ? ` · ${sc.timeActive} active` : ""}</span>
        <span className="sp" />
        {/* #126 — edit-mode toggle */}
        <button type="button" className={`btn${editMode ? " accent" : ""}`} onClick={() => setEditMode((m) => !m)}
          data-testid="edit-toggle" aria-pressed={editMode}>
          {editMode ? "✓ Xong" : "✎ Sửa"}
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="tracing-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {status === "loading" && <div className="hint" style={{ padding: "24px 4px" }} data-testid="tracing-loading">Đang tải tracing…</div>}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="tracing-error">
          Không tải được tracing: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && (
        <div className="grid tracing-2col" style={{ gridTemplateColumns: "1fr 1fr", gap: 14, alignItems: "start" }} data-testid="tracing-2col">

          {/* ===== LEFT — Timeline (read-view default) + edit affordances ===== */}
          <div className="panel" data-testid="tracing-timeline" style={{ overflow: "hidden" }}>
            <div className="phead">
              <span className="kicker">Hôm nay · theo giờ</span>
              <span className="hint" style={{ marginLeft: "auto" }}>{sc.done}/{sc.total} xong</span>
            </div>

            {/* edit-mode: add-via-text + "+ Từ mẫu" */}
            {editMode && (
              <div style={{ padding: "12px 16px 6px", display: "flex", flexDirection: "column", gap: 8 }} data-testid="todo-edit-tools">
                <form onSubmit={onAddTodo} style={{ display: "flex", flexDirection: "column", gap: 8 }} data-testid="todo-add-form">
                  <div className="row" style={{ gap: 8 }}>
                    <input className="finput" style={{ flex: 1 }} value={todoText} onChange={(e) => setTodoText(e.target.value)}
                      placeholder="Thêm việc cần làm hôm nay…" data-testid="todo-input" aria-label="Việc cần làm" />
                    <button className="btn accent" type="submit" disabled={addBusy} data-testid="todo-submit">{addBusy ? "…" : "Thêm"}</button>
                    <button className="btn" type="button" onClick={openTemplates} data-testid="tpl-open" aria-expanded={tplOpen}>+ Từ mẫu</button>
                  </div>
                  <RemindControls value={todoRemind} onChange={setTodoRemind} channels={channels} idPrefix="todo" />
                  {addErr && <span className="hint neg" data-testid="todo-add-error">{addErr}</span>}
                </form>

                {/* #124 template picker */}
                {tplOpen && (
                  <div className="panel" style={{ padding: "10px 12px", background: "var(--bg-2)" }} data-testid="tpl-picker">
                    <div className="row" style={{ alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span className="kicker">Mẫu đã lưu</span>
                      <span className="sp" style={{ flex: 1 }} />
                      <button className="btn sm accent" type="button" onClick={onAddAllTemplates} disabled={tplBusy === "__all__"} data-testid="tpl-add-all">
                        {tplBusy === "__all__" ? "…" : "Thêm tất cả"}
                      </button>
                    </div>
                    {tplStatus === "loading" && <span className="hint faint" data-testid="tpl-loading">Đang tải mẫu…</span>}
                    {tplStatus === "error" && <span className="hint neg" data-testid="tpl-error">Không tải được mẫu: {tplErr}</span>}
                    {tplStatus === "idle" && templates.length === 0 && <span className="hint faint" data-testid="tpl-empty">Chưa có mẫu nào.</span>}
                    {tplErr && tplStatus !== "error" && <span className="hint neg" data-testid="tpl-add-error">{tplErr}</span>}
                    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                      {templates.map((t) => (
                        <button key={t.id} type="button" className="tagchip" onClick={() => onAddTemplate(t)} disabled={tplBusy === t.id}
                          data-testid={`tpl-${t.id}`} title={`Thêm "${t.name}" vào hôm nay`} style={{ cursor: "pointer" }}>
                          {t.emoji ? `${t.emoji} ` : ""}{t.name}{tplBusy === t.id ? " …" : ""}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {rowErr && <div style={{ padding: "4px 16px" }}><span className="hint neg" data-testid="todo-row-error">⚠ {rowErr}</span></div>}

            {/* the time-rail */}
            <div className="tlx-list" style={{ padding: "6px 8px 10px" }} data-testid="timeline-rail">
              {acts.length === 0 ? (
                <div style={{ padding: "22px 12px", textAlign: "center" }} data-testid="timeline-empty">
                  <div className="hint" style={{ fontSize: 13 }}>Chưa có việc nào hôm nay.</div>
                  <div className="hint faint" style={{ marginTop: 4 }}>
                    {editMode ? "Gõ ở trên + Enter, hoặc “+ Từ mẫu”." : "Bấm “✎ Sửa” để thêm việc."}
                  </div>
                </div>
              ) : (
                <>
                  {timed.map((a) => <TimelineRow key={a.id} a={a} />)}
                  {anytime.length > 0 && (
                    <>
                      {timed.length > 0 && (
                        <div className="hint faint" data-testid="timeline-anytime-sep" style={{ padding: "8px 8px 4px", fontSize: 10.5 }}>CẢ NGÀY</div>
                      )}
                      {anytime.map((a) => <TimelineRow key={a.id} a={a} />)}
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          {/* ===== RIGHT — Note (multi-list) ===== */}
          <div className="panel" data-testid="tracing-notes" style={{ overflow: "hidden" }}>
            <div className="phead">
              <span className="kicker">Ghi chú trong ngày</span>
              <span className="hint" style={{ marginLeft: "auto" }}>{notesApi.notes.length} ghi chú</span>
            </div>

            {/* add-a-note (always available — notes are quick captures) */}
            <form onSubmit={onAddNote} style={{ padding: "12px 16px 6px", display: "flex", flexDirection: "column", gap: 8 }} data-testid="note-add-form">
              <textarea className="finput" rows={2} value={noteText} onChange={(e) => setNoteText(e.target.value)}
                placeholder="Ghi lại điều cần nhớ / một suy nghĩ trong ngày…" data-testid="note-input" aria-label="Nội dung ghi chú" style={{ resize: "vertical" }} />
              <RemindControls value={noteRemind} onChange={setNoteRemind} channels={channels} idPrefix="note" allowOnce />
              <div className="row" style={{ gap: 8 }}>
                <button className="btn accent" type="submit" disabled={noteBusy} data-testid="note-submit">{noteBusy ? "Đang lưu…" : "Thêm ghi chú"}</button>
              </div>
              {noteErr && <span className="hint neg" data-testid="note-add-error">{noteErr}</span>}
            </form>

            {noteRowErr && <div style={{ padding: "0 16px" }}><span className="hint neg" data-testid="note-row-error">⚠ {noteRowErr}</span></div>}
            {notesApi.status === "error" && (
              <div style={{ padding: "0 16px 8px" }}><span className="hint neg" data-testid="notes-load-error">Không tải được ghi chú: {notesApi.errMsg}.</span></div>
            )}

            {/* the multi-card note list */}
            <div className="tl-list" style={{ padding: "6px 8px 10px" }} data-testid="note-list">
              {notesApi.notes.length === 0 ? (
                <div style={{ padding: "22px 12px", textAlign: "center" }} data-testid="notes-empty">
                  <div className="hint faint" style={{ fontSize: 12.5 }}>Chưa có ghi chú nào.</div>
                </div>
              ) : (
                notesApi.notes.map((n) => (
                  <div className="note-card" key={n.id} data-testid={`note-${n.id}`}
                    style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 8px", borderBottom: "1px solid var(--bg-2)" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div data-testid={`note-text-${n.id}`} style={{ fontSize: 13, color: "var(--tx-0)", whiteSpace: "pre-wrap" }}>{n.text}</div>
                      {/* #125 — a one-shot (remindDate set) OR a recurring (repeat≠off) chip */}
                      {n.remindAt && (n.remindDate || n.remindRepeat !== "off") && (
                        <div style={{ marginTop: 4 }}>
                          <RemindChip at={n.remindAt} repeat={n.remindRepeat} date={n.remindDate} testid={`note-remind-${n.id}`} />
                        </div>
                      )}
                    </div>
                    <button className="btn sm ghost" type="button" onClick={() => onDeleteNote(n)} disabled={noteBusyId === n.id}
                      data-testid={`note-delete-${n.id}`} title="Xóa ghi chú">✕</button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ===== streak + heatmap — KEPT but small / collapsed ===== */}
      {status === "ready" && (
        <details className="panel" data-testid="tracing-stats" style={{ marginTop: 14 }}>
          <summary className="phead" style={{ cursor: "pointer", listStyle: "revert" }} data-testid="tracing-stats-summary">
            <span className="kicker">Streak &amp; lịch sử 12 tuần</span>
            <span className="hint" style={{ marginLeft: "auto" }}>streak tốt nhất {sc.topStreak}d · mở để xem</span>
          </summary>
          <div style={{ padding: "12px 16px 16px" }}>
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
      )}
    </section>
  );
}
