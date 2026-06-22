import { markWikiTreeStale } from "@/lib/wikiTreeBus";
import { apiGet, apiPost, apiPut, apiDelete } from "./_client";
import type {
  ApiResponse,
  WikiBacklinks,
  WikiBatchAcceptInput,
  WikiBatchAcceptResult,
  WikiBulkDeleteResult,
  WikiCitationVerifyInput,
  WikiCitationVerifyResult,
  WikiClusterList,
  WikiConflictList,
  WikiConflictResolveInput,
  WikiDecideInput,
  WikiFolderCreateInput,
  WikiFolderCreateResult,
  WikiFolderDeleteResult,
  WikiFolderMoveResult,
  WikiGraph,
  WikiImportInput,
  WikiImportResponse,
  WikiInbox,
  WikiMocList,
  WikiNote,
  WikiNoteCreateInput,
  WikiNoteUpdateInput,
  WikiOverview,
  WikiProposal,
  WikiProposalList,
  WikiProposalStatus,
  WikiSearchHit,
  WikiSoftDeleteResult,
  WikiTrash,
  WikiTree,
} from "@/lib/types";

/** W2 — one wiki note by integer id. 404 → ApiError(404). */
export function getWikiNote(id: number): Promise<ApiResponse<WikiNote>> {
  return apiGet<WikiNote>(`/wiki/notes/${id}`);
}
/** W3 capture — create a (default fleeting) wiki note. Returns the created note.
 *  #108: bumps the wiki-tree bus on success so the Explorer count reflects the new
 *  note's folder (a create into a NEW folder otherwise left the Explorer stale). */
export function createWikiNote(body: WikiNoteCreateInput): Promise<ApiResponse<WikiNote>> {
  return apiPost<WikiNote>("/wiki/notes", body).then(bumpTree);
}
/** #93 import — POST /wiki/import. Multi-file, FAIL-SOFT: the response carries a
 *  per-file {ok, noteId, title, error}; a bad file (wrong ext / empty) returns
 *  ok:false + an agent-error (code/message/hint), it does NOT fail the whole call.
 *  #108: bumps the tree bus on success (imported notes can land in new folders). */
export function importWiki(body: WikiImportInput): Promise<ApiResponse<WikiImportResponse>> {
  return apiPost<WikiImportResponse>("/wiki/import", body).then(bumpTree);
}
/** W2 edit — partial update (PUT /wiki/notes/{id}). Bad enum → ApiError(422) per-field.
 *  #108: bumps the tree bus on success (a `folder` change moves the note between
 *  folders → both old + new counts change). */
export function updateWikiNote(id: number, body: WikiNoteUpdateInput): Promise<ApiResponse<WikiNote>> {
  return apiPut<WikiNote>(`/wiki/notes/${id}`, body).then(bumpTree);
}
/** #94 SOFT-delete a wiki note → moves to trash (recoverable via restore). Returns
 *  `{deleted, deletedAt}`. Inbound links become ghost server-side. 404 if unknown.
 *  #108: bumps the tree bus (the note leaves its folder → count drops). */
export function deleteWikiNote(id: number): Promise<ApiResponse<WikiSoftDeleteResult>> {
  return apiDelete<WikiSoftDeleteResult>(`/wiki/notes/${id}`).then(bumpTree);
}
/** #94 GET /wiki/trash — the soft-deleted notes (newest-deleted-first) + count. */
export function getWikiTrash(): Promise<ApiResponse<WikiTrash>> {
  return apiGet<WikiTrash>("/wiki/trash");
}
/** #94 POST /wiki/notes/{id}/restore — bring a soft-deleted note back. Returns the note.
 *  #108: bumps the tree bus (the restored note re-enters its folder → count rises). */
export function restoreWikiNote(id: number): Promise<ApiResponse<WikiNote>> {
  return apiPost<WikiNote>(`/wiki/notes/${id}/restore`, {}).then(bumpTree);
}
/** #94 POST /wiki/notes/bulk-delete — soft-delete many. FAIL-SOFT: per-id results
 *  ({id, ok, error}); a bad id returns ok:false + agent-error, doesn't fail the batch.
 *  #108: bumps the tree bus on success (the deleted notes leave their folders). */
export function bulkDeleteWikiNotes(ids: number[]): Promise<ApiResponse<WikiBulkDeleteResult>> {
  return apiPost<WikiBulkDeleteResult>("/wiki/notes/bulk-delete", { ids }).then(bumpTree);
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

/* ---- #127 W3 — wiki folder lifecycle ops (the dev work-dir; REST/FE-only, not MCP).
   All bump the tree bus so the Explorer refetches. The W1 FROZEN contracts. ---- */
/** POST /wiki/folders — create a (possibly nested) folder. A nested path ("A/B/C")
 *  nests through each segment (the empty-folder anchor). dup → 409, empty → 422. */
export function createWikiFolder(body: WikiFolderCreateInput): Promise<ApiResponse<WikiFolderCreateResult>> {
  return apiPost<WikiFolderCreateResult>("/wiki/folders", body).then(bumpTree);
}
/** DELETE /wiki/folders/{path} — SCOPED soft-delete the subtree (recoverable). 🔴 observe
 *  "gone" via the refreshed /wiki/tree, NOT get_note (still returns the tombstone). 422 on root. */
export function deleteWikiFolder(path: string): Promise<ApiResponse<WikiFolderDeleteResult>> {
  return apiDelete<WikiFolderDeleteResult>(`/wiki/folders/${encodeWikiPath(path)}`).then(bumpTree);
}
/** PUT /wiki/folders/{path}/move — re-prefix the subtree to `to`. 409 target-exists, 422 into-own-subtree. */
export function moveWikiFolder(path: string, to: string): Promise<ApiResponse<WikiFolderMoveResult>> {
  return apiPut<WikiFolderMoveResult>(`/wiki/folders/${encodeWikiPath(path)}/move`, { to }).then(bumpTree);
}
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

/** #108 helper — mark the wiki tree stale (the Explorer refetches its counts) then pass
 *  the response through unchanged. Only runs on a RESOLVED (successful) write; a throw
 *  skips it (the tree didn't change). */
function bumpTree<T>(res: T): T {
  markWikiTreeStale();
  return res;
}

/** encode a "/"-delimited folder path for the URL WITHOUT escaping the slashes (the BE
 *  route is {path:path} = a catch-all; each SEGMENT is encoded, the slashes are kept). */
function encodeWikiPath(path: string): string {
  return path.split("/").map(encodeURIComponent).join("/");
}
