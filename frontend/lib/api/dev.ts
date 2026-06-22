import { apiGet, apiPost } from "./_client";
import type {
  ApiResponse,
  CodeInsight,
  DevActivityOverview,
  DevScanResult,
  RepoMemory,
} from "@/lib/types";

/** GET /dev_activity?days=N — the dev-activity board (default 90 days).
 *  honest-empty "you" when DEV_TRACING_EMAILS unset (summary all-0 + everything
 *  in otherRepos + a warning). */
export function getDevActivity(days = 90): Promise<ApiResponse<DevActivityOverview>> {
  return apiGet<DevActivityOverview>(`/dev_activity?days=${days}`);
}
/** POST /dev_activity/scan?days=N — re-scan the tracked repos now. Returns the
 *  scan result (scannedRepos/rowsUpserted/yourCommits/warnings). */
export function scanDevActivity(days = 90): Promise<ApiResponse<DevScanResult>> {
  return apiPost<DevScanResult>(`/dev_activity/scan?days=${days}`);
}

/* ----------------------------------------------------------------------------
   #64 Repo Memory (REPOMEM) — render-only reads. code_insight = a fresh-now git
   read; code_insight/memory = the durable curated note. Both honest-empty
   (found:false → empty-state, never crash). */
/** GET /code_insight?repo=<name|path> — a fresh structural read of a repo
 *  (structure/README/recentCommits/stack/asOf). found:false → not found/readable. */
export function getCodeInsight(repo: string): Promise<ApiResponse<CodeInsight>> {
  return apiGet<CodeInsight>(`/code_insight?repo=${encodeURIComponent(repo)}`);
}
/** GET /code_insight/memory?repo=<name> — the durable repo_memory note (the
 *  Repos/<name> wiki note). found:false + note:null → no note yet for this repo. */
export function getRepoMemory(repo: string): Promise<ApiResponse<RepoMemory>> {
  return apiGet<RepoMemory>(`/code_insight/memory?repo=${encodeURIComponent(repo)}`);
}

/* ----------------------------------------------------------------------------
   #6/#88 MCP key scoping CRUD (#86, FROZEN). Per-key tool visibility. */
