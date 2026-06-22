import { apiGet } from "./_client";
import type {
  ApiResponse,
  Brief,
} from "@/lib/types";

/** S11 — today's daily brief (template roll-up + severity-ordered priorities). */
export function getBrief(): Promise<ApiResponse<Brief>> {
  return apiGet<Brief>("/brief");
}
/** S11 — past persisted briefs (newest-first). [] if none. */
export function getBriefHistory(): Promise<ApiResponse<Brief[]>> {
  return apiGet<Brief[]>("/brief/history");
}
