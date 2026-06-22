/* API client HTTP core — split from lib/api.ts (#138-P3, pure move).
   The shared fetch wrappers + ApiError + base URL. Every domain file imports from here. */
import type {
  ApiResponse,
  ValidationErrorItem,
} from "@/lib/types";


// In-container the compose env sets NEXT_PUBLIC_API_BASE=:8686. The fallback is for
// bare-metal dev → MUST be life-os BE :8686 (NOT :8000 = OutboundOS, a different app;
// the old :8000 default silently 404'd wiki calls bare-metal). [W1-FE, architect-requested]
const BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8686";

export class ApiError extends Error {
  status: number;
  /** FastAPI 422 validation detail[] (loc:["body",<field>], msg, ...) when present —
   *  lets a form map per-field errors. Empty/undefined for non-422 errors. LEGACY
   *  shape; the agent-error shape (#46/#70) carries per-field info in `message`
   *  ("body.<field>: <msg>") and is parsed into `_fields` instead. */
  detail?: ValidationErrorItem[];
  /** Agent-error code (#46) — e.g. NOT_FOUND / INVALID_INPUT. undefined for legacy. */
  code?: string;
  /** Agent-error remediation hint (#46) — "GET /reminders for valid ids". */
  hint?: string;
  /** Agent-error retryable flag (#46) — true if the caller can safely retry. */
  retryable?: boolean;
  /** Per-field map parsed from an agent-error `message` ("body.<field>: <msg>"),
   *  the #46/#70 replacement for the legacy loc-array. undefined when none parsed. */
  private _fields?: Record<string, string>;

  constructor(
    status: number,
    message: string,
    opts?: {
      detail?: ValidationErrorItem[];
      code?: string;
      hint?: string;
      retryable?: boolean;
      fields?: Record<string, string>;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = opts?.detail;
    this.code = opts?.code;
    this.hint = opts?.hint;
    this.retryable = opts?.retryable;
    this._fields = opts?.fields;
  }

  /** field → first error message, for per-field form echo. Reads BOTH the new
   *  agent-error per-field map (parsed from `message`) AND the legacy loc-array
   *  (loc[1] = field), so forms keep working across both error shapes. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = { ...(this._fields ?? {}) };
    for (const d of this.detail ?? []) {
      const field = typeof d.loc?.[1] === "string" ? (d.loc[1] as string) : undefined;
      if (field && !(field in out)) out[field] = d.msg;
    }
    return out;
  }
}

/** Parse per-field errors out of an agent-error message. The #46/P7 validation
 *  handler formats a field as "<loc>.<field>: <msg>" (loc ∈ body|path|query),
 *  embedded in a prose lead-in ("request validation failed — body.title: <msg>").
 *  Real BE today reports the FIRST failing field only, but if it ever joins several
 *  with "; " we map them all. The field-prefix is matched ANYWHERE in each segment
 *  (not anchored), so the prose lead-in doesn't defeat it. Returns {field: msg};
 *  empty when no "<loc>.<field>:" pattern is present (so a plain message → no fields). */
function parseFieldsFromMessage(message: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const part of message.split(";")) {
    const m = part.match(/(?:body|path|query)\.(\w+):\s*(.+?)\s*$/);
    if (m && !(m[1] in out)) out[m[1]] = m[2];
  }
  return out;
}

/** Build an ApiError from a non-2xx body. Handles THREE shapes, newest first:
 *   1. Agent-error (#46): {error:{code,message,hint,retryable}} — the current BE
 *      contract. message carries per-field info ("body.<field>: <msg>") which we
 *      parse into ApiError so fieldErrors() still works (no loc-array anymore).
 *   2. LEGACY FastAPI 422: {detail:[{loc,msg,...}]} — per-field loc-array.
 *   3. LEGACY simple: {detail:"..."} or {message:"..."} string.
 *  Falls through to a generic message only when NOTHING usable is present (so a
 *  malformed/empty error body never crashes the caller). */
function errorFromBody(url: string, status: number, parsed: unknown): ApiError {
  // (1) Agent-error shape {error:{...}} — read it FIRST (current BE contract).
  const errObj = (parsed as { error?: unknown })?.error;
  if (errObj && typeof errObj === "object") {
    const e = errObj as { code?: unknown; message?: unknown; hint?: unknown; retryable?: unknown };
    const message = typeof e.message === "string" && e.message ? e.message : `Request to ${url} failed (${status})`;
    const fields = parseFieldsFromMessage(message);
    return new ApiError(status, message, {
      code: typeof e.code === "string" ? e.code : undefined,
      hint: typeof e.hint === "string" ? e.hint : undefined,
      retryable: typeof e.retryable === "boolean" ? e.retryable : undefined,
      fields: Object.keys(fields).length ? fields : undefined,
    });
  }

  // (2) Legacy FastAPI 422 — detail is a loc-array.
  const detailRaw = (parsed as { detail?: unknown })?.detail;
  if (Array.isArray(detailRaw)) {
    const items = detailRaw as ValidationErrorItem[];
    const msg = items.map((i) => `${i.loc?.[1] ?? "?"}: ${i.msg}`).join("; ") || `Validation failed (${status})`;
    return new ApiError(status, msg, { detail: items });
  }

  // (3) Legacy simple {detail:"..."} / {message:"..."} / generic fallback.
  const msg =
    (typeof detailRaw === "string" ? detailRaw : undefined) ||
    (parsed as { message?: string })?.message ||
    `Request to ${url} failed (${status})`;
  return new ApiError(status, msg);
}

/**
 * Core fetch wrapper. Throws ApiError on non-2xx or malformed envelope.
 * Returns the typed ApiResponse<T> (caller reads .data / .warning).
 */
export async function apiGet<T>(
  path: string,
  init?: RequestInit
): Promise<ApiResponse<T>> {
  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers: { Accept: "application/json", ...init?.headers } });
  } catch (e) {
    throw new ApiError(0, `Network error reaching ${url}: ${(e as Error).message}`);
  }
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new ApiError(res.status, `Invalid JSON from ${url} (status ${res.status})`);
  }
  if (!res.ok) {
    throw errorFromBody(url, res.status, body);
  }
  return body as ApiResponse<T>;
}

/**
 * POST wrapper. Same envelope + error handling as apiGet; sends a JSON body.
 * Throws ApiError on non-2xx (caller maps 400/404/409 to UI messaging).
 */
export async function apiPost<T>(
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<ApiResponse<T>> {
  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      ...init,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...init?.headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, `Network error reaching ${url}: ${(e as Error).message}`);
  }
  let parsed: unknown;
  try {
    parsed = await res.json();
  } catch {
    throw new ApiError(res.status, `Invalid JSON from ${url} (status ${res.status})`);
  }
  if (!res.ok) {
    throw errorFromBody(url, res.status, parsed);
  }
  return parsed as ApiResponse<T>;
}

/** PUT wrapper. Same envelope + error handling as apiPost; sends a JSON body. */
export async function apiPut<T>(
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<ApiResponse<T>> {
  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "PUT",
      ...init,
      headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, `Network error reaching ${url}: ${(e as Error).message}`);
  }
  let parsed: unknown;
  try {
    parsed = await res.json();
  } catch {
    throw new ApiError(res.status, `Invalid JSON from ${url} (status ${res.status})`);
  }
  if (!res.ok) {
    throw errorFromBody(url, res.status, parsed);
  }
  return parsed as ApiResponse<T>;
}

/** PATCH wrapper. Same envelope + error handling as apiPost; sends a JSON body. */
export async function apiPatch<T>(
  path: string,
  body?: unknown,
  init?: RequestInit
): Promise<ApiResponse<T>> {
  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "PATCH",
      ...init,
      headers: { Accept: "application/json", "Content-Type": "application/json", ...init?.headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new ApiError(0, `Network error reaching ${url}: ${(e as Error).message}`);
  }
  let parsed: unknown;
  try {
    parsed = await res.json();
  } catch {
    throw new ApiError(res.status, `Invalid JSON from ${url} (status ${res.status})`);
  }
  if (!res.ok) {
    throw errorFromBody(url, res.status, parsed);
  }
  return parsed as ApiResponse<T>;
}

/** DELETE wrapper. Same envelope + error handling as apiGet. */
export async function apiDelete<T>(
  path: string,
  init?: RequestInit
): Promise<ApiResponse<T>> {
  const url = `${BASE}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "DELETE",
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
    });
  } catch (e) {
    throw new ApiError(0, `Network error reaching ${url}: ${(e as Error).message}`);
  }
  let parsed: unknown;
  try {
    parsed = await res.json();
  } catch {
    throw new ApiError(res.status, `Invalid JSON from ${url} (status ${res.status})`);
  }
  if (!res.ok) {
    throw errorFromBody(url, res.status, parsed);
  }
  return parsed as ApiResponse<T>;
}

export const apiBase = BASE;
