import { apiGet, apiPost, apiPut, apiDelete } from "./_client";
import type {
  ApiResponse,
  Reminder,
  ReminderChannelList,
  ReminderInput,
  ReminderList,
} from "@/lib/types";

/** List reminders by filter. SERVER filters: today|week|undone|all (unknown →
 *  lenient all). The UI "Done" view fetches `all` + client-filters done_at!=null —
 *  there is NO server `done` filter. Empty → {reminders:[], count:0, …}. */
export function getReminders(
  filter: "today" | "week" | "undone" | "all" = "all",
): Promise<ApiResponse<ReminderList>> {
  return apiGet<ReminderList>(`/reminders?filter=${encodeURIComponent(filter)}`);
}
/** #111 GET /reminders/channels — the selectable reminder channels (in_app/email/
 *  discord) + whether each is available (configured). in_app always available. */
export function getReminderChannels(): Promise<ApiResponse<ReminderChannelList>> {
  return apiGet<ReminderChannelList>("/reminders/channels");
}
/** Create a reminder. 201 + the created reminder. Blank title / unparseable due_at
 *  → ApiError(422) with .fieldErrors() per-field (surface it; no optimistic add). */
export function createReminder(body: ReminderInput): Promise<ApiResponse<Reminder>> {
  return apiPost<Reminder>("/reminders", body);
}
/** Tick a reminder done (PUT /reminders/{id}/tick). IDEMPOTENT — re-tick keeps the
 *  first done_at. 200 + the reminder (done_at set, overdue→false). 404 if absent. */
export function tickReminder(id: number): Promise<ApiResponse<Reminder>> {
  return apiPut<Reminder>(`/reminders/${id}/tick`);
}
/** Delete a reminder (DELETE /reminders/{id}). 200 + {deleted:id}. 404 if absent. */
export function deleteReminder(id: number): Promise<ApiResponse<{ deleted: number }>> {
  return apiDelete<{ deleted: number }>(`/reminders/${id}`);
}

/* ---- Daily Tracing (#65 · G-HABIT) — the habit board ----
   Backend REST is shipped + FROZEN (P1/P2); FE consumes only (no backend change).
   Errors are the post-#46/#70 {error:{code,message,hint,retryable}} shape — handled
   centrally by errorFromBody/ApiError above. */
