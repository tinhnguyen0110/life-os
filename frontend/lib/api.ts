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
  Holding,
  HoldingInput,
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
  ExchangeOverview,
  CryptoBasis,
  WikiNote,
  WikiNoteCreateInput,
  WikiNoteUpdateInput,
  WikiBacklinks,
  WikiInbox,
  WikiOverview,
  WikiSearchHit,
  WikiGraph,
  WikiProposal,
  WikiProposalList,
  WikiProposalStatus,
  WikiDecideInput,
  WikiBatchAcceptInput,
  WikiBatchAcceptResult,
  WikiClusterList,
  WikiMocList,
  WikiTree,
  WikiCitationVerifyInput,
  WikiCitationVerifyResult,
  WikiConflictList,
  WikiConflictResolveInput,
  DecisionJournalData,
  DecisionEntry,
  DecisionCreateInput,
  DecisionPatchInput,
  Cv,
  BlogPost,
  BlogInput,
  DemoItem,
  DemoInput,
  DecisionWeight,
  MacroCycle,
  DecisionAllocation,
  DecisionGuardian,
  NavHistory,
} from "./types";

// In-container the compose env sets NEXT_PUBLIC_API_BASE=:8686. The fallback is for
// bare-metal dev → MUST be life-os BE :8686 (NOT :8000 = OutboundOS, a different app;
// the old :8000 default silently 404'd wiki calls bare-metal). [W1-FE, architect-requested]
const BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8686";

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

/** S6 — add a holding (POST /finance/holdings). Bad field → ApiError(422) per-field.
 *  Returns the created Holding (the caller refetches GET /finance for the new overview). */
export function createHolding(body: HoldingInput): Promise<ApiResponse<Holding>> {
  return apiPost<Holding>("/finance/holdings", body);
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

/** OKX exchange overview (balances + positions). configured=false if no API key. */
export function getExchange(): Promise<ApiResponse<ExchangeOverview>> {
  return apiGet<ExchangeOverview>("/exchange");
}

/** Force a fresh pull from OKX (bypasses in-memory cache). */
export function syncExchange(): Promise<ApiResponse<ExchangeOverview>> {
  return apiPatch<ExchangeOverview>("/exchange/sync");
}

/** Finance — get crypto cost basis (snapshot or manual override). */
export function getCryptoBasis(): Promise<ApiResponse<CryptoBasis>> {
  return apiGet<CryptoBasis>("/finance/crypto-basis");
}

/** #74 change 5 — verify the privacy reveal-pass. The pass lives in BE env (never sent
 *  to the FE); we POST the user's ATTEMPT and read data.ok. Always HTTP 200 (a wrong
 *  pass is data.ok=false, not an error). */
export function verifyPrivacyPass(pass: string): Promise<ApiResponse<{ ok: boolean }>> {
  return apiPost<{ ok: boolean }>("/settings/privacy/verify", { pass });
}

/** Finance — user override for crypto cost basis (PUT /finance/crypto-basis). */
export function setCryptoBasis(basis: number): Promise<ApiResponse<CryptoBasis>> {
  return apiPut<CryptoBasis>("/finance/crypto-basis", { basis });
}

/* ---- Wiki (W1–W5 · integer-ID PKM) — frozen M1 contract (end_sprint_W1c §3) ---- */

/** W2 — one wiki note by integer id. 404 → ApiError(404). */
export function getWikiNote(id: number): Promise<ApiResponse<WikiNote>> {
  return apiGet<WikiNote>(`/wiki/notes/${id}`);
}

/** W3 capture — create a (default fleeting) wiki note. Returns the created note. */
export function createWikiNote(body: WikiNoteCreateInput): Promise<ApiResponse<WikiNote>> {
  return apiPost<WikiNote>("/wiki/notes", body);
}

/** W2 edit — partial update (PUT /wiki/notes/{id}). Bad enum → ApiError(422) per-field. */
export function updateWikiNote(id: number, body: WikiNoteUpdateInput): Promise<ApiResponse<WikiNote>> {
  return apiPut<WikiNote>(`/wiki/notes/${id}`, body);
}

/** Delete a wiki note (inbound links become ghost server-side). 404 if unknown. */
export function deleteWikiNote(id: number): Promise<ApiResponse<WikiNote>> {
  return apiDelete<WikiNote>(`/wiki/notes/${id}`);
}

/** W2 — a note's connections: linked + unlinked mentions + outbound (resolved/ghost). */
export function getWikiBacklinks(id: number): Promise<ApiResponse<WikiBacklinks>> {
  return apiGet<WikiBacklinks>(`/wiki/notes/${id}/backlinks`);
}

/** W3 refine — apply edit + flip status. ≥1-link gate is SERVER-enforced: 0-link &
 *  non-cold-start → ApiError(422) (surface visibly); cold-start → 200 + warning. */
export function refineWikiNote(id: number, body: WikiNoteUpdateInput): Promise<ApiResponse<WikiNote>> {
  return apiPost<WikiNote>(`/wiki/notes/${id}/refine`, body);
}

/** W3 — fleeting notes awaiting triage (oldest→newest). aiSuggest null at M1. */
export function getWikiInbox(): Promise<ApiResponse<WikiInbox>> {
  return apiGet<WikiInbox>("/wiki/inbox");
}

/** W1 — vault overview (stats + inbox/orphan summaries + op-log + proposalCount).
 *  `warning` carries the empty-vault note on a cold-start vault. */
export function getWikiOverview(): Promise<ApiResponse<WikiOverview>> {
  return apiGet<WikiOverview>("/wiki/overview");
}

/** W1 search box — FTS5 full-text. Empty `q` or no match → data: []. */
export function searchWiki(q: string): Promise<ApiResponse<WikiSearchHit[]>> {
  return apiGet<WikiSearchHit[]>(`/wiki/search?q=${encodeURIComponent(q)}`);
}

/** W4 — ego-graph around `note` (1–2 hops). `depth` defaults to 2. Backend 404s
 *  the note → ApiError(404); FE surfaces the not-found state. */
export function getWikiGraph(
  note: number,
  depth = 2,
): Promise<ApiResponse<WikiGraph>> {
  return apiGet<WikiGraph>(`/wiki/graph?note=${note}&depth=${depth}`);
}

/** GLOBAL-GRAPH — whole-vault graph (GET /wiki/graph with NO note param → global,
 *  per the GLOBAL-GRAPH T1 contract). Same shape as ego ({center:null, nodes, edges,
 *  clusters} over the whole vault). Empty vault → {center:null, nodes:[], …}. */
export function getWikiGraphGlobal(): Promise<ApiResponse<WikiGraph>> {
  return apiGet<WikiGraph>("/wiki/graph");
}

/* ---- P1 Proposal Queue (W4a) — review surface for AI-proposed mutations ---- */

/** List proposals. `status` ∈ pending(default) | accepted | rejected | all.
 *  Response carries `counts` for the filter chips. Empty queue → proposals: []. */
export function getWikiProposals(
  status: WikiProposalStatus | "all" = "pending",
): Promise<ApiResponse<WikiProposalList>> {
  return apiGet<WikiProposalList>(`/wiki/proposals?status=${status}`);
}

/** Accept ONE proposal → applies it via the changes-queue/op-log (→ verified).
 *  Throws ApiError(4xx) with a {detail} message when the apply can't proceed
 *  (e.g. target note missing, malformed payload) — caller surfaces it (fail-closed). */
export function acceptWikiProposal(
  id: number,
  body?: WikiDecideInput,
): Promise<ApiResponse<WikiProposal>> {
  return apiPost<WikiProposal>(`/wiki/proposals/${id}/accept`, body ?? {});
}

/** Reject ONE proposal (remembered — not re-suggested). */
export function rejectWikiProposal(
  id: number,
  body?: WikiDecideInput,
): Promise<ApiResponse<WikiProposal>> {
  return apiPost<WikiProposal>(`/wiki/proposals/${id}/reject`, body ?? {});
}

/** Batch-accept many proposals in one call (P1 queue batch action). `ids` non-empty.
 *  Returns per-id results — the batch can PARTIALLY succeed (200 + accepted>0 AND
 *  failed>0), so the caller must inspect `failed`/`results`, not just the 2xx. */
export function batchAcceptWikiProposals(
  body: WikiBatchAcceptInput,
): Promise<ApiResponse<WikiBatchAcceptResult>> {
  return apiPost<WikiBatchAcceptResult>("/wiki/proposals/accept-batch", body);
}

/* ---- W5 MOC / clusters (W5a substrate) ---- */

/** W5 — detected clusters (MOC candidates), ranked by advisory importance. Empty
 *  when no group meets the size/density threshold (honest — no fabricated clusters). */
export function getWikiClusters(): Promise<ApiResponse<WikiClusterList>> {
  return apiGet<WikiClusterList>("/wiki/clusters");
}

/** W5 — existing MOC notes (noteType="moc"), newest-first. Empty when none ratified. */
export function getWikiMocs(): Promise<ApiResponse<WikiMocList>> {
  return apiGet<WikiMocList>("/wiki/mocs");
}

/** WEXP — virtual folder tree (groups of notes by their `folder` field) for the
 *  explorer pane. Empty vault → groups: []. (WEXP-BE freezes the shape.) */
export function getWikiTree(): Promise<ApiResponse<WikiTree>> {
  return apiGet<WikiTree>("/wiki/tree");
}

/* ---- A1b citation verify + A1a sync conflicts (W7) ---- */

/** Verify a batch of LLM-returned citations (deterministic CODE post-verify): each
 *  claim → verified/weaklyGrounded/rejected/ungrounded + the note it resolves to. */
export function verifyWikiCitations(
  body: WikiCitationVerifyInput,
): Promise<ApiResponse<WikiCitationVerifyResult>> {
  return apiPost<WikiCitationVerifyResult>("/wiki/citations/verify", body);
}

/** List sync conflicts. `status` ∈ open(default) | resolved. Empty → conflicts:[]. */
export function getWikiConflicts(
  status: "open" | "resolved" = "open",
): Promise<ApiResponse<WikiConflictList>> {
  return apiGet<WikiConflictList>(`/wiki/sync/conflicts?status=${status}`);
}

/** Resolve a conflict: write the chosen content THROUGH the single-writer queue +
 *  mark resolved. Throws ApiError(404) if absent/already-resolved/note-gone. */
export function resolveWikiConflict(
  conflictId: number,
  body: WikiConflictResolveInput,
): Promise<ApiResponse<unknown>> {
  return apiPost<unknown>(`/wiki/sync/conflicts/${conflictId}/resolve`, body);
}

/* ---- Decision Journal + Calibration (W7-A2 / F1-H1) ---- */

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

/** The living CV, parsed into header meta + ordered sections (with proof chips). */
export function getCareerCv(): Promise<ApiResponse<Cv>> {
  return apiGet<Cv>("/career/cv");
}

/** The CV's raw markdown (for export / copy). */
export function getCareerCvRaw(): Promise<ApiResponse<{ markdown: string }>> {
  return apiGet<{ markdown: string }>("/career/cv/raw");
}

/** Replace the CV's raw markdown (edit). Returns the re-parsed CV. 422 on empty. */
export function updateCareerCv(markdown: string): Promise<ApiResponse<Cv>> {
  return apiPut<Cv>("/career/cv", { markdown });
}

/** All blog posts, newest-updated first. */
export function getCareerBlog(): Promise<ApiResponse<BlogPost[]>> {
  return apiGet<BlogPost[]>("/career/blog");
}

/** Create a blog post. Bad field → ApiError(422) per-field. */
export function createCareerBlog(body: BlogInput): Promise<ApiResponse<BlogPost>> {
  return apiPost<BlogPost>("/career/blog", body);
}

/** Update a blog post (404 if absent). */
export function updateCareerBlog(id: string, body: BlogInput): Promise<ApiResponse<BlogPost>> {
  return apiPut<BlogPost>(`/career/blog/${encodeURIComponent(id)}`, body);
}

/** Delete a blog post (404 if absent). */
export function deleteCareerBlog(id: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/career/blog/${encodeURIComponent(id)}`);
}

/** All demo / showcase items, newest-updated first. */
export function getCareerDemo(): Promise<ApiResponse<DemoItem[]>> {
  return apiGet<DemoItem[]>("/career/demo");
}

/** Create a demo item. Bad field → ApiError(422) per-field. */
export function createCareerDemo(body: DemoInput): Promise<ApiResponse<DemoItem>> {
  return apiPost<DemoItem>("/career/demo", body);
}

/** Update a demo item (404 if absent). */
export function updateCareerDemo(id: string, body: DemoInput): Promise<ApiResponse<DemoItem>> {
  return apiPut<DemoItem>(`/career/demo/${encodeURIComponent(id)}`, body);
}

/** Delete a demo item (404 if absent). */
export function deleteCareerDemo(id: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/career/demo/${encodeURIComponent(id)}`);
}

/* ---- Decision tower (FINANCE-ASSISTANT P1–P4) — the /decision cockpit ---- */

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

export const apiBase = BASE;
