

/* ============================================================
   Wiki / Knowledge vault (W1–W5) — MIRRORS backend modules/wiki/schema.py
   (Sprint W1a, FROZEN) + the W1c reader shapes (backlinks / inbox). Integer-ID
   PKM notes — SEPARATE from the string-ID `notes` module above. Frozen contract:
   end_sprint_W1c §3 (12 endpoints, envelope {success,data,warning?}).
   AI-derived fields (aiSuggest / suggestions) are null/empty at M1 — M4 (Claude
   Code via MCP) populates them. Render the empty state, never fabricate.
   ============================================================ */
export type WikiStatus = "fleeting" | "developing" | "evergreen";
export type WikiNoteType = "concept" | "literature";
export type WikiTrustTier = "verified" | "candidate";
/** A stored wiki note — mirrors `Note` (GET /wiki/notes/{id}). `id` is the
 *  immutable integer identity; `title` is mutable ("" for a raw fleeting capture).
 *  `contentHash` = sha256 of the body. Timestamps ISO-8601 UTC, server-set. */
export interface WikiNote {
  id: number;
  title: string;
  aliases: string[];
  status: WikiStatus;
  noteType: WikiNoteType;
  trustTier: WikiTrustTier;
  /** "human" | "agent:<name>". */
  author: string;
  tags: string[];
  /** markdown body (may contain `[[id|title]]` wikilinks). */
  content: string;
  created: string;
  updated: string;
  contentHash: string;
  /** #94 soft-delete: ISO timestamp when soft-deleted (in trash), else null/absent. */
  deletedAt?: string | null;
}

/* ============================================================================
   #94 Wiki soft-delete (trash/restore/bulk). Delete is now RECOVERABLE — a deleted
   note moves to the trash (GET /wiki/trash) + can be restored. Mirrors the FROZEN
   #94-BE schema. The "xoá nhầm → rollback" recovery the user asked for.
   ============================================================================ */
/** A trash item (GET /wiki/trash) — a LEAN view of a soft-deleted note (not the full
 *  body; enough to identify + restore). newest-deleted-first. */
export interface WikiTrashItem {
  id: number;
  title: string;
  /** ISO timestamp it was soft-deleted. */
  deletedAt: string;
  folder: string;
}
/** GET /wiki/trash → the soft-deleted notes + count. */
export interface WikiTrash {
  trash: WikiTrashItem[];
  count: number;
}
/** DELETE /wiki/notes/{id} (now SOFT) → confirms the move to trash. */
export interface WikiSoftDeleteResult {
  deleted: number;
  deletedAt: string;
}
/** POST /wiki/notes/bulk-delete body. */
export interface WikiBulkDeleteInput {
  ids: number[];
}
/** Per-id bulk-delete result. ok:false → the agent-error (e.g. NOT_FOUND). FAIL-SOFT. */
export interface WikiBulkDeleteItem {
  id: number;
  ok: boolean;
  error: { code: string; message: string; hint?: string; retryable?: boolean } | null;
}
/** POST /wiki/notes/bulk-delete → per-id results + how many were soft-deleted. */
export interface WikiBulkDeleteResult {
  results: WikiBulkDeleteItem[];
  deletedCount: number;
}
/** POST /wiki/notes body — mirrors `NoteCreateInput`. id/timestamps server-assigned.
 *  A fleeting capture legitimately has no title; links/title come at REFINE. */
export interface WikiNoteCreateInput {
  content?: string;
  title?: string;
  status?: WikiStatus;
  noteType?: WikiNoteType;
  tags?: string[];
  author?: string;
  /** command_bar | quick_add | mcp_agent | daily_note (free-form; default quick_add). */
  captureSource?: string;
  /** #127-W3A — the virtual folder this note is created in ("" = root). The BE
   *  NoteCreateInput accepts it (verified live). Lets "＋ Note mới" land in a folder. */
  folder?: string;
}
/** PUT /wiki/notes/{id} (+ POST .../refine) body — mirrors `NoteUpdateInput`.
 *  Partial: a field left undefined is unchanged; a present field overwrites.
 *  Bad enum value → per-field 422 (ApiError.fieldErrors()). */
export interface WikiNoteUpdateInput {
  title?: string;
  content?: string;
  status?: WikiStatus;
  noteType?: WikiNoteType;
  trustTier?: WikiTrustTier;
  aliases?: string[];
  tags?: string[];
  /** WEXP: virtual folder path ("/"-delimited). Move = set this (no .md rewrite).
   *  Optional; the WEXP-BE PUT accepts it once that lands. */
  folder?: string;
}
/** One inbound linked mention (GET /wiki/notes/{id}/backlinks → linked[]). The
 *  `snippet` is body text around the mention, may carry `<b>`-highlight HTML.
 *  `anchor` = the `^block-id` the mention sits in, when present. */
export interface WikiLinkedMention {
  id: number;
  title: string;
  snippet: string;
  anchor?: string;
}
/** One unlinked mention (backlinks → unlinked[]) — a note that names this title/
 *  alias in prose but hasn't linked it (FTS-derived; "link nó" candidate). */
export interface WikiUnlinkedMention {
  id: number;
  title: string;
  snippet: string;
}
/** One outbound edge (backlinks → outbound[]). Resolved → {id,title,isResolved:true};
 *  ghost (target note doesn't exist yet) → {ghost,isResolved:false}. Discriminate
 *  on `isResolved` / presence of `id` vs `ghost`. */
export type WikiOutboundLink =
  | { id: number; title: string; isResolved: true; ghost?: undefined }
  | { ghost: string; isResolved: false; id?: undefined };
/** GET /wiki/notes/{id}/backlinks — mirrors reader.backlinks (W1c). */
export interface WikiBacklinks {
  linked: WikiLinkedMention[];
  unlinked: WikiUnlinkedMention[];
  outbound: WikiOutboundLink[];
}
/** One inbox (fleeting) item — mirrors reader.inbox (W1c). `aiSuggest` is null at
 *  M1 (no embedded AI); the shape is kept so M4 slots in unchanged. */
export interface WikiInboxItem {
  id: number;
  /** null = no title yet (raw fleeting capture). */
  title: string | null;
  status: WikiStatus;
  /** body snippet of the raw capture. */
  rawContent: string;
  /** ISO/display capture time. */
  captured: string;
  /** command_bar | quick_add | mcp_agent | daily_note. */
  captureSource: string;
  /** outbound resolved-link count (drives the ≥1-link refine gate, server-enforced). */
  linkCount: number;
  /** null at M1 — M4 populates {titleClaim,summary,atomicityFlag,dupeOf}. */
  aiSuggest: WikiAiSuggest | null;
}
/** GET /wiki/inbox payload — mirrors reader.inbox. */
export interface WikiInbox {
  items: WikiInboxItem[];
}

/* ============================================================================
   #93 Wiki import — POST /wiki/import. Multi-file, FAIL-SOFT: each file gets its own
   {ok, noteId, title, error}; a bad file doesn't block the good ones. Mirrors the
   FROZEN #93-BE schema. The agent-error shape is the post-#46/#70 {code,message,hint}.
   ============================================================================ */
/** One file to import — filename (for ext/type) + the raw text content (read client-
 *  side via FileReader, or pasted). */
export interface WikiImportFile {
  filename: string;
  content: string;
}
/** POST /wiki/import body. */
export interface WikiImportInput {
  files: WikiImportFile[];
}
/** Per-file result. ok:true → noteId+title; ok:false → error (agent-readable). */
export interface WikiImportResult {
  filename: string;
  ok: boolean;
  noteId: number | null;
  title: string | null;
  /** the agent-error when ok:false (unsupported ext / empty / etc.), else null. */
  error: { code: string; message: string; hint?: string; retryable?: boolean } | null;
}
/** POST /wiki/import response data — per-file results + how many notes were created. */
export interface WikiImportResponse {
  imported: WikiImportResult[];
  createdCount: number;
}
/** AI refine suggestion for an inbox item — null at M1, M4 populates. */
export interface WikiAiSuggest {
  titleClaim: string;
  summary: string;
  atomicityFlag: string;
  dupeOf: { id: number; title: string; similarity: number } | null;
}
/** One AI link-suggestion (GET /wiki/notes/{id}/suggestions). EMPTY at M1 (no
 *  embedded AI) — render the empty state, M4 populates via Claude Code. */
export interface WikiSuggestion {
  id: number;
  title: string;
  why: string;
  confidence: number;
  state: "candidate" | "accepted" | "rejected" | "pinned";
}

/* ---- W1 Vault Overview (GET /wiki/overview) — mirrors reader.overview ---- */
/** op-log op kind. M1 emits create/edit/link/refine/merge/delete; the agent kinds
 *  (link_candidate/moc_proposal) are in the enum for M4 but never produced now. */
export type WikiOpKind =
  | "create" | "edit" | "link" | "link_candidate"
  | "refine" | "merge" | "moc_proposal" | "delete";
/** Vault-wide counters. `pctWithLink` is null on an empty vault (no denominator). */
export interface WikiVaultStats {
  totalNotes: number;
  byStatus: { fleeting: number; developing: number; evergreen: number };
  totalLinks: number;
  orphanCount: number;
  ghostLinkCount: number;
  /** % of notes with ≥1 link; null when totalNotes==0 (avoid div-by-zero). */
  pctWithLink: number | null;
  asOf: string;
}
/** One orphan-sweep row (degree-0 / stale note). */
export interface WikiOrphan {
  id: number;
  title: string | null;
  status: WikiStatus;
  degree: number;
  lastTouched: string;
}
/** One op-log activity row (recentActivity[], newest→oldest). `detail`/`noteTitle`
 *  may be empty/null. `actor` = human | agent (agent never auto-writes at M1). */
export interface WikiActivity {
  ts: string;
  op: WikiOpKind;
  actor: "human" | "agent";
  noteId: number;
  noteTitle: string;
  detail: string | null;
}
/** GET /wiki/overview payload — mirrors reader.overview. `inbox`/`orphans` are
 *  short summaries (full lists live on W3 / W4). `proposalCount` is 0 at M1. */
export interface WikiOverview {
  stats: WikiVaultStats;
  inbox: WikiInboxItem[];
  orphans: WikiOrphan[];
  recentActivity: WikiActivity[];
  proposalCount: number;
}

/* ---- W4 Graph Explorer (GET /wiki/graph?note=X&depth=N) — mirrors reader.graph ---- */
/** One graph node. The API does NOT carry x/y — the FE computes a radial ego-layout
 *  client-side (center fixed, neighbors on rings by hop distance). */
export interface WikiGraphNode {
  id: number;
  title: string;
  status: WikiStatus;
  degree: number;
}
/** One typed edge. `type` ∈ relates|supports|contradicts|refines|example_of (M1
 *  typed graph). `isResolved=false` = ghost target (note not yet created). */
export interface WikiGraphEdge {
  source: number;
  target: number;
  type: string;
  isResolved: boolean;
}
/** One AI-detected cluster (MOC candidate). EMPTY at M1 (no embedded clustering);
 *  the shape is kept so M4/W5 slot in unchanged. */
export interface WikiGraphCluster {
  label: string;
  noteIds: number[];
  density: number;
  mocSuggestion: boolean;
}
/** GET /wiki/graph payload — mirrors reader.graph. Ego-graph around `center`.
 *  `clusters` uses the SAME shape the backend ego-graph emits (reader.detect_clusters
 *  → {members, size, density, importance, suggestedTitle}) — NOT the stale
 *  WikiGraphCluster ({label, noteIds}), which the backend never returns. */
export interface WikiGraph {
  /** ego center note id; null for the GLOBAL (whole-vault) graph. */
  center: number | null;
  nodes: WikiGraphNode[];
  edges: WikiGraphEdge[];
  clusters: WikiCluster[];
}
/** One FTS5 search hit (GET /wiki/search?q=). EMPTY array when no match. */
export interface WikiSearchHit {
  id: number;
  title: string | null;
  status: WikiStatus;
  snippet: string;
}

/* ---- P1 Proposal Queue (W4a) — MIRRORS backend modules/wiki/proposals_schema.py.
   The single review surface for every AI-proposed mutation. Trust boundary: AI
   write-back ALWAYS lands here as `pending` first; a human accepts/rejects — AI
   NEVER edits an evergreen note's body in place. ---- */
/** Proposal kind enum — frozen W4a (proposals_schema.ProposalKind). NOT the mock's
 *  aspirational link_candidate/moc_proposal set; build to the live contract. */
export type WikiProposalKind =
  | "note_create" | "note_edit" | "link_add" | "link_remove" | "merge" | "moc";
/** pending → accepted | rejected (terminal). */
export type WikiProposalStatus = "pending" | "accepted" | "rejected";
/** One stored proposal (GET /wiki/proposals → data.proposals[]). `payload` is a
 *  kind-specific dict (note_edit→{title?,content?,status?,...} · link_add→{target,display?}
 *  · merge→{sourceId,targetId} · …) rendered generically. `decided*`/`appliedNoteId`
 *  are set only once a human decides; `appliedNoteId` deep-links the applied note. */
export interface WikiProposal {
  id: number;
  kind: WikiProposalKind;
  /** the note the proposal acts on (edit/merge target); null for some link/create. */
  targetId: number | null;
  payload: Record<string, unknown>;
  rationale: string;
  /** "agent" | "agent:<name>" | "human". */
  actor: string;
  status: WikiProposalStatus;
  correlationId: string | null;
  created: string;
  decided: string | null;
  decidedBy: string | null;
  appliedNoteId: number | null;
}
/** GET /wiki/proposals payload — mirrors reader. `counts` drives the queue badge /
 *  filter chips. `proposals: []` on an empty queue (honest empty, never null). */
export interface WikiProposalList {
  proposals: WikiProposal[];
  counts: Partial<Record<WikiProposalStatus, number>>;
}
/** Accept/reject body (DecideInput) — `decidedBy` defaults to "human" server-side. */
export interface WikiDecideInput {
  decidedBy?: string;
}
/** Batch-accept body (BatchAcceptInput). `ids` must be non-empty. */
export interface WikiBatchAcceptInput {
  ids: number[];
  decidedBy?: string;
}
/** One per-id result from POST /wiki/proposals/accept-batch. `ok=false` carries
 *  `error` (e.g. "not found" / apply-failed); `ok=true` carries the applied proposal. */
export interface WikiBatchAcceptResultItem {
  id: number;
  ok: boolean;
  proposal?: WikiProposal;
  error?: string;
}
/** POST /wiki/proposals/accept-batch response. A batch can PARTIALLY succeed
 *  (200 envelope with accepted>0 AND failed>0) — the UI must surface failed, not
 *  treat the 200 as all-success. */
export interface WikiBatchAcceptResult {
  results: WikiBatchAcceptResultItem[];
  accepted: number;
  failed: number;
}

/* ---- W5 SYNTHESIZE / MOC (W5a) — MIRRORS backend reader.clusters / reader.mocs.
   Substrate only: clusters are detected by CODE (graph community detection,
   deterministic, NO vector/AI); MOC drafting + throughline + contradiction are the
   EXTERNAL Claude Code (MCP) job (ARCH §11, D-W5.4) — this screen lists the substrate
   + hints "ask Claude Code to draft", it does NOT fabricate an AI workspace. ---- */
/** One cluster member (id + title). title null = untitled note. */
export interface WikiClusterMember {
  id: number;
  title: string | null;
}
/** One detected cluster = MOC candidate (GET /wiki/clusters → data.clusters[]).
 *  `importance` = size×density is ADVISORY (D-W5.3) — ranks candidates, never gates.
 *  `suggestedTitle` is a deterministic hint, NOT an AI-generated title. */
export interface WikiCluster {
  members: WikiClusterMember[];
  size: number;
  density: number;
  importance: number;
  suggestedTitle: string | null;
}
/** GET /wiki/clusters payload. Empty = no cluster meets the size/density threshold. */
export interface WikiClusterList {
  clusters: WikiCluster[];
}
/** One MOC note (GET /wiki/mocs → data.items[]) — a noteType="moc" note. */
export interface WikiMoc {
  id: number;
  title: string | null;
  status: WikiStatus;
  created: string;
  updated: string;
  outboundLinks: number;
}
/** GET /wiki/mocs payload. Empty = no MOC notes yet (none ratified). */
export interface WikiMocList {
  items: WikiMoc[];
}

/* ---- A1b Citation verify (W7) — MIRRORS POST /wiki/citations/verify. The SPEC
   surface (L257): grounded Q&A is EXTERNAL Claude Code (MCP), NOT an in-app chat;
   the FE shows "answered via MCP, N citations verified" + click→note+span. This is
   the verify display, deterministic CODE post-verification of LLM-returned cites. ---- */
/** One claim to verify. `noteId`/`span` null = ungrounded (no citation given). */
export interface WikiCitation {
  claim: string;
  noteId?: number | null;
  span?: string | null;
}
/** POST /wiki/citations/verify body. */
export interface WikiCitationVerifyInput {
  claims: WikiCitation[];
}
/** verified = span found in the cited note · weaklyGrounded = note exists, span
 *  fuzzy/partial · rejected = cited note/span absent · ungrounded = no citation. */
export type WikiCitationStatus = "verified" | "weaklyGrounded" | "rejected" | "ungrounded";
/** One verify result. `resolvedNoteId` = the note the citation actually resolves to
 *  (for click→jump); `reason` = machine code (span_not_in_note / no_citation / …). */
export interface WikiCitationResult {
  claim: string;
  noteId: number | null;
  status: WikiCitationStatus;
  reason: string;
  resolvedNoteId: number | null;
}
export interface WikiCitationSummary {
  verified: number;
  rejected: number;
  ungrounded: number;
  weaklyGrounded: number;
  total: number;
}
/** POST /wiki/citations/verify response. */
export interface WikiCitationVerifyResult {
  results: WikiCitationResult[];
  summary: WikiCitationSummary;
}

/* ---- A1a M3 sync conflicts (W7, deferred from A1a) — MIRRORS reader sync_store.
   Block-level LWW convergence keeps EVERY version (0 data loss); a TRUE conflict
   (same note+block edited divergently) is surfaced here for human resolution. ---- */
/** One kept version of a conflicting block (the LWW loser is recoverable). */
export interface WikiConflictVersion {
  device: string;
  content: string;
  ts: string;
}
/** One detected conflict (GET /wiki/sync/conflicts → data.conflicts[]). */
export interface WikiConflict {
  id: number;
  noteId: number;
  blockIndex: number;
  versions: WikiConflictVersion[];
  status: "open" | "resolved";
  detected: string;
  resolved: string | null;
}
/** GET /wiki/sync/conflicts payload. Empty = no open conflicts (honest). */
export interface WikiConflictList {
  conflicts: WikiConflict[];
}
/** POST /wiki/sync/conflicts/{id}/resolve body — human picks the winning content,
 *  written THROUGH the single-writer queue (update_note) for one auditable path. */
export interface WikiConflictResolveInput {
  noteId: number;
  content: string;
}

/* ---- Wiki Explorer tree (WEXP) — GET /wiki/tree. MIRRORS the frozen WEXP-BE shape:
   a RECURSIVE nested node {name, path, folders[], notes[]} built from notes' virtual
   `folder` field (NOT physical folders — flat 47.md preserved). Root node has name/
   path "". The backend pre-nests the tree (the FE renders it directly, no flattening). */
export interface WikiTreeNote {
  id: number;
  title: string | null;
}
/** A recursive folder node. `path` = "/"-delimited virtual path ("" = vault root);
 *  `folders` = subfolders (same shape); `notes` = notes directly in this folder. */
export interface WikiTreeNode {
  name: string;
  path: string;
  folders: WikiTreeNode[];
  notes: WikiTreeNote[];
}
/** GET /wiki/tree payload = the root WikiTreeNode (data IS the node). */
export type WikiTree = WikiTreeNode;

/* ---- #127 W1/W3 — wiki folder lifecycle (the dev work-dir ops). Mirror the FROZEN
   W1 response shapes (verified live). Folders are a human-curation surface (REST/FE-only,
   user CHỐT — not MCP). create = nested any depth (the empty-folder anchor); delete =
   SCOPED soft-delete the subtree (recoverable); move = re-prefix. ---- */
/** POST /wiki/folders body — create a (possibly nested) folder. path = "/"-delimited;
 *  a nested path ("A/B/C") nests through each segment (the empty-folder anchor). */
export interface WikiFolderCreateInput {
  path: string;
  desc?: string;
}
/** POST /wiki/folders response. created=false when the folder already existed (idempotent). */
export interface WikiFolderCreateResult {
  path: string;
  desc: string;
  created: boolean;
}
/** DELETE /wiki/folders/{path} response — the SCOPED soft-delete (subtree tombstoned,
 *  recoverable). deletedNotes = the note ids tombstoned; removedMeta = the meta keys dropped.
 *  🔴 "gone" is observed via the refreshed /wiki/tree, NOT get_note (still returns the tombstone). */
export interface WikiFolderDeleteResult {
  folder: string;
  deletedNotes: number[];
  removedMeta: string[];
  warnings: string[];
}

/** PUT /wiki/folders/{path}/move body + response — re-prefix the subtree. */
export interface WikiFolderMoveInput {
  to: string;
}
export interface WikiFolderMoveResult {
  from: string;
  to: string;
  movedNotes: number[];
  movedMeta: number;
  warnings: string[];
}

/* ---- Decision Journal + Calibration (W7-A2 / F1-H1) — MIRRORS backend
   modules/decision_journal/schema.py. A GENERAL decision (not a trade): decision +
   thesis + falsification condition + confidence% (the probability claim) → on
   resolve, an outcome (right/wrong on the THESIS axis) drives calibration. Brier +
   confidence-band + rule-based domain bias-cluster. ---- */
