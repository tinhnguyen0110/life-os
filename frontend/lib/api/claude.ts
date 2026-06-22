import { apiGet } from "./_client";
import type {
  ApiResponse,
  ClaudeUsage,
} from "@/lib/types";

/** S9 — Claude token usage (gauge + series + byModel + cost; resetIn/byProject stubs). */
export function getClaudeUsage(): Promise<ApiResponse<ClaudeUsage>> {
  return apiGet<ClaudeUsage>("/claude-usage");
}
