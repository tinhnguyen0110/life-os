import { apiGet, apiPost, apiPut } from "./_client";
import type {
  ApiResponse,
  JournalEntry,
  JournalInput,
  JournalStats,
} from "@/lib/types";

/** S7 — journal (entries + performance/calibration stats). */
export function getJournal(): Promise<ApiResponse<JournalStats>> {
  return apiGet<JournalStats>("/journal");
}
/** S7 — record a trade (POST /journal). */
export function createJournal(body: JournalInput): Promise<ApiResponse<JournalEntry>> {
  return apiPost<JournalEntry>("/journal", body);
}
/** S7 — update/close an entry (PUT /journal/{id}; close = set pnl/outcome/lesson). */
export function updateJournal(id: string, body: JournalInput): Promise<ApiResponse<JournalEntry>> {
  return apiPut<JournalEntry>(`/journal/${encodeURIComponent(id)}`, body);
}
