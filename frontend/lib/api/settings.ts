import { apiGet, apiPatch } from "./_client";
import type {
  ApiResponse,
  AppConfig,
  AppConfigPatch,
} from "@/lib/types";

/** S12 — full resolved global app-config. */
export function getSettings(): Promise<ApiResponse<AppConfig>> {
  return apiGet<AppConfig>("/settings");
}
/** S12 — partial config update (only provided keys). Bad field → ApiError(422) with
 *  .fieldErrors() per-field. Returns the new full config (refetch-after-write). */
export function patchSettings(patch: AppConfigPatch): Promise<ApiResponse<AppConfig>> {
  return apiPatch<AppConfig>("/settings", patch);
}
