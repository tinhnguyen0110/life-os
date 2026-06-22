import { apiGet, apiPost, apiPut, apiDelete } from "./_client";
import type {
  ApiResponse,
  DecisionAllocation,
  DecisionCreateInput,
  DecisionEntry,
  DecisionGuardian,
  DecisionJournalData,
  DecisionPatchInput,
  DecisionWeight,
  MacroCycle,
  NavHistory,
} from "@/lib/types";

/** List decisions + derived calibration/bias stats (brier/bands/biasFlags embedded). */
export function getDecisionJournal(): Promise<ApiResponse<DecisionJournalData>> {
  return apiGet<DecisionJournalData>("/decision-journal");
}
/** Log a new decision (confidence REQUIRED). Throws ApiError(422) on bad confidence/empty. */
export function createDecision(body: DecisionCreateInput): Promise<ApiResponse<DecisionEntry>> {
  return apiPost<DecisionEntry>("/decision-journal", body);
}
/** Partial update / resolve — `{status:"resolved", outcome:"right"}` resolves without
 *  resending required fields. Throws ApiError on bad body / 404. */
export function updateDecision(id: string, body: DecisionPatchInput): Promise<ApiResponse<DecisionEntry>> {
  return apiPut<DecisionEntry>(`/decision-journal/${encodeURIComponent(id)}`, body);
}
/** Delete a decision. 404 if unknown. */
export function deleteDecision(id: string): Promise<ApiResponse<DecisionEntry>> {
  return apiDelete<DecisionEntry>(`/decision-journal/${encodeURIComponent(id)}`);
}

/* ---- Career cockpit (CAR-1) — living CV + blog manager + demo showcase ---- */
/** GET /decision/weight — decision-weight gauge (W = ∏ layer-q + verdict + confidence). */
export function getDecisionWeight(): Promise<ApiResponse<DecisionWeight>> {
  return apiGet<DecisionWeight>("/decision/weight");
}
/** GET /decision/macro-cycle — Investment-Clock phase + axes + the cycle q. */
export function getMacroCycle(): Promise<ApiResponse<MacroCycle>> {
  return apiGet<MacroCycle>("/decision/macro-cycle");
}
/** GET /decision/allocation — REFERENCE weighting (clock + capital tier), surfaced as DATA. */
export function getDecisionAllocation(): Promise<ApiResponse<DecisionAllocation>> {
  return apiGet<DecisionAllocation>("/decision/allocation");
}
/** GET /decision/guardian — risk QUESTIONS (alerts[].msg are questions, not advice). */
export function getDecisionGuardian(): Promise<ApiResponse<DecisionGuardian>> {
  return apiGet<DecisionGuardian>("/decision/guardian");
}
/** GET /decision/nav-history — NAV series (short-series warning + low confidence honest). */
export function getNavHistory(from?: string, to?: string): Promise<ApiResponse<NavHistory>> {
  const qs = new URLSearchParams();
  if (from) qs.set("from", from);
  if (to) qs.set("to", to);
  const q = qs.toString();
  return apiGet<NavHistory>(`/decision/nav-history${q ? `?${q}` : ""}`);
}

/* ---- Reminders (#27–#31 · GAP-4) — the user-facing tick screen ----
   Backend REST is shipped + FROZEN; FE consumes only (no backend change). */
