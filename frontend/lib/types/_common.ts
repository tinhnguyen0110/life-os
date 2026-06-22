/** C4 — every endpoint answers this envelope (ROADMAP §6). */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  warning?: string;
}
/** /health payload (Sprint 0). */
export interface HealthData {
  status: string;
  modules: string[];
}
/** One FastAPI validation error item (PATCH 422 → { detail: ValidationErrorItem[] }).
 *  loc is ["body", <fieldName>, ...]; loc[1] names the offending field. */
export interface ValidationErrorItem {
  type: string;
  loc: (string | number)[];
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

