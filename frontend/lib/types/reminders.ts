/** repeat policy — STORED on the reminder; only the #29 notify routine acts on it. */
export type ReminderRepeat = "once" | "daily" | "weekly";
/** The stored reminder (GET /reminders[].* and POST/PUT/tick response data). */
export interface Reminder {
  id: number;
  title: string;
  note: string | null;
  /** ISO-8601 UTC the reminder is due (echoed +00:00, UTC-normalized at write). */
  due_at: string;
  repeat: ReminderRepeat;
  /** minutes between re-notifies (#29), null = single notify. */
  re_notify_every: number | null;
  /** max notify count (#29), null = uncapped. */
  max_times: number | null;
  /** times notified so far this period (#29). */
  notified_count: number;
  /** ISO of the last notify, else null (#29). */
  last_notified: string | null;
  /** ISO when ticked done, else null. done_at != null = the reminder is resolved. */
  done_at: string | null;
  /** ISO-8601 created timestamp. */
  created: string;
  /** un-done AND due_at < now (NOT cap-gated, reader-derived #29). Drives RED. */
  overdue: boolean;
  /** #75: "manual" (user-created) or "tracing" (auto from a habit's nudge). absent
   *  pre-#75-BE → treat as "manual" (no badge). */
  source?: ReminderSource;
  /** #75: the linked activity id when source="tracing", else null/absent. SNAKE on the
   *  wire — the reminders module is pure snake_case (due_at/done_at), so this field is
   *  `activity_id` to stay consistent WITHIN the module (team-lead decision, not camel). */
  activity_id?: string | null;
}
/** #75 — where a reminder came from. */
export type ReminderSource = "manual" | "tracing";
/** POST /reminders body. due_at unparseable / blank title → 422 (no row stored). */
export interface ReminderInput {
  title: string;
  note?: string | null;
  /** ISO-8601 datetime the reminder is due (required). */
  due_at: string;
  repeat?: ReminderRepeat;
  re_notify_every?: number | null;
  max_times?: number | null;
}
/** GET /reminders?filter=… response data. The 4 SERVER filters are
 *  today|week|undone|all (NO server `done` filter — the UI's "Done" view is a
 *  render-only client filter over `all` where done_at != null). */
export interface ReminderList {
  reminders: Reminder[];
  count: number;
  /** how many in this list are un-done (done_at null). */
  undoneCount: number;
  /** the filter the server applied (today|week|undone|all). */
  filter: string;
}

/* ---- Daily Tracing (#65 · G-HABIT) — the day-to-day life-logging module ----
   Mirrors the FROZEN backend tracing/schema.py (P1/P2). RENDER-ONLY: the backend
   computes ALL derived metrics (streak, pct, week, history, heatmap, score) over
   VN-day buckets — the FE displays them + POSTs raw sessions, never recomputes. */
