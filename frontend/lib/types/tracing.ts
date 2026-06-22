/** An activity's TODAY rollup (Σ of today's VN-day sessions). */
export interface TracingToday {
  /** today's Σval ≥ goal. */
  done: boolean;
  /** Σ of today's sessions' val. */
  val: number;
  /** Σ today duration, "Hh Mm" / "Mm" (e.g. "5m", "1h 20m"). */
  dur: string;
  /** Σ today duration in minutes. */
  durMin: number;
  /** the latest today session's note, else null. */
  note: string | null;
  /** today's progress toward goal, 0-100 (backend-clamped). */
  pct: number;
  /** count of today's sessions. */
  sessions: number;
}
/** One activity with its backend-derived views (the GET /tracing activities[] item
 *  and the POST log response). */
export interface ActivityView {
  id: string;
  name: string;
  emoji: string;
  icon: string;
  unit: string;
  /** daily target in the activity's unit. */
  goal: number;
  /** hex accent for the card/bars. */
  color: string;
  today: TracingToday;
  /** consecutive goal-met VN-days (today-at-risk does NOT break it). */
  streak: number;
  /** last 7 VN-days Σval, Mon→Sun (index 6 = today). */
  week: number[];
  /** last 84 VN-days (12w×7) Σval, oldest→newest. */
  history12w: number[];
  /** #75: HH:MM (VN local) to nudge a reminder for this habit, null = no reminder.
   *  CAMEL wire (tracing module convention). OPTIONAL/defensive — absent pre-#75-BE. */
  remindAt?: string | null;
  /** #75: the nudge cadence. "off" / absent ⇒ no reminder. */
  remindRepeat?: RemindRepeat;
  /** #111 / #136: the reminder delivery channel (in_app/email/discord). The BE
   *  ActivityView carries it; the per-card reminder editor reads/writes it. */
  remindChannel?: RemindChannel;
  /** #136 G3-(ii): a HH:MM scheduled time-of-day, INDEPENDENT of the reminder (a time
   *  with no reminder firing). The timeline rails by `time` (fallback remindAt). */
  time?: string | null;
}
/** #75 — a habit's reminder-nudge cadence. */
export type RemindRepeat = "daily" | "weekdays" | "off";
/** The day's score panel (backend-computed roll-up). */
export interface TracingScore {
  /** number of active (non-archived) activities. */
  total: number;
  /** how many met their goal today. */
  done: number;
  /** done/total as 0-100. */
  pct: number;
  /** Σ today all sessions' dur, "Hh Mm". */
  timeActive: string;
  /** best streak across all activities. */
  topStreak: number;
}
/** GET /tracing → the whole habit board (render-only). honest-empty: 0 activities
 *  → activities:[], heatmap12w all-0, score all-0. */
export interface TracingOverview {
  /** today's VN-day, "YYYY-MM-DD". */
  date: string;
  activities: ActivityView[];
  /** 84 cells (12w×7), per-day COUNT of activities that MET their goal that VN-day
   *  (0..total — NOT a boolean, NOT capped at 4). oldest→newest. */
  heatmap12w: number[];
  score: TracingScore;
}
/* ============================================================================
   #109 Tracing templates — pre-made activity presets. The picker prefills the add
   form (id/name/goal/unit/emoji/color) so the user doesn't define a habit from scratch.
   8 seed by default; user overrides/adds via PUT, removes/hides via DELETE/bulk.
   Mirrors the FROZEN #109-BE shape. source="seed" (default) | "user" (overridden/added).
   ============================================================================ */
export interface TracingTemplate {
  id: string;
  name: string;
  /** target value (e.g. 8 ly nước). */
  goal: number;
  unit: string;
  emoji: string;
  /** an icon key (BE-side; may be ""). */
  icon: string;
  /** hex accent for the chip. */
  color: string;
  source: "seed" | "user";
}
/** GET /tracing/templates → the template list. */
export interface TracingTemplateList {
  templates: TracingTemplate[];
}
/** PUT /tracing/templates/{id} body — upsert a user template/override. */
export interface TracingTemplateInput {
  name: string;
  goal: number;
  unit: string;
  emoji: string;
  color: string;
}
/* ============================================================================
   #137 Template SETS — a "mẫu" = a saved LIST of rich activities (a reusable routine),
   NOT the #109 1-word chips. 1-click import creates today's activities (each goal=1,
   carrying its time + reminder). Mirrors the FROZEN #137-T1 BE shape (verified live).
   ============================================================================ */
/** One member of a template set — a rich activity preset (content + time + reminder). */
export interface TemplateMember {
  /** the activity name (1-120, non-blank). */
  content: string;
  /** HH:MM VN scheduled time, or null = no time. */
  time: string | null;
  /** "off"/"daily"/"weekdays" — the member's reminder cadence (default off). */
  remindRepeat: RemindRepeat;
  /** in_app/email/discord — the reminder channel (default in_app). */
  remindChannel: RemindChannel;
}
/** A saved template set = a named ordered LIST of member-activities. */
export interface TemplateSet {
  /** server-set id (slug). */
  id: string;
  /** the set's display name (1-80). */
  name: string;
  activities: TemplateMember[];
}
/** GET /tracing/template-sets → the set list. */
export interface TemplateSetList {
  sets: TemplateSet[];
}
/** POST/PUT body — create/replace a set. id server-set on create; PUT = whole-set replace.
 *  blank name / blank member content / bad time → 422. */
export interface TemplateSetInput {
  name: string;
  activities: TemplateMember[];
}
/** POST /tracing/template-sets/{id}/import response — 1-click import the WHOLE set →
 *  today's activities. created = the new ActivityViews (goal=1, time/reminder preset);
 *  skipped = member contents that were already present (honest, no dup). */
export interface TemplateImportResult {
  created: ActivityView[];
  skipped: string[];
}
/** POST /tracing/{id}/log body — one raw session. val<0 → 422. */
export interface TracingLogInput {
  val: number;
  dur_min?: number | null;
  note?: string | null;
}
/** POST /tracing/activities body — define a new activity. dup id → 409, blank/neg → 422.
 *  #75: remindAt/remindRepeat are CAMEL-case on the wire — the tracing module's
 *  convention (durMin/topStreak), team-lead/architect decision. Sending remindAt is
 *  all the FE does — the BE creates the linked reminder (one-way tracing→reminder
 *  sync; FE does NOT create it). */
export interface ActivityInput {
  id: string;
  name: string;
  goal: number;
  unit?: string;
  emoji?: string;
  icon?: string;
  color?: string;
  /** HH:MM VN local to nudge, null/absent = no reminder. [#75] */
  remindAt?: string | null;
  /** "off"/absent = no reminder. [#75] */
  remindRepeat?: RemindRepeat;
  /** #111 — which channel the linked reminder fires on (default in_app). CAMEL wire,
   *  like remindAt. Only relevant when remindAt is set. */
  remindChannel?: RemindChannel;
  /** #136 G3-(ii) — a HH:MM scheduled time, independent of the reminder. */
  time?: string | null;
}
/** #111 — a reminder delivery channel. in_app always available; email/discord depend
 *  on config. Mirrors GET /reminders/channels ids. */
export type RemindChannel = "in_app" | "email" | "discord";
/** One channel option (GET /reminders/channels). available=false → disabled in the UI
 *  ("chưa cấu hình"). in_app is always available. */
export interface ReminderChannelOption {
  id: RemindChannel;
  label: string;
  available: boolean;
}
/** GET /reminders/channels → the selectable channels. */
export interface ReminderChannelList {
  channels: ReminderChannelOption[];
}
/** PUT /tracing/activities/{id} body — partial edit (all fields optional). */
export interface ActivityPatch {
  name?: string;
  goal?: number;
  unit?: string;
  emoji?: string;
  icon?: string;
  color?: string;
  /** #75 — set/clear the habit's reminder (CAMEL wire). null clears it. */
  remindAt?: string | null;
  remindRepeat?: RemindRepeat;
  /** #111 / #136 — the reminder delivery channel (in_app/email/discord). The BE
   *  ActivityUpdate accepts it; the FE per-card reminder picker sends it. */
  remindChannel?: RemindChannel;
  /** #136 G3-(ii) — set/clear a HH:MM scheduled time, independent of the reminder.
   *  null clears it. PUT /tracing/activities/{id} {time}. */
  time?: string | null;
}
/** The bare stored activity (POST/PUT activities response — NOT the derived view).
 *  #75: remindAt/remindRepeat OPTIONAL/defensive (absent pre-#75-BE). */
export interface Activity {
  id: string;
  name: string;
  emoji: string;
  icon: string;
  unit: string;
  goal: number;
  color: string;
  created: string;
  archived: boolean;
  remindAt?: string | null;
  remindRepeat?: RemindRepeat;
}
/* ============================================================================
   #121 / #122 Tracing day-notes — a day-note = text + optional 🔔-remind. A note WITH
   a remind (remindAt + remindRepeat≠"off") drives a linked reminder (source
   "tracing-note", the #75 wire + #111 channel); clearing/deleting removes it.
   Mirrors the FROZEN backend tracing/schema.py Note/NoteInput/NoteUpdate (verified live:
   GET/POST/PUT/DELETE /tracing/notes → {id,text,remindAt,remindRepeat,remindChannel,created}).
   Named Tracing* to avoid collision with the wiki `NoteInput` (a different module).
   ============================================================================ */
/** GET /tracing/notes list item + the create/update echo (the FROZEN Note shape). */
export interface TracingNote {
  /** the note id (autoincrement PK, stringified). */
  id: string;
  text: string;
  /** HH:MM VN reminder time, or null = no reminder. CAMEL wire (tracing convention). */
  remindAt: string | null;
  /** #125 — YYYY-MM-DD future date for a ONE-SHOT remind (a repeat="once" reminder at
   *  remindDate@remindAt). null = the recurring (#121) remindRepeat path instead. */
  remindDate: string | null;
  /** "off"/absent ⇒ no recurring reminder. */
  remindRepeat: RemindRepeat;
  /** #111 — which channel the linked reminder fires on (default in_app). */
  remindChannel: RemindChannel;
  /** ISO-8601 (VN) when the note was created. */
  created: string;
}
/** POST /tracing/notes body — create a day-note. id/created server-set. blank text → 422.
 *  #125: pass remindDate (future YYYY-MM-DD) + remindAt for a ONE-SHOT; OR remindAt +
 *  remindRepeat (daily/weekdays) for a RECURRING reminder. A past remindDate → 422. */
export interface TracingNoteInput {
  text: string;
  remindAt?: string | null;
  /** #125 — future YYYY-MM-DD for a one-shot remind (with remindAt). Past → 422. */
  remindDate?: string | null;
  remindRepeat?: RemindRepeat;
  remindChannel?: RemindChannel;
}
/** PUT /tracing/notes/{id} body — partial update; only supplied fields change. To CLEAR
 *  the remind pass remindRepeat:"off" (the linked reminder is then deleted). */
export interface TracingNoteUpdate {
  text?: string;
  remindAt?: string | null;
  /** #125 — future YYYY-MM-DD for a one-shot remind. */
  remindDate?: string | null;
  remindRepeat?: RemindRepeat;
  remindChannel?: RemindChannel;
}
/** GET /tracing/notes → the day-note list (honest-empty: {notes: []}). */
export interface TracingNoteList {
  notes: TracingNote[];
}

/* ---- Dev Activity (#63 · DEVACT) — git-contribution tracing ----
   Mirrors the FROZEN backend dev_activity/schema.py (P1). "what did I code, which
   project, when" derived FROM git (commits/LOC/active-span per date×repo). RENDER-ONLY:
   the BE computes everything. "you" = commits attributed via DEV_TRACING_EMAILS;
   everything else is "other" (team context, NOT in your totals). LOC is informational
   (Goodhart) — secondary, NOT the headline. */
