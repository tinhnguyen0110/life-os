import { apiGet } from "./_client";
import type {
  ApiResponse,
  GraveyardStats,
} from "@/lib/types";

/** S4 — graveyard (abandoned projects + pattern stats + lessons). */
export function getGraveyard(): Promise<ApiResponse<GraveyardStats>> {
  return apiGet<GraveyardStats>("/graveyard");
}
