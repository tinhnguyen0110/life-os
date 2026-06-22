import { apiGet, apiPost, apiPatch } from "./_client";
import type {
  ActivityFeed,
  ActivityRun,
  ApiResponse,
  RoutineInfo,
  RoutinesView,
  RunResultView,
} from "@/lib/types";

/** S13 — routines view (catalog + run_log stats + roll-up). */
export function getRoutines(): Promise<ApiResponse<RoutinesView>> {
  return apiGet<RoutinesView>("/routines");
}
/** S14 — activity feed (run_log projection + stats). Optional status/range filters. */
export function getActivity(opts?: { status?: string; range?: string }): Promise<ApiResponse<ActivityFeed>> {
  const qs = new URLSearchParams();
  if (opts?.status) qs.set("status", opts.status);
  if (opts?.range) qs.set("range", opts.range);
  const q = qs.toString();
  return apiGet<ActivityFeed>(`/activity${q ? `?${q}` : ""}`);
}
/** S14 — one run by its run_log PK. 404 if absent. */
export function getActivityRun(id: number): Promise<ApiResponse<ActivityRun>> {
  return apiGet<ActivityRun>(`/activity/${id}`);
}
/** S13 — toggle a routine enabled (PATCH /routines/{id}). */
export function toggleRoutine(id: string, enabled: boolean): Promise<ApiResponse<RoutineInfo>> {
  return apiPatch<RoutineInfo>(`/routines/${encodeURIComponent(id)}`, { enabled });
}
/** S13 — run a routine now (POST /routines/{id}/run → recorded run). */
export function runRoutine(id: string): Promise<ApiResponse<RunResultView>> {
  return apiPost<RunResultView>(`/routines/${encodeURIComponent(id)}/run`);
}
