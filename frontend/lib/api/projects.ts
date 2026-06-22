import { apiGet, apiPost } from "./_client";
import type {
  ApiResponse,
  HealthData,
  ProjectDevActivity,
  ProjectStatus,
  ProjectsListData,
} from "@/lib/types";

/** Sprint 0 — health probe (drives the TopBar "API live" pill). */
export function getHealth(): Promise<ApiResponse<HealthData>> {
  return apiGet<HealthData>("/health");
}
/** S2 — all tracked, non-abandoned projects + health summary. #113: pass
 *  includeHidden to also surface soft-hidden projects (for the "đã ẩn" view). */
export function getProjects(includeHidden = false): Promise<ApiResponse<ProjectsListData>> {
  return apiGet<ProjectsListData>(`/projects${includeHidden ? "?include=hidden" : ""}`);
}
/** S3 — one project by id (includes abandoned). 404 → ApiError(404). */
export function getProject(id: string): Promise<ApiResponse<ProjectStatus>> {
  return apiGet<ProjectStatus>(`/projects/${encodeURIComponent(id)}`);
}
/** #113 — soft-hide a project from the default list (≠ abandon). Returns the project. */
export function hideProject(id: string): Promise<ApiResponse<ProjectStatus>> {
  return apiPost<ProjectStatus>(`/projects/${encodeURIComponent(id)}/hide`);
}
/** #113 — un-hide a soft-hidden project. Returns the project. */
export function unhideProject(id: string): Promise<ApiResponse<ProjectStatus>> {
  return apiPost<ProjectStatus>(`/projects/${encodeURIComponent(id)}/unhide`);
}
/** #112 — per-project git dev-activity. found:false → not in the scan (honest untracked,
 *  NOT real 0s) — the caller renders "chưa track git" + the reason. */
export function getProjectDevActivity(id: string, days = 90): Promise<ApiResponse<ProjectDevActivity>> {
  return apiGet<ProjectDevActivity>(`/projects/${encodeURIComponent(id)}/dev-activity?days=${days}`);
}
/** S4 — un-graveyard a project (POST /projects/{id}/restore). 404 if unknown. */
export function restoreProject(id: string): Promise<ApiResponse<ProjectStatus>> {
  return apiPost<ProjectStatus>(`/projects/${encodeURIComponent(id)}/restore`);
}
