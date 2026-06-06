/* ============================================================
   API client — single entry to the FastAPI backend (C4).
   Every endpoint returns { success, data, warning? } (ApiResponse<T>).
   No auth (single-user, localhost). Sprint 0: only /health is live.
   ============================================================ */
import type { ApiResponse, HealthData } from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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
    const msg =
      (body as { detail?: string; message?: string })?.detail ||
      (body as { message?: string })?.message ||
      `Request to ${url} failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as ApiResponse<T>;
}

/** Sprint 0 — health probe (drives the TopBar "API live" pill). */
export function getHealth(): Promise<ApiResponse<HealthData>> {
  return apiGet<HealthData>("/health");
}

export const apiBase = BASE;
