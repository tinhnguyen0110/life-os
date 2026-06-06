/* ============================================================
   API client — single entry to the FastAPI backend (C4).
   Every endpoint returns { success, data, warning? } (ApiResponse<T>).
   No auth (single-user, localhost). Sprint 0: only /health is live.
   ============================================================ */
import type {
  ApiResponse,
  HealthData,
  ProjectStatus,
  ProjectsListData,
  FinanceOverview,
  ChannelDetail,
  MarketData,
  ClaudeUsage,
  GraveyardStats,
  JournalStats,
  JournalEntry,
  JournalInput,
  RoutinesView,
  RoutineInfo,
  RunResultView,
  ActivityFeed,
  ActivityRun,
  Brief,
  AppConfig,
  AppConfigPatch,
  ValidationErrorItem,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  /** FastAPI 422 validation detail[] (loc:["body",<field>], msg, ...) when present —
   *  lets a form map per-field errors. Empty/undefined for non-422 errors. */
  detail?: ValidationErrorItem[];
  constructor(status: number, message: string, detail?: ValidationErrorItem[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** field → first error message, for per-field form echo. Reads loc[1] as the field. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const d of this.detail ?? []) {
      const field = typeof d.loc?.[1] === "string" ? (d.loc[1] as string) : undefined;
      if (field && !(field in out)) out[field] = d.msg;
    }
    return out;
  }
}

/** Build an ApiError from a non-2xx body. Handles FastAPI 422 where `detail` is an
 *  ARRAY of {loc,msg,...} (per-field) AND the simpler {detail|message: string} case —
 *  the array is carried on ApiError.detail so a form can echo per field. */
function errorFromBody(url: string, status: number, parsed: unknown): ApiError {
  const detailRaw = (parsed as { detail?: unknown })?.detail;
  if (Array.isArray(detailRaw)) {
    const items = detailRaw as ValidationErrorItem[];
    const msg = items.map((i) => `${i.loc?.[1] ?? "?"}: ${i.msg}`).join("; ") || `Validation failed (${status})`;
    return new ApiError(status, msg, items);
  }
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

/** Sprint 0 — health probe (drives the TopBar "API live" pill). */
export function getHealth(): Promise<ApiResponse<HealthData>> {
  return apiGet<HealthData>("/health");
}

/** S2 — all tracked, non-abandoned projects + health summary. */
export function getProjects(): Promise<ApiResponse<ProjectsListData>> {
  return apiGet<ProjectsListData>("/projects");
}

/** S3 — one project by id (includes abandoned). 404 → ApiError(404). */
export function getProject(id: string): Promise<ApiResponse<ProjectStatus>> {
  return apiGet<ProjectStatus>(`/projects/${encodeURIComponent(id)}`);
}

/** S5 — finance overview (totalValue + allocations + dryPowder + pnlTotal). */
export function getFinance(): Promise<ApiResponse<FinanceOverview>> {
  return apiGet<FinanceOverview>("/finance");
}

/** S6 — one channel's detail (alloc + priced holdings + ladder). 404 if unknown. */
export function getChannelDetail(channel: string): Promise<ApiResponse<ChannelDetail>> {
  return apiGet<ChannelDetail>(`/finance/${encodeURIComponent(channel)}`);
}

/** S8 — market view (quotes + triggers + macro + alertHistory). */
export function getMarket(): Promise<ApiResponse<MarketData>> {
  return apiGet<MarketData>("/market");
}

/** S9 — Claude token usage (gauge + series + byModel + cost; resetIn/byProject stubs). */
export function getClaudeUsage(): Promise<ApiResponse<ClaudeUsage>> {
  return apiGet<ClaudeUsage>("/claude-usage");
}

/** S4 — graveyard (abandoned projects + pattern stats + lessons). */
export function getGraveyard(): Promise<ApiResponse<GraveyardStats>> {
  return apiGet<GraveyardStats>("/graveyard");
}

/** S7 — journal (entries + performance/calibration stats). */
export function getJournal(): Promise<ApiResponse<JournalStats>> {
  return apiGet<JournalStats>("/journal");
}

/** S13 — routines view (catalog + run_log stats + roll-up). */
export function getRoutines(): Promise<ApiResponse<RoutinesView>> {
  return apiGet<RoutinesView>("/routines");
}

/** S14 — activity feed (run_log projection + stats). Optional status/range filters. */
export function getActivity(opts?: { status?: string; range?: string }): Promise<ApiResponse<ActivityFeed>> {
  const qs = new URLSearchParams();
  if (opts?.status) qs.set("status", opts.status);
  if (opts?.range) qs.set("range", opts.range);
  const q = qs.toString();
  return apiGet<ActivityFeed>(`/activity${q ? `?${q}` : ""}`);
}

/** S14 — one run by its run_log PK. 404 if absent. */
export function getActivityRun(id: number): Promise<ApiResponse<ActivityRun>> {
  return apiGet<ActivityRun>(`/activity/${id}`);
}

/** S11 — today's daily brief (template roll-up + severity-ordered priorities). */
export function getBrief(): Promise<ApiResponse<Brief>> {
  return apiGet<Brief>("/brief");
}

/** S11 — past persisted briefs (newest-first). [] if none. */
export function getBriefHistory(): Promise<ApiResponse<Brief[]>> {
  return apiGet<Brief[]>("/brief/history");
}

/** S12 — full resolved global app-config. */
export function getSettings(): Promise<ApiResponse<AppConfig>> {
  return apiGet<AppConfig>("/settings");
}

/** S12 — partial config update (only provided keys). Bad field → ApiError(422) with
 *  .fieldErrors() per-field. Returns the new full config (refetch-after-write). */
export function patchSettings(patch: AppConfigPatch): Promise<ApiResponse<AppConfig>> {
  return apiPatch<AppConfig>("/settings", patch);
}

/** S13 — toggle a routine enabled (PATCH /routines/{id}). */
export function toggleRoutine(id: string, enabled: boolean): Promise<ApiResponse<RoutineInfo>> {
  return apiPatch<RoutineInfo>(`/routines/${encodeURIComponent(id)}`, { enabled });
}

/** S13 — run a routine now (POST /routines/{id}/run → recorded run). */
export function runRoutine(id: string): Promise<ApiResponse<RunResultView>> {
  return apiPost<RunResultView>(`/routines/${encodeURIComponent(id)}/run`);
}

/** S7 — record a trade (POST /journal). */
export function createJournal(body: JournalInput): Promise<ApiResponse<JournalEntry>> {
  return apiPost<JournalEntry>("/journal", body);
}

/** S7 — update/close an entry (PUT /journal/{id}; close = set pnl/outcome/lesson). */
export function updateJournal(id: string, body: JournalInput): Promise<ApiResponse<JournalEntry>> {
  return apiPut<JournalEntry>(`/journal/${encodeURIComponent(id)}`, body);
}

/** S4 — un-graveyard a project (POST /projects/{id}/restore). 404 if unknown. */
export function restoreProject(id: string): Promise<ApiResponse<ProjectStatus>> {
  return apiPost<ProjectStatus>(`/projects/${encodeURIComponent(id)}/restore`);
}

export const apiBase = BASE;
