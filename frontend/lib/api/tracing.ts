import { apiGet, apiPost, apiPut, apiDelete } from "./_client";
import type {
  Activity,
  ActivityInput,
  ActivityPatch,
  ActivityView,
  ApiResponse,
  TemplateImportResult,
  TemplateSet,
  TemplateSetInput,
  TemplateSetList,
  TracingLogInput,
  TracingNote,
  TracingNoteInput,
  TracingNoteList,
  TracingNoteUpdate,
  TracingOverview,
  TracingTemplate,
  TracingTemplateInput,
  TracingTemplateList,
} from "@/lib/types";

/** GET /tracing — the whole habit board (date + activities + heatmap12w + score).
 *  honest-empty when 0 activities (activities:[], heatmap all-0, score all-0). */
export function getTracing(): Promise<ApiResponse<TracingOverview>> {
  return apiGet<TracingOverview>("/tracing");
}
/** Log a session against an activity (POST /tracing/{id}/log). val<0 → ApiError(422)
 *  with .fieldErrors().val. Returns the activity's UPDATED ActivityView (re-render). */
export function logTracingSession(id: string, body: TracingLogInput): Promise<ApiResponse<ActivityView>> {
  return apiPost<ActivityView>(`/tracing/${encodeURIComponent(id)}/log`, body);
}
/** #136 — UN-TICK: clear TODAY's logged sessions for an activity → today.done=false (the
 *  tick-toggle un-complete). BE FROZE the shape (architect decision (a)): DELETE
 *  /tracing/{id}/sessions?date=<today-VN> (date defaults to today server-side) →
 *  {activityId, date, deletedSessions}. 404 unknown. The caller refetches /tracing. */
export function untickActivity(id: string): Promise<ApiResponse<{ activityId: string; date: string; deletedSessions: number }>> {
  return apiDelete<{ activityId: string; date: string; deletedSessions: number }>(`/tracing/${encodeURIComponent(id)}/sessions`);
}
/** Add an activity (POST /tracing/activities). Dup id → ApiError(409); blank/neg → 422.
 *  Returns the bare Activity (caller refetches GET /tracing for the derived board). */
export function createActivity(body: ActivityInput): Promise<ApiResponse<Activity>> {
  return apiPost<Activity>("/tracing/activities", body);
}
/** Partial edit (PUT /tracing/activities/{id}). 404 if unknown, 422 on bad field. */
export function updateActivity(id: string, body: ActivityPatch): Promise<ApiResponse<Activity>> {
  return apiPut<Activity>(`/tracing/activities/${encodeURIComponent(id)}`, body);
}
/** Archive an activity (DELETE /tracing/activities/{id}). SOFT — the card disappears,
 *  its logged sessions survive. Returns {archived:id}. 404 if unknown. */
export function archiveActivity(id: string): Promise<ApiResponse<{ archived: string }>> {
  return apiDelete<{ archived: string }>(`/tracing/activities/${encodeURIComponent(id)}`);
}

/* ---- #109 Tracing templates — activity presets that prefill the add form ---- */
/** GET /tracing/templates — the preset list (8 seed by default + any user overrides). */
export function getTracingTemplates(): Promise<ApiResponse<TracingTemplateList>> {
  return apiGet<TracingTemplateList>("/tracing/templates");
}
/** PUT /tracing/templates/{id} — upsert a user template/override. Returns the saved one. */
export function upsertTracingTemplate(id: string, body: TracingTemplateInput): Promise<ApiResponse<TracingTemplate>> {
  return apiPut<TracingTemplate>(`/tracing/templates/${encodeURIComponent(id)}`, body);
}
/** DELETE /tracing/templates/{id} — remove a user template / tombstone-hide a seed.
 *  Returns {deleted, changed}. */
export function deleteTracingTemplate(id: string): Promise<ApiResponse<{ deleted: string; changed: boolean }>> {
  return apiDelete<{ deleted: string; changed: boolean }>(`/tracing/templates/${encodeURIComponent(id)}`);
}
/** POST /tracing/templates/reset — back to the 8 pure seed (drops user overrides/hides).
 *  Returns {reset, count}. */
export function resetTracingTemplates(): Promise<ApiResponse<{ reset: boolean; count: number }>> {
  return apiPost<{ reset: boolean; count: number }>("/tracing/templates/reset", {});
}
/** POST /tracing/templates/bulk-delete — remove/hide many (idempotent). Returns {deleted}. */
export function bulkDeleteTracingTemplates(ids: string[]): Promise<ApiResponse<{ deleted: number }>> {
  return apiPost<{ deleted: number }>("/tracing/templates/bulk-delete", { ids });
}

/* ---- #124 "+ Từ mẫu" — add a saved template → today's activity (todo, goal=1, tickable) ---- */
/** POST /tracing/templates/{id}/add — 1-click add a saved template to today. Returns
 *  {activity, added}; added=false when an activity with that id already exists (idempotent,
 *  returns the existing — no dup). 404 if the template id is unknown. */
export function addTemplateToToday(id: string): Promise<ApiResponse<{ activity: Activity; added: boolean }>> {
  return apiPost<{ activity: Activity; added: boolean }>(`/tracing/templates/${encodeURIComponent(id)}/add`, {});
}
/** POST /tracing/templates/add-all — add ALL non-hidden templates to today in one call.
 *  Returns {created:[Activity], skipped:[ids]} (already-present ids are skipped, honest). */
export function addAllTemplates(): Promise<ApiResponse<{ created: Activity[]; skipped: string[] }>> {
  return apiPost<{ created: Activity[]; skipped: string[] }>("/tracing/templates/add-all", {});
}

/* ---- #137 Template SETS — a "mẫu" = a saved LIST of rich activities (a routine) ----
   Mirrors the FROZEN #137-T1 BE shape. The chip CRUD above stays (dormant, REST/MCP
   parity); these SETS are a separate surface. */
/** GET /tracing/template-sets — all saved template sets. */
export function getTemplateSets(): Promise<ApiResponse<TemplateSetList>> {
  return apiGet<TemplateSetList>("/tracing/template-sets");
}
/** POST /tracing/template-sets — create a set. 201 + the set (server-set id). blank name /
 *  blank member content / bad time → 422. */
export function createTemplateSet(body: TemplateSetInput): Promise<ApiResponse<TemplateSet>> {
  return apiPost<TemplateSet>("/tracing/template-sets", body);
}
/** PUT /tracing/template-sets/{id} — whole-set replace (name + members). 404 unknown. */
export function updateTemplateSet(id: string, body: TemplateSetInput): Promise<ApiResponse<TemplateSet>> {
  return apiPut<TemplateSet>(`/tracing/template-sets/${encodeURIComponent(id)}`, body);
}
/** DELETE /tracing/template-sets/{id} — remove a set. {deleted}. 404 unknown. */
export function deleteTemplateSet(id: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/tracing/template-sets/${encodeURIComponent(id)}`);
}
/** POST /tracing/template-sets/{id}/import — 1-click import the WHOLE set → today's
 *  activities (each goal=1, time/reminder preset). {created:[ActivityView], skipped:[content]}.
 *  404 unknown. After this, REFETCH GET /tracing (the board updates). */
export function importTemplateSet(id: string): Promise<ApiResponse<TemplateImportResult>> {
  return apiPost<TemplateImportResult>(`/tracing/template-sets/${encodeURIComponent(id)}/import`, {});
}
/** POST /tracing/template-sets/reset — discard all + re-seed the default ("Buổi sáng").
 *  Returns {sets:[the default(s)]}. */
export function resetTemplateSets(): Promise<ApiResponse<TemplateSetList>> {
  return apiPost<TemplateSetList>("/tracing/template-sets/reset", {});
}

/* ---- #121 / #122 Tracing day-notes — text + optional 🔔-remind (note→reminder link) ---- */
/** GET /tracing/notes — all day-notes, newest-first. honest-empty {notes: []}. */
export function getTracingNotes(): Promise<ApiResponse<TracingNoteList>> {
  return apiGet<TracingNoteList>("/tracing/notes");
}
/** POST /tracing/notes — create a day-note (text + optional remind). 201 + the Note.
 *  A note WITH remindAt + remindRepeat≠"off" links a reminder (BE-side). blank text → 422. */
export function createTracingNote(body: TracingNoteInput): Promise<ApiResponse<TracingNote>> {
  return apiPost<TracingNote>("/tracing/notes", body);
}
/** PUT /tracing/notes/{id} — partial update; only supplied fields change. To CLEAR the
 *  remind pass remindRepeat:"off". Returns the updated Note. 404 if unknown id. */
export function updateTracingNote(id: string, body: TracingNoteUpdate): Promise<ApiResponse<TracingNote>> {
  return apiPut<TracingNote>(`/tracing/notes/${encodeURIComponent(id)}`, body);
}
/** DELETE /tracing/notes/{id} — remove the note (+ its linked reminder). {deleted:id}. 404 if unknown. */
export function deleteTracingNote(id: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/tracing/notes/${encodeURIComponent(id)}`);
}

/* ---- Dev Activity (#63 · DEVACT) — git-contribution tracing ----
   Backend REST is shipped + FROZEN (P1); FE consumes only. Errors are the
   post-#46/#70 {error:{code,message,hint}} shape (errorFromBody/ApiError). */
