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
import { useEffect, useMemo, useRef, useState } from "react";
import { useTracing } from "@/lib/useTracing";
import { useTracingNotes } from "@/lib/useTracingNotes";
import { apiBase, ApiError, getReminderChannels } from "@/lib/api";
import { slugifyVi } from "@/lib/format";
import { useClickAway } from "@/lib/useClickAway";
import { Popover } from "@/components/Popover";
import { TemplateSetsModal } from "./TemplateSetsModal";
import type {
  ActivityView, ActivityInput, TracingNote, TracingNoteInput,
  RemindRepeat, RemindChannel, ReminderChannelOption,
} from "@/lib/types";

const WEEK_DAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]; // Mon→Sun

/** TRACING-ALARM — 🔒 LOCKED weekday ints: Mon=0,Tue=1,…,Sun=6 (= Python date.weekday(),
 *  matches backend). FE labels by index: T2=0,T3=1,T4=2,T5=3,T6=4,T7=5,CN=6. */
const DAY_LABELS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]; // index = weekday int (Mon0..Sun6)

/** Format a remindDays int[] → compact VN labels, collapsing a CONTIGUOUS run to "T2-T6".
 *  e.g. [0,1,2,3,4]→"T2-T6" · [0,2,4]→"T2, T4, T6" · []→"" (defensive). */
function formatRemindDays(days: number[]): string {
  const sorted = [...new Set(days)].filter((d) => d >= 0 && d <= 6).sort((a, b) => a - b);
  if (sorted.length === 0) return "";
  const runs: string[] = [];
  let start = sorted[0], prev = sorted[0];
  for (let i = 1; i <= sorted.length; i++) {
    const cur = sorted[i];
    if (cur === prev + 1) { prev = cur; continue; }
    // close the current run
    runs.push(start === prev ? DAY_LABELS[start] : `${DAY_LABELS[start]}-${DAY_LABELS[prev]}`);
    start = cur; prev = cur;
  }
  return runs.join(", ");
}

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
type RemindState = { on: boolean; kind: RemindKind; time: string; repeat: RemindRepeat; date: string; channel: RemindChannel; days: number[] };
const EMPTY_REMIND: RemindState = { on: false, kind: "recurring", time: "07:00", repeat: "daily", date: "", channel: "in_app", days: [] };
/** #139 — every newly-added activity gets a time (no bare "–"). The add-form's TIME input
 *  defaults to this; the user can edit it before adding. A fixed, sensible 08:00 (start of
 *  the working day) — least-friction, not a hard-required 422 (would block quick-add). */
const ADD_TIME_DEFAULT = "08:00";

/** today (VN) as YYYY-MM-DD — the client-side min for the one-shot date picker (the BE
 *  also 422s a past date; this is just a friendly guard). */
function todayVnDate(): string {
  // toISOString is UTC; for the date-input min a UTC date is close enough (the BE is the
  // authority on "past" in VN time — it 422s, we surface the hint).
  return new Date().toISOString().slice(0, 10);
}

function RemindControls({ value, onChange, channels, idPrefix, allowOnce = false, defaultTime }: {
  value: RemindState; onChange: (next: RemindState) => void; channels: ReminderChannelOption[]; idPrefix: string;
  allowOnce?: boolean;
  /** TRACING-UX3 req2 — when the toggle flips OFF→ON, seed remind.time from this (the
   *  activity's own time) instead of the disjoint 07:00 default. Sync is ON TOGGLE-ON ONLY
   *  (we don't fight a later explicit remind-time edit). Undefined → keep value.time. */
  defaultTime?: string;
}) {
  // toggle handler: flipping ON seeds the time from defaultTime (the activity time) when one
  // is provided; flipping OFF just clears `on`. Toggle-on-only so a user's later edit sticks.
  function toggle() {
    if (!value.on) {
      onChange({ ...value, on: true, time: defaultTime || value.time });
    } else {
      onChange({ ...value, on: false });
    }
  }
  return (
    <div className="row" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <button type="button" className={`tab${value.on ? " on" : ""}`} onClick={toggle}
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
            <select className="finput" style={{ width: 160 }} value={value.repeat}
              onChange={(e) => onChange({ ...value, repeat: e.target.value as RemindRepeat })} data-testid={`${idPrefix}-remind-repeat`} aria-label="Lặp lại">
              <option value="daily">Hằng ngày</option>
              <option value="weekdays">Ngày thường (T2–T6)</option>
              {/* TRACING-ALARM — pick specific weekdays (alarm-style). */}
              <option value="custom">Tùy chọn (chọn thứ)</option>
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
          {/* TRACING-ALARM — custom-weekday toggles (recurring branch only). 7 buttons
              T2…CN → weekday ints 0..6 (🔒 Mon0..Sun6). Clicking toggles the int in days.
              Empty → an inline "chọn ít nhất 1 thứ" hint (the parent add also guards). */}
          {value.repeat === "custom" && !(allowOnce && value.kind === "once") && (
            <div className="trk-day-row" data-testid={`${idPrefix}-custom-days`} role="group" aria-label="Chọn thứ trong tuần">
              {DAY_LABELS.map((lbl, n) => {
                const sel = value.days.includes(n);
                return (
                  <button type="button" key={n} className={`trk-day-btn${sel ? " on" : ""}`}
                    aria-pressed={sel} data-testid={`${idPrefix}-day-${n}`} title={lbl}
                    onClick={() => onChange({ ...value, days: sel ? value.days.filter((d) => d !== n) : [...value.days, n] })}>
                    {lbl}
                  </button>
                );
              })}
              {value.days.length === 0 && (
                <span className="hint neg" style={{ fontSize: 10.5 }} data-testid={`${idPrefix}-days-hint`}>Chọn ít nhất 1 thứ</span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** human label for a reminder channel (GAP 2 — show the SET channel on the card face). */
function channelLabel(c: RemindChannel | undefined): string {
  return c === "discord" ? "Discord" : c === "email" ? "Email" : "In-app";
}
/** human label for the recurring frequency. TRACING-ALARM: "custom" → "" (the chip shows
 *  the day list instead via formatRemindDays). */
function freqLabel(repeat: RemindRepeat): string {
  return repeat === "daily" ? "hằng ngày" : repeat === "weekdays" ? "ngày thường" : "";
}

/** a compact remind chip shown on a timed todo/note. #125: when `date` is set it's a
 *  ONE-SHOT (date @ time); otherwise the recurring (repeat) chip. #136 GAP-2: the SET
 *  frequency + channel are shown ON the card face (e.g. "🔔 07:00 · hằng ngày · Discord")
 *  so the user sees what they configured without opening the editor.
 *  TRACING-ALARM: a custom reminder renders its days compactly (e.g. "🔔 07:00 · T2-T6"). */
function RemindChip({ at, repeat, date, channel, days, testid }: { at: string; repeat: RemindRepeat; date?: string | null; channel?: RemindChannel; days?: number[] | null; testid: string }) {
  const ch = channelLabel(channel);
  // custom → compact day list ("T2-T6"); falls back to freqLabel for daily/weekdays.
  const freq = repeat === "custom"
    ? formatRemindDays(Array.isArray(days) ? days : [])
    : freqLabel(repeat);
  return (
    <span className="tagchip acc" data-testid={testid} title={date ? "Nhắc một lần" : "Nhắc nhở"}>
      🔔 {date ? (
        <><span className="num">{date}</span> lúc <span className="num">{at}</span></>
      ) : (
        <><span className="num">{at}</span>{freq ? <> · <span data-testid={`${testid}-days`}>{freq}</span></> : null}</>
      )}
      {" · "}<span data-testid={`${testid}-channel`}>{ch}</span>
    </span>
  );
}

/** #136 G3 — the effective time on the rail = the dedicated `time` field (independent of
 *  the reminder), falling back to remindAt when time isn't set. */
function railTime(a: ActivityView): string | null {
  return a.time || a.remindAt || null;
}

/** Order activities for the timeline rail: TIMED (railTime set) ascending first, then
 *  UN-TIMED (anytime) in their given order. Pure. */
function timelineOrder(acts: ActivityView[]): { timed: ActivityView[]; anytime: ActivityView[] } {
  const timed = acts.filter((a) => !!railTime(a)).slice().sort((a, b) => {
    const ta = railTime(a)!, tb = railTime(b)!;
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });
  const anytime = acts.filter((a) => !railTime(a));
  return { timed, anytime };
}

export default function TracingPage() {
  const { data, status, errMsg, warning, reload, log, add, edit, archive, untick } = useTracing();
  const notesApi = useTracingNotes();

  // #136 — NO global edit-mode. Timeline is the default; edit is PER-CARD (each row's ⋯).

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
  // #139 — every NEW activity gets a time (no bare "–"). The add-form has a TIME input
  // defaulting to ADD_TIME_DEFAULT; sent as ActivityInput.time. User can still edit it
  // before adding, and a legacy/timeless row keeps the clickable "–" ("Đặt giờ") to set one.
  const [todoTime, setTodoTime] = useState<string>(ADD_TIME_DEFAULT);
  const [todoRemind, setTodoRemind] = useState<RemindState>({ ...EMPTY_REMIND });
  const [addBusy, setAddBusy] = useState(false);
  const [addErr, setAddErr] = useState("");
  const [rowErr, setRowErr] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  // ---- #137 template-SET modal (replaces the rejected 1-word chip row) ----
  const [tplModalOpen, setTplModalOpen] = useState(false);
  const [toast, setToast] = useState("");

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
  // TRACING-UX3 req4 — current streak = the best running streak across today's activities
  // (0 when there are none). best streak = sc.topStreak (BE-computed). Both client-side, no fetch.
  const currentStreak = useMemo(() => Math.max(0, ...acts.map((a) => a.streak)), [acts]);

  // #137 — a template-set was imported → refetch the board + toast "đã thêm N việc".
  function onTemplateImported(created: number, skipped: string[]) {
    reload();
    setToast(`Đã thêm ${created} việc${skipped.length ? ` · ${skipped.length} đã có sẵn` : ""}.`);
    setTplModalOpen(false);
  }
  // auto-dismiss the toast.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  async function onAddTodo(e: React.FormEvent) {
    e.preventDefault();
    setAddErr("");
    const text = todoText.trim();
    if (!text) { setAddErr("Nhập nội dung việc cần làm."); return; }
    const id = slugifyVi(text);
    if (!id) { setAddErr("Nội dung không tạo được id — thử chữ có dấu cách / chữ cái."); return; }
    // TRACING-UX3 req1 — giờ là BẮT BUỘC: block submit when the time is empty (the user
    // cleared the 08:00 prefill). No more silent fallback-to-null; every new activity is timed.
    if (!todoTime) { setAddErr("Chọn giờ cho việc — giờ là bắt buộc."); return; }
    // TRACING-ALARM — a custom-weekday reminder needs ≥1 day picked before adding.
    if (todoRemind.on && todoRemind.repeat === "custom" && todoRemind.days.length === 0) {
      setAddErr("Chọn ít nhất 1 thứ cho nhắc nhở tùy chọn."); return;
    }
    const body: ActivityInput = {
      id, name: text, goal: 1,
      // TRACING-UX3 req1 — always a real time (validation above guarantees todoTime is set).
      time: todoTime,
      remindAt: todoRemind.on ? todoRemind.time : null,
      remindRepeat: todoRemind.on ? todoRemind.repeat : "off",
      // TRACING-ALARM — send the chosen weekday ints only for a custom reminder; null otherwise.
      remindDays: todoRemind.on && todoRemind.repeat === "custom" ? todoRemind.days : null,
      remindChannel: todoRemind.on ? todoRemind.channel : undefined,
    };
    setAddBusy(true);
    try {
      await add(body);
      setTodoText(""); setTodoTime(ADD_TIME_DEFAULT); setTodoRemind({ ...EMPTY_REMIND });
    } catch (err) { setAddErr(errText(err)); } finally { setAddBusy(false); }
  }

  // #136 — tick = TOGGLE. tick an undone row → done (log val=1); tick a DONE row → UN-complete
  // (clear today's log). 1-click, works in the read/timeline view (NOT gated by edit).
  async function onTickTodo(a: ActivityView) {
    setRowErr(""); setBusyId(a.id);
    try {
      if (a.today.done) {
        await untick(a.id);     // clear today's log → done=false (BE endpoint, #136)
      } else {
        await log(a.id, { val: 1, dur_min: null, note: null });
      }
    } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
  }

  async function onArchiveTodo(id: string) {
    setRowErr(""); setBusyId(id);
    try { await archive(id); } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
  }

  // #136 — inline RENAME (the missing Update): PUT /tracing/activities/{id} {name}.
  async function onRenameTodo(id: string, name: string) {
    const trimmed = name.trim();
    if (!trimmed) { setRowErr("Tên việc không được trống."); return; }
    setRowErr(""); setBusyId(id);
    try { await edit(id, { name: trimmed }); } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
  }

  // #136 — set/clear a todo's reminder (time + freq + channel) → PUT.
  // TRACING-ALARM — custom repeat carries remindDays (Mon0..Sun6); guard ≥1 day.
  async function onSetReminder(id: string, r: RemindState) {
    setRowErr("");
    if (r.on && r.repeat === "custom" && r.days.length === 0) {
      setRowErr("Chọn ít nhất 1 thứ cho nhắc nhở tùy chọn."); return;
    }
    setBusyId(id);
    try {
      await edit(id, {
        remindAt: r.on ? r.time : null,
        remindRepeat: r.on ? r.repeat : "off",
        remindDays: r.on && r.repeat === "custom" ? r.days : null,
        remindChannel: r.on ? r.channel : undefined,
      });
    } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
  }

  // #136 G3-(ii) — set/clear a todo's dedicated TIME (independent of the reminder) → PUT {time}.
  async function onSetTime(id: string, time: string | null) {
    setRowErr(""); setBusyId(id);
    try { await edit(id, { time }); } catch (err) { setRowErr(errText(err)); } finally { setBusyId(null); }
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

  // #136 — set/clear a NOTE's reminder PER-CARD (mirrors the activity per-card reminder).
  // Notes support BOTH kinds: recurring (repeat) and one-shot (a future date → remindDate).
  async function onSetNoteReminder(n: TracingNote, r: RemindState) {
    const isOnce = r.on && r.kind === "once";
    if (isOnce && !r.date) { setNoteRowErr("Chọn ngày cho nhắc một lần."); return; }
    setNoteRowErr(""); setNoteBusyId(n.id);
    try {
      await notesApi.update(n.id, {
        remindAt: r.on ? r.time : null,
        remindDate: isOnce ? r.date : null,
        remindRepeat: r.on && !isOnce ? r.repeat : "off",
        remindChannel: r.on ? r.channel : undefined,
      });
    } catch (err) { setNoteRowErr(errText(err)); } finally { setNoteBusyId(null); }
  }

  /** #136 — one timeline row with its OWN per-card edit (⋯ menu: rename inline / set
   *  reminder / delete). NO global edit toggle. Tick = toggle (done ↔ un-complete). */
  function TimelineRow({ a }: { a: ActivityView }) {
    const [menuOpen, setMenuOpen] = useState(false);
    const [editing, setEditing] = useState(false);       // inline rename
    const [nameVal, setNameVal] = useState(a.name);
    const [remOpen, setRemOpen] = useState(false);       // the per-card reminder editor
    const [timeOpen, setTimeOpen] = useState(false);     // #136 G3 — the per-card time editor
    const [timeVal, setTimeVal] = useState(railTime(a) ?? "");
    // #137-T2 (UX) — close the inline editors when a click lands outside (not
    // re-click-the-icon). The ⋯ menu (#142-P1) is now a portaled <Popover> that owns
    // its own click-away/Escape + viewport-edge collision; we just anchor it to the ⋯ button.
    const menuBtnRef = useRef<HTMLButtonElement | null>(null);
    const timeEditorRef = useClickAway<HTMLDivElement>(timeOpen, () => setTimeOpen(false));
    const remEditorRef = useClickAway<HTMLDivElement>(remOpen, () => setRemOpen(false));
    const [rem, setRem] = useState<RemindState>({
      ...EMPTY_REMIND,
      on: !!a.remindAt && a.remindRepeat !== "off",
      time: a.remindAt ?? "07:00",
      repeat: (a.remindRepeat && a.remindRepeat !== "off" ? a.remindRepeat : "daily"),
      // TRACING-ALARM — seed the existing custom weekdays so editing shows them selected.
      days: Array.isArray(a.remindDays) ? a.remindDays : [],
      channel: a.remindChannel ?? "in_app",
    });

    async function saveName() {
      if (nameVal.trim() && nameVal.trim() !== a.name) await onRenameTodo(a.id, nameVal);
      setEditing(false);
    }
    async function saveReminder() {
      await onSetReminder(a.id, rem);
      setRemOpen(false);
    }
    async function saveTime() {
      await onSetTime(a.id, timeVal.trim() || null); // #136 G3 — empty clears the time
      setTimeOpen(false);
    }

    return (
      <div className="tlx-row" data-testid={`tl-${a.id}`} data-done={a.today.done}
        style={{ display: "grid", gridTemplateColumns: "66px 16px 1fr auto", alignItems: "center", gap: 10, padding: "9px 6px", borderBottom: "1px solid var(--bg-2)" }}>
        {/* giờ — #136 G3: the dedicated time (fallback remindAt). Click to set/edit.
            #139 — a null-time (legacy) row shows a PROMINENT "⏰ Đặt giờ" pill (NOT a bare "—")
            so every row reads as either a real time or an actionable "tap to set". No auto-backfill
            — we never write a guessed time to the user's data; the pill just opens the time editor. */}
        {railTime(a) ? (
          <button type="button" className="tl-time-btn num faint" data-testid={`tl-time-${a.id}`}
            onClick={() => { setTimeVal(railTime(a) ?? ""); setTimeOpen((o) => !o); }} title="Đổi giờ"
            style={{ fontSize: 12, textAlign: "right", background: "none", border: 0, cursor: "pointer", color: "var(--tx-1)", fontFamily: "var(--mono)" }}>
            {railTime(a)}
          </button>
        ) : (
          <button type="button" className="tl-settime-pill" data-testid={`tl-time-${a.id}`}
            onClick={() => { setTimeVal(""); setTimeOpen((o) => !o); }} title="Đặt giờ cho việc này"
            aria-label="Đặt giờ">
            ⏰ <span className="tl-settime-pill-label">Đặt giờ</span>
          </button>
        )}
        {/* color-dot */}
        <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: "50%", background: a.today.done ? "var(--green)" : (a.color || "var(--tx-2)"), justifySelf: "center", boxShadow: a.today.done ? "0 0 6px -1px var(--green)" : undefined }} />
        {/* việc — TOGGLE tick + icon + name + (G4-A) metric/sub-detail from REAL fields */}
        <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
          <button type="button" className={`todo-tick${a.today.done ? " on" : ""}`} onClick={() => onTickTodo(a)}
            disabled={busyId === a.id} data-testid={`tick-${a.id}`} aria-pressed={a.today.done}
            aria-label={a.today.done ? "Bỏ đánh dấu xong" : "Đánh dấu xong"} title={a.today.done ? "Bấm để bỏ hoàn thành" : "Đánh dấu xong"}
            style={{ width: 20, height: 20, borderRadius: 5, flexShrink: 0, cursor: "pointer",
              border: `1.5px solid ${a.today.done ? "var(--green)" : "var(--tx-2)"}`, background: a.today.done ? "var(--green)" : "transparent",
              color: "var(--bg-0)", fontSize: 12, lineHeight: 1, fontWeight: 700 }}>
            {a.today.done ? "✓" : ""}
          </button>
          {/* #136 G4-A — the activity emoji as a leading icon (real field; "•" fallback) */}
          {a.emoji && <span aria-hidden="true" data-testid={`tl-icon-${a.id}`} style={{ fontSize: 14, flexShrink: 0 }}>{a.emoji}</span>}
          <div style={{ display: "flex", flexDirection: "column", minWidth: 0, gap: 1 }}>
            {editing ? (
              <input className="finput" data-testid={`tl-rename-input-${a.id}`} value={nameVal} autoFocus
                onChange={(e) => setNameVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") saveName(); if (e.key === "Escape") { setNameVal(a.name); setEditing(false); } }}
                onBlur={saveName} style={{ fontSize: 13, padding: "2px 6px" }} />
            ) : (
              <span data-testid={`tl-name-${a.id}`} onDoubleClick={() => { setNameVal(a.name); setEditing(true); }}
                title="Bấm đúp để đổi tên"
                style={{ fontSize: 13, color: a.today.done ? "var(--tx-2)" : "var(--tx-0)", textDecoration: a.today.done ? "line-through" : "none", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", cursor: "text" }}>
                {a.name}
              </span>
            )}
            {/* #136 G4-A — sub-detail line: metric (val+unit) · dur · today's note — REAL fields
                only (no fabricated km/pace/location). Rendered only when there's something. */}
            {!editing && (a.today.val > 0 || a.today.dur || a.today.note) && (
              <span className="faint" data-testid={`tl-detail-${a.id}`} style={{ fontSize: 10.5, fontFamily: "var(--mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {[
                  a.today.val > 0 ? `${a.today.val}${a.unit ? ` ${a.unit}` : ""}` : null,
                  a.today.dur || null,
                  a.today.note || null,
                ].filter(Boolean).join(" · ")}
              </span>
            )}
          </div>
        </div>
        {/* chi tiết — streak / remind chip / per-card ⋯ ops */}
        <div className="row" style={{ gap: 6, alignItems: "center", justifyContent: "flex-end", flexWrap: "wrap", position: "relative" }}>
          {a.streak > 0 && <span className="num faint" data-testid={`tl-streak-${a.id}`} style={{ fontSize: 10.5 }}>{a.streak}d {streakBadge(a.streak)}</span>}
          {a.remindAt && a.remindRepeat && a.remindRepeat !== "off" && (
            <RemindChip at={a.remindAt} repeat={a.remindRepeat} days={a.remindDays} channel={a.remindChannel} testid={`tl-remind-${a.id}`} />
          )}
          {/* #136 — the per-card ⋯ menu (rename / reminder / delete). #142-P1: portaled
              <Popover> (viewport-edge collision + outside-click/Escape close). */}
          <div className="tl-ops" style={{ position: "relative" }}>
            <button type="button" ref={menuBtnRef} className="tl-ops-btn" onClick={() => setMenuOpen((o) => !o)}
              aria-haspopup="menu" aria-expanded={menuOpen} data-testid={`tl-ops-${a.id}`} title="Sửa việc này">⋯</button>
            <Popover open={menuOpen} anchorRef={menuBtnRef} onClose={() => setMenuOpen(false)}
              className="tl-ops-menu" testId={`tl-ops-menu-${a.id}`}>
              <button type="button" role="menuitem" data-testid={`tl-op-rename-${a.id}`}
                onClick={() => { setMenuOpen(false); setNameVal(a.name); setEditing(true); }}>✎ Đổi tên</button>
              <button type="button" role="menuitem" data-testid={`tl-op-time-${a.id}`}
                onClick={() => { setMenuOpen(false); setTimeVal(railTime(a) ?? ""); setTimeOpen((o) => !o); }}>🕐 Đặt giờ</button>
              <button type="button" role="menuitem" data-testid={`tl-op-remind-${a.id}`}
                onClick={() => { setMenuOpen(false); setRemOpen((o) => !o); }}>🔔 Nhắc nhở</button>
              <button type="button" role="menuitem" className="neg" data-testid={`tl-op-delete-${a.id}`}
                onClick={() => { setMenuOpen(false); onArchiveTodo(a.id); }}>✕ Xóa</button>
            </Popover>
          </div>
        </div>

        {/* #136 G3 — the per-card TIME editor (a HH:MM, independent of the reminder). #137-T2: closes on outside-click. */}
        {timeOpen && (
          <div ref={timeEditorRef} style={{ gridColumn: "1 / -1", padding: "8px 6px 4px", display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }} data-testid={`tl-time-editor-${a.id}`}>
            <span className="hint faint">Giờ:</span>
            <input className="finput num" type="time" style={{ width: 120 }} value={timeVal}
              onChange={(e) => setTimeVal(e.target.value)} data-testid={`tl-time-input-${a.id}`} aria-label="Giờ của việc" />
            <button type="button" className="btn sm ghost" onClick={() => { setTimeVal(""); void onSetTime(a.id, null); setTimeOpen(false); }}
              disabled={busyId === a.id} data-testid={`tl-time-clear-${a.id}`}>Xóa giờ</button>
            <span className="sp" style={{ flex: 1 }} />
            <button type="button" className="btn sm ghost" onClick={() => setTimeOpen(false)} disabled={busyId === a.id}>Hủy</button>
            <button type="button" className="btn sm accent" onClick={saveTime} disabled={busyId === a.id} data-testid={`tl-time-save-${a.id}`}>
              {busyId === a.id ? "…" : "Lưu giờ"}
            </button>
          </div>
        )}

        {/* #136 — the per-card reminder editor (time + freq + channel; reuse RemindControls). #137-T2: closes on outside-click. */}
        {remOpen && (
          <div ref={remEditorRef} style={{ gridColumn: "1 / -1", padding: "8px 6px 4px", display: "flex", flexDirection: "column", gap: 6 }} data-testid={`tl-remind-editor-${a.id}`}>
            <RemindControls value={rem} onChange={setRem} channels={channels} idPrefix={`tlrem-${a.id}`} />
            <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
              <button type="button" className="btn sm ghost" onClick={() => setRemOpen(false)} disabled={busyId === a.id}>Hủy</button>
              <button type="button" className="btn sm accent" onClick={saveReminder} disabled={busyId === a.id} data-testid={`tl-remind-save-${a.id}`}>
                {busyId === a.id ? "…" : "Lưu nhắc nhở"}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  /** #136 — one NOTE card with its OWN per-card ⋯ (set reminder / delete). Mirrors the
   *  activity per-card pattern; notes support BOTH remind kinds (recurring + one-shot). */
  function NoteCard({ n }: { n: TracingNote }) {
    const [menuOpen, setMenuOpen] = useState(false);
    const [remOpen, setRemOpen] = useState(false);
    // #137-T2 (UX) — close the reminder editor on outside-click. #142-P1: the ⋯ menu is
    // a portaled <Popover> (owns its own click-away/Escape); anchor it to the ⋯ button.
    const noteMenuBtnRef = useRef<HTMLButtonElement | null>(null);
    const noteRemEditorRef = useClickAway<HTMLDivElement>(remOpen, () => setRemOpen(false));
    const hasRem = !!n.remindAt && (!!n.remindDate || n.remindRepeat !== "off");
    const [rem, setRem] = useState<RemindState>({
      ...EMPTY_REMIND,
      on: hasRem,
      kind: n.remindDate ? "once" : "recurring",
      time: n.remindAt ?? "07:00",
      date: n.remindDate ?? "",
      repeat: (n.remindRepeat && n.remindRepeat !== "off" ? n.remindRepeat : "daily"),
      channel: n.remindChannel ?? "in_app",
    });
    async function saveRem() { await onSetNoteReminder(n, rem); setRemOpen(false); }

    return (
      <div className="note-card" data-testid={`note-${n.id}`}
        style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", gap: 10, padding: "10px 8px", borderBottom: "1px solid var(--bg-2)", position: "relative" }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div data-testid={`note-text-${n.id}`} style={{ fontSize: 13, color: "var(--tx-0)", whiteSpace: "pre-wrap" }}>{n.text}</div>
          {hasRem && (
            <div style={{ marginTop: 4 }}>
              <RemindChip at={n.remindAt as string} repeat={n.remindRepeat} date={n.remindDate} channel={n.remindChannel} testid={`note-remind-${n.id}`} />
            </div>
          )}
        </div>
        {/* #136 — per-note ⋯ menu (set reminder / delete). #142-P1: portaled <Popover>. */}
        <div className="tl-ops" style={{ position: "relative" }}>
          <button type="button" ref={noteMenuBtnRef} className="tl-ops-btn" onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu" aria-expanded={menuOpen} data-testid={`note-ops-${n.id}`} title="Sửa ghi chú này">⋯</button>
          <Popover open={menuOpen} anchorRef={noteMenuBtnRef} onClose={() => setMenuOpen(false)}
            className="tl-ops-menu" testId={`note-ops-menu-${n.id}`}>
            <button type="button" role="menuitem" data-testid={`note-op-remind-${n.id}`}
              onClick={() => { setMenuOpen(false); setRemOpen((o) => !o); }}>🔔 Nhắc nhở</button>
            <button type="button" role="menuitem" className="neg" data-testid={`note-op-delete-${n.id}`}
              onClick={() => { setMenuOpen(false); onDeleteNote(n); }}>✕ Xóa</button>
          </Popover>
        </div>
        {/* the per-note reminder editor (recurring + one-shot, reuse RemindControls allowOnce). #137-T2: closes on outside-click. */}
        {remOpen && (
          <div ref={noteRemEditorRef} style={{ width: "100%", padding: "8px 2px 2px", display: "flex", flexDirection: "column", gap: 6 }} data-testid={`note-remind-editor-${n.id}`}>
            <RemindControls value={rem} onChange={setRem} channels={channels} idPrefix={`nrem-${n.id}`} allowOnce />
            <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
              <button type="button" className="btn sm ghost" onClick={() => setRemOpen(false)} disabled={noteBusyId === n.id}>Hủy</button>
              <button type="button" className="btn sm accent" onClick={saveRem} disabled={noteBusyId === n.id} data-testid={`note-remind-save-${n.id}`}>
                {noteBusyId === n.id ? "…" : "Lưu nhắc nhở"}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <section className="view" data-screen="S14" data-testid="tracing-screen">
      <div className="vtitle">
        <h1>Daily Tracing</h1>
        <span className="sub">{data.date || "—"} · {sc.done}/{sc.total} việc xong{sc.timeActive ? ` · ${sc.timeActive} active` : ""}</span>
        {/* #136 — NO global "Sửa" toggle; edit is per-card (the ⋯ on each row). */}
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

            {/* #136 — add-via-text + "+ Từ mẫu" ALWAYS visible (not gated behind a global
                edit toggle — the template button was hidden before, the user's complaint). */}
            <div style={{ padding: "12px 16px 6px", display: "flex", flexDirection: "column", gap: 8 }} data-testid="todo-add-tools">
                {/* noValidate — a type="time" input reports validity.badInput when empty/incomplete,
                    and native constraint-validation fires its OWN (English) tooltip BEFORE our onSubmit
                    runs → our custom Vietnamese "giờ là bắt buộc" message would never show. We own the
                    validation (onAddTodo), so disable the native pass and let our guard be the gate. */}
                <form onSubmit={onAddTodo} noValidate style={{ display: "flex", flexDirection: "column", gap: 8 }} data-testid="todo-add-form">
                  <div className="row" style={{ gap: 8 }}>
                    <input className="finput" style={{ flex: 1 }} value={todoText} onChange={(e) => setTodoText(e.target.value)}
                      placeholder="Thêm việc cần làm hôm nay…" data-testid="todo-input" aria-label="Việc cần làm" />
                    {/* TRACING-UX3 req1 — giờ là BẮT BUỘC. Prefilled 08:00 (least friction) but the
                        user must see/confirm/edit it: required + aria-required + an accent-border cue +
                        a "*" label so it reads as mandatory (no longer a silent fallback). */}
                    <label className="trk-req-time" data-testid="todo-time-label" title="Giờ của việc — bắt buộc">
                      {/* aria-required (a11y) but NOT native `required`: a native-required empty
                          time would trigger the browser's own tooltip + block submit BEFORE our JS
                          guard runs — so we'd never show the custom Vietnamese message. We own the
                          validation (onAddTodo) → keep the cue, let our message be the source of truth. */}
                      <input className="finput num trk-req" type="time" style={{ width: 110 }} value={todoTime}
                        onChange={(e) => setTodoTime(e.target.value)} data-testid="todo-time" aria-label="Giờ (bắt buộc)"
                        aria-required="true" />
                      <span className="trk-req-star" aria-hidden="true">*</span>
                    </label>
                    <button className="btn accent" type="submit" disabled={addBusy} data-testid="todo-submit">{addBusy ? "…" : "Thêm"}</button>
                    {/* #137 — opens the template-SET modal (replaced the rejected 1-word chip row). */}
                    <button className="btn" type="button" onClick={() => setTplModalOpen(true)} data-testid="tpl-open">+ Từ mẫu</button>
                  </div>
                  {/* TRACING-UX3 req2 — the todo add-row passes its own time as the remind default:
                      toggling 🔔 ON seeds the nhắc-time = giờ-việc (not the disjoint 07:00). */}
                  <RemindControls value={todoRemind} onChange={setTodoRemind} channels={channels} idPrefix="todo" defaultTime={todoTime} />
                  {addErr && <span className="hint neg" data-testid="todo-add-error">{addErr}</span>}
                </form>
              </div>

            {toast && <div style={{ padding: "4px 16px" }}><span className="hint pos" data-testid="tracing-toast">{toast}</span></div>}
            {rowErr && <div style={{ padding: "4px 16px" }}><span className="hint neg" data-testid="todo-row-error">⚠ {rowErr}</span></div>}

            {/* the time-rail */}
            <div className="tlx-list" style={{ padding: "6px 8px 10px" }} data-testid="timeline-rail">
              {acts.length === 0 ? (
                <div style={{ padding: "22px 12px", textAlign: "center" }} data-testid="timeline-empty">
                  <div className="hint" style={{ fontSize: 13 }}>Chưa có việc nào hôm nay.</div>
                  <div className="hint faint" style={{ marginTop: 4 }}>
                    Gõ ở trên + Enter, hoặc bấm “+ Từ mẫu”.
                  </div>
                </div>
              ) : (
                <>
                  {/* TRACING-UX3 req3 — the left column is a real vertical time-rail: every NEW
                      activity has a time (req1) → timed rows ascending. OLD timeless rows (time=null,
                      pre-this-sprint) are NOT backfilled with a fake time — they drop into a small
                      labeled "Chưa đặt giờ" bucket at the BOTTOM, keeping their "đặt giờ" affordance. */}
                  {timed.map((a) => <TimelineRow key={a.id} a={a} />)}
                  {anytime.length > 0 && (
                    <div className="trk-anytime-head" data-testid="timeline-anytime-head">
                      <span className="kicker">Chưa đặt giờ</span>
                      <span className="hint faint" style={{ marginLeft: "auto", fontSize: 10.5 }}>
                        {anytime.length} việc · bấm ⏰ để đưa lên rail
                      </span>
                    </div>
                  )}
                  {anytime.map((a) => <TimelineRow key={a.id} a={a} />)}
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
                notesApi.notes.map((n) => <NoteCard key={n.id} n={n} />)
              )}
            </div>
          </div>
        </div>
      )}

      {/* ===== TRACING-UX3 req4 — streak + 12-week history: ALWAYS-VISIBLE "pro" panel
              (no more collapse-by-default). Prominent current + best streak stat tiles, a
              clearer 12-week heatmap (bigger cells, week columns, day labels, legend). ===== */}
      {status === "ready" && (
        <div className="panel" data-testid="tracing-stats" style={{ marginTop: 14 }}>
          <div className="phead">
            <span className="kicker">Streak &amp; lịch sử 12 tuần</span>
          </div>
          <div style={{ padding: "12px 16px 16px" }}>
            {/* prominent streak stat tiles */}
            <div className="trk-streak-tiles" data-testid="streak-tiles">
              <div className="trk-streak-tile" data-testid="streak-current">
                <span className="trk-streak-num num">🔥 {currentStreak}</span>
                <span className="trk-streak-lbl">streak hiện tại {streakBadge(currentStreak)}</span>
              </div>
              <div className="trk-streak-tile" data-testid="streak-best">
                <span className="trk-streak-num num">✦ {sc.topStreak}</span>
                <span className="trk-streak-lbl">streak tốt nhất</span>
              </div>
            </div>

            {/* the 12-week heatmap — bigger cells, week columns, day labels, legend */}
            <div className="heatmap-wrap trk-hm" style={{ marginTop: 14 }}>
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

            {/* per-activity streak list — kept, secondary (below the headline + heatmap) */}
            {acts.length > 0 && (
              <div className="hm-acts" data-testid="streak-list" style={{ marginTop: 14 }}>
                {acts.map((a) => (
                  <div className="hma-row" key={a.id} data-testid={`streak-${a.id}`}>
                    <span style={{ fontSize: 12, flex: 1 }}>{a.name}</span>
                    <span className="num" style={{ fontSize: 11.5, color: "var(--accent)" }}>{a.streak}d streak {streakBadge(a.streak)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* #137 — the template-SET modal (list/edit/import/reset). */}
      {tplModalOpen && (
        <TemplateSetsModal channels={channels} onClose={() => setTplModalOpen(false)} onImported={onTemplateImported} />
      )}
    </section>
  );
}
