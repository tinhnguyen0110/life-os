import { apiGet } from "./_client";
import type {
  ApiResponse,
  MarketData,
} from "@/lib/types";

/** S8 — market view (quotes + triggers + macro + alertHistory). */
export function getMarket(): Promise<ApiResponse<MarketData>> {
  return apiGet<MarketData>("/market");
}
