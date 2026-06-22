"""modules/wiki/router.py — Wiki REST endpoints (Sprint W1a).

Mounts at ``/wiki`` via the registry (``MODULE`` below). Adding this folder is the
ONLY wiring needed — no edit to ``core/`` or ``main.py`` (registry auto-discovers
``MODULE`` from this file, the projects/notes fallback path).

W1a scope = identity + store + single-writer queue + CRUD. Links/FTS/graph are
W1b/W1c. This router is HTTP shape + status codes only — all mutation logic lives
in ``service.py`` (every write goes through the single-writer changes-queue).
Envelope: ``core.responses.ok`` → ``{success, data, warning?}``. Errors are the flat
agent-first shape ``{error:{code,message,hint,retryable}}`` via ``agent_error_response``
(AGENT-ERROR #46): 404 NOT_FOUND (missing note/proposal), 409 CONFLICT (already-decided
proposal), 422 INVALID_INPUT (merge/refine/apply gate). Raw body/path 422s are still
FastAPI/Pydantic auto (the #24 follow-up will normalize those app-wide).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from core.agent_errors import agent_error, agent_error_response  # #61 item#3 + AGENT-ERROR-P6 (#46)
from core.base import BaseModule
from core.responses import ok


def _note_not_found(note_id: int) -> JSONResponse:
    """WIKI-RECONCILE/#61 item#3: a note-id 404 as the agent-first error shape (flat top-level
    ``{error:{code,message,hint,retryable}}`` via agent_error #46) — NOT the raw {"detail":...}.
    JSONResponse (not HTTPException(detail=...)) so the body is the flat error, not double-nested
    under "detail". NOT_FOUND auto-resolves retryable=False. The agent gets a code to branch on + a
    hint naming where to find a valid id."""
    return JSONResponse(
        status_code=404,
        content=agent_error("NOT_FOUND", f"wiki note {note_id} not found",
                            hint="check the id via wiki_tree or wiki_search"),
    )

from datetime import datetime, timezone

from . import citations, proposals_service, reader, service, sync_store
from . import store as wiki_store
from .proposals_schema import (
    BatchAcceptInput,
    DecideInput,
    ProposalCreateInput,
)
from .schema import (
    CitationVerifyInput,
    ConflictResolveInput,
    DeviceRegisterInput,
    FolderCreateInput,
    FolderMetaInput,
    FolderMoveInput,
    BulkDeleteInput,
    ImportInput,
    MergeInput,
    NoteCreateInput,
    NoteUpdateInput,
    OverrideReason,
)

logger = logging.getLogger("life-os.wiki.router")

router = APIRouter(tags=["wiki"])


@router.get("")
def wiki_info():
    """Liveness/info for the wiki module. The note CRUD surface is below."""
    return ok(data={"module": "wiki", "status": "ok"})


@router.get("/search")
def search(q: str = "", query: str = "", folder: str | None = None):
    """Full-text search → RANKED top-5 ``[{id, title, folder, snippet, score, relevance}]``
    (WIKI-RETRIEVAL-2 #22 + #99 relevance — agent-first lean: top-5 not flat, score+relevance so the
    agent sees WHY/HOW-STRONG it matched, NO body). Accepts ``q`` OR ``query`` (alias; ``q`` wins).
    ``folder`` (#101, optional): scope to a folder + its subtree; None/'' = whole vault (the default,
    non-blocking). Empty/malformed → empty list (never 500). Same reader.search the MCP wiki_search
    uses (#24 parity)."""
    return ok(data=reader.search(q or query, folder=folder))


@router.get("/overview")
def overview():
    """Vault overview (C4): ``{stats, inbox, orphans, recentActivity, proposalCount}``.
    Empty vault → ``stats.pctWithLink: null`` + a warning (never 0/div-zero)."""
    data, warning = reader.overview()
    return ok(data=data, warning=warning)


@router.get("/inbox")
def inbox():
    """Fleeting notes awaiting triage (C5), oldest→newest. ``aiSuggest: null`` (M4)."""
    return ok(data=reader.inbox())


@router.get("/graph")
def graph(note: int | None = None, depth: int = 2):
    """Wiki graph: ``{center, nodes, edges, clusters}``.

    - NO ``note`` → GLOBAL whole-vault graph (the DEFAULT, Obsidian-style): every note +
      every resolved edge + all clusters; ``center: null``. Honest-empty on a fresh vault.
    - ``?note=X`` → ego-graph 1–2 hop around X (unchanged); 404 if X is absent. ``depth``
      is ego-only.
    """
    if note is None:
        return ok(data=reader.global_graph())
    g = reader.ego_graph(note, depth)
    if g is None:
        return agent_error_response("NOT_FOUND", f"wiki note {note} not found",
                                    hint="check the id via wiki_tree or wiki_search")
    return ok(data=g)


# --------------------------------------------------------------------------- #
# W6 A1a — M3 multi-device sync (option B): device registry + conflict surfacing #
# Merge mechanism is in sync.py (pure) + sync_store.py. These endpoints expose   #
# the registry + the detected-conflict queue + a human-resolve path (writes      #
# through the single-writer). DEFERRED (option B): id-prefix migration, FE UI,    #
# real transport — see end_sprint §Assumptions.                                  #
# --------------------------------------------------------------------------- #
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/sync/devices")
def register_device(body: DeviceRegisterInput):
    """Register/refresh a sync device (M3 A1a). The identity an op-stream is tagged
    with. Returns the device list."""
    sync_store.register_device(body.deviceId, body.name, _now_iso())
    return ok(data={"devices": sync_store.list_devices()})


@router.get("/sync/devices")
def list_devices():
    """Registered sync devices, most-recently-seen first."""
    return ok(data={"devices": sync_store.list_devices()})


@router.get("/sync/conflicts")
def sync_conflicts(status: str = "open"):
    """Detected true conflicts awaiting resolution (M3 A1a, the surfacing endpoint).
    Each: ``{id, noteId, blockIndex, versions:[{device, content, ts}], status,
    detected, resolved}`` — EVERY version kept so the LWW loser is recoverable (0
    data loss). No conflicts → ``{conflicts: []}`` (honest)."""
    return ok(data={"conflicts": sync_store.list_conflicts(status)})


@router.post("/sync/conflicts/{conflict_id}/resolve")
def resolve_conflict(conflict_id: int, body: ConflictResolveInput):
    """Human resolves a conflict: write the chosen note ``content`` THROUGH the
    single-writer queue (reuses update_note — all mutation in one auditable place),
    then mark the conflict resolved. 404 if the conflict is absent/already resolved
    or the target note is gone.

    F2-M3: VALIDITY CHECKED BEFORE THE WRITE — gate the note-mutation on the conflict
    being open, so resolving an absent/already-resolved conflict never mutates the
    vault (the old order wrote the note first, then 404'd — a stray write)."""
    if not sync_store.conflict_is_open(conflict_id):
        return agent_error_response("NOT_FOUND", f"conflict {conflict_id} not found or already resolved",
                                    hint="GET /wiki/sync/conflicts for open conflicts")
    try:
        service.update_note(body.noteId, NoteUpdateInput(content=body.content))
    except service.NoteNotFound:
        return agent_error_response("NOT_FOUND", f"wiki note {body.noteId} not found",
                                    hint="check the id via wiki_tree or wiki_search")
    # mark resolved (guarded UPDATE — still atomic-safe if a race slipped through).
    if not sync_store.resolve_conflict(conflict_id, _now_iso()):
        return agent_error_response("NOT_FOUND", f"conflict {conflict_id} not found or already resolved",
                                    hint="GET /wiki/sync/conflicts for open conflicts")
    return ok(data={"resolved": conflict_id})


@router.post("/citations/verify")
def verify_citations(body: CitationVerifyInput):
    """Post-verify citations (W6 A1b, spec L120-121 — the anti-fabrication gate).
    Body ``{claims:[{claim, noteId?, span?}]}`` → per-claim status
    verified | rejected | ungrounded | weakly_grounded + a summary. Read-only: it
    only reads notes (follows D6 redirects), never mutates. Empty claims → empty
    results (never 500). The external agent calls this BEFORE presenting its answer."""
    claims = [c.model_dump() for c in body.claims]
    return ok(data=citations.verify_citations(claims))


@router.post("/reindex")
def reindex():
    """WIKI-RECONCILE (#53): bulk-reconcile the wiki cache against the md files (source of truth),
    PRUNING orphan cache rows whose .md is gone (the tree-lies bug — phantom rows listed by
    all_notes() that GET /notes/{id} 404s). ``{scanned, dropped, rebuilt, unchanged, droppedIds}``.
    Reuses the per-note reindex primitive — prunes ONLY orphan index rows, never a real note.
    Idempotent (a 2nd call drops 0). Same reader.reindex_all the MCP wiki_reindex calls → byte-identical (#24)."""
    return ok(data=reader.reindex_all())


@router.get("/clusters")
def clusters():
    """MOC candidates (W5a, D-W5.1): graph-detected clusters of ≥3 linked notes
    above the density threshold, ranked by advisory importance (size×density).
    Each: ``{members:[{id,title}], size, density, importance, suggestedTitle}``.
    No clusters yet → ``{clusters: []}`` (honest empty state)."""
    return ok(data={"clusters": reader.detect_clusters()})


@router.get("/mocs")
def mocs():
    """List MOC-type notes (W5a, D-W5.2), newest first. Empty → ``{items: []}``."""
    return ok(data=reader.mocs())


@router.get("/stale")
def stale():
    """WIKI-STALE-DETECTOR (#41, SPEC A6): the read-only staleness + contradiction-candidate
    detector. ``{stale:[{id,title,updated,daysSince,inboundCount,status}], contradictionCandidates:
    [{pair,titles,reason}], thresholdDays, staleCount, candidateCount}``. STALE = evergreen + updated
    > the ``staleThresholdDays`` config knob + ≥1 inbound. Read-only (no auto-fix); honest-empty.
    Same ``reader.stale_notes`` the MCP ``wiki_stale`` calls → MCP≡REST byte-identical (#24)."""
    from modules.settings.service import get_config
    return ok(data=reader.stale_notes(threshold_days=get_config().staleThresholdDays))


@router.get("/tree")
def tree(folder: str | None = None, depth: int | None = None):
    """W-Explorer virtual folder-tree built from notes' ``folder`` fields. Nested
    ``{name, path, meta:{desc}|null, counts:{notes:N}, folders:[...], notes:[{id,title,kind,
    status}]}`` rooted at "" (WIKI-RETRIEVAL-1 #20: +meta/counts/kind/status for ls-style
    navigation without reading bodies). ``folder`` scopes to a subtree; ``depth`` limits nesting.
    Folders are virtual (files stay flat at <id>.md — D1). Empty vault → honest empty root. This
    is the SAME shape the MCP wiki_tree returns (byte-identical — the #24 invariant)."""
    return ok(data=reader.folder_tree(folder=folder, depth=depth))


@router.put("/folders/{folder_path:path}/meta")
def set_folder_meta(folder_path: str, body: FolderMetaInput):
    """WIKI-RETRIEVAL-1 (#20): set a folder's description (shows as the tree's ``meta:{desc}``).
    A blank desc CLEARS the meta (→ meta:null, honest-null vs an empty 'described as nothing').
    ``folder_path`` is the virtual path (may contain '/'). Returns the resulting meta (or null)."""
    wiki_store.set_folder_meta(folder_path, body.desc)
    return ok(data={"folderPath": folder_path, "meta": wiki_store.get_folder_meta(folder_path)})


def _folder_error(exc: service.FolderError) -> JSONResponse:
    """#127: map a FolderError → the agent-first flat error (422 INVALID_INPUT / 409 CONFLICT)."""
    status = 409 if exc.code == "CONFLICT" else 422
    return JSONResponse(status_code=status,
                        content=agent_error(exc.code, exc.message, hint=exc.hint))  # type: ignore[arg-type]


@router.post("/folders")
def create_folder(body: FolderCreateInput):
    """#127 (WIKI-WORKDIR): create a (possibly NESTED, arbitrary-depth) EMPTY folder by anchoring a
    wiki_folder_meta row at the normalized ``path`` — so a folder with NO notes now EXISTS in /tree
    (counts:0). Returns ``{path, desc, created}``. 422 if the path normalizes to empty; 409 if the
    folder already exists (a meta row OR notes carry the prefix). REST-only (folder-ops are not MCP)."""
    try:
        return ok(data=service.create_folder(body.path, body.desc))
    except service.FolderError as exc:
        return _folder_error(exc)


@router.put("/folders/{folder_path:path}/move")
def move_folder(folder_path: str, body: FolderMoveInput):
    """#127: rename/move a folder — re-prefix every note under ``folder_path`` → ``to`` + move the
    folder_meta rows (path + descendants). Returns ``{from, to, movedNotes:[ids], movedMeta:N,
    warnings:[]}``. 422 if path/to empty or ``to`` is inside ``path``; 409 if ``to`` already exists
    (no silent merge). Fail-soft per note (a single note's move error → a warning)."""
    try:
        return ok(data=service.move_folder(folder_path, body.to))
    except service.FolderError as exc:
        return _folder_error(exc)


@router.delete("/folders/{folder_path:path}")
def delete_folder(folder_path: str):
    """#127: SOFT-delete a folder + its subtree — #94-tombstones every note under ``folder_path``
    (recoverable, → trash) + removes the folder_meta rows (path + descendants). SCOPED to exactly
    that subtree (#72 — never a blanket). Returns ``{folder, deletedNotes:[ids], removedMeta:[paths],
    warnings:[]}``. 422 if the path is empty (can't delete the root)."""
    try:
        return ok(data=service.delete_folder(folder_path))
    except service.FolderError as exc:
        return _folder_error(exc)


@router.post("/notes")
def create_note(body: NoteCreateInput):
    """Create a note (capture → fleeting). Server-set id + timestamps. Goes through
    the single-writer queue → 1 git commit + 1 op_log row.

    WIKI-SUGGEST-LINK (#34): the write-through response carries ``suggestedLinks`` — top 3-5 NEW
    link candidates (FTS over the new content, self + already-linked excluded) so the agent can link
    the fresh note + keep the graph connected. Suggest-only (never auto-applies)."""
    note = service.create_note(body)
    data = note.model_dump()
    data["suggestedLinks"] = reader.suggest_links(note.id)
    return ok(data=data)


@router.post("/import")
async def import_notes(request: Request):
    """#93: import .md/.txt → wiki note(s), reusing create_note (→ 1 git commit + [[link]] resolve).
    Supports BOTH (content-type sniffed, logged to Assumptions):
      - JSON ``{files:[{filename, content}]}`` (paste path — the FE's primary).
      - multipart ``UploadFile[]`` (file upload — any field name; each part's filename + decoded text).
    Returns ``{success, data:{imported:[result rows], createdCount}}``. Per-file fail-soft: a bad
    file yields its agent_error row, the good ones still import (batch never fails wholesale)."""
    ctype = request.headers.get("content-type", "")
    files: list[tuple[str, str]] = []
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        for value in form.values():
            # UploadFile parts only (skip plain form fields); decode bytes → text (utf-8, lenient).
            if hasattr(value, "filename") and hasattr(value, "read"):
                raw = await value.read()
                text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                files.append((value.filename or "upload", text))
        if not files:
            return agent_error_response(
                "INVALID_INPUT", "no files in the multipart upload",
                hint="attach at least one .md or .txt file")
    else:
        # JSON paste path — validate via ImportInput (≥1 file; 422 on a malformed body).
        try:
            payload = await request.json()
        except Exception:
            return agent_error_response("INVALID_INPUT", "request body is not valid JSON",
                                        hint="send {files:[{filename, content}]} or a multipart upload")
        try:
            parsed = ImportInput.model_validate(payload)
        except Exception as exc:
            return agent_error_response("INVALID_INPUT", f"bad import body: {exc}",
                                        hint="send {files:[{filename, content}]} with ≥1 file")
        files = [(f.filename, f.content) for f in parsed.files]
    return ok(data=service.import_files(files))


@router.post("/notes/merge")
def merge_notes(body: MergeInput):
    """Merge ``sourceId`` INTO ``targetId`` (B5/D6): source deleted, a redirect
    tombstone written, inbound links repointed. Returns the target note. 422 if the
    ids are equal; 404 if either note is absent."""
    try:
        note = service.merge_notes(body.sourceId, body.targetId)
    except service.MergeError as exc:
        return agent_error_response("INVALID_INPUT", str(exc),
                                    hint="source and target must be different existing note ids")
    except service.NoteNotFound as exc:
        return agent_error_response("NOT_FOUND", f"wiki note {exc} not found",
                                    hint="check both ids via wiki_tree or wiki_search")
    return ok(data=note.model_dump(),
              warning=f"merged #{body.sourceId} into #{body.targetId}")


@router.get("/notes/{note_id}")
def get_note(note_id: int, mode: str = "full", heading: str | None = None):
    """One note. Follows a redirect tombstone (a merged-away id returns the merge target + a
    warning, NOT 404 — citations survive, B5). 404 only if the id never existed.

    WIKI-RETRIEVAL-2 (#21) ``mode``: full (DEFAULT, the bare note UNCHANGED) | outline (heading
    ToC + meta, NO body) | section (+``heading`` → only that section). Same reader.note_view the
    MCP wiki_get_note uses → byte-identical (#24)."""
    note, warning = service.resolve_note(note_id)
    if note is None:
        return _note_not_found(note_id)  # #61 item#3: agent-readable 404 shape
    return ok(data=reader.note_view(note, mode=mode, heading=heading), warning=warning)


@router.get("/notes/{note_id}/backlinks")
def get_backlinks(note_id: int):
    """Backlinks for a note: ``{linked, unlinked, outbound}`` (B3). 404 if the note
    is absent. ``unlinked`` ships ``[]`` in W1b (FTS-backed, populated W1c)."""
    if service.get_note(note_id) is None:
        return _note_not_found(note_id)  # #61 item#3: agent-readable 404 shape
    return ok(data=reader.backlinks(note_id))


@router.get("/notes/{note_id}/context")
def get_context(note_id: int, depth: int = 2):
    """WIKI-RETRIEVAL-3 (#23): a note's FULL neighborhood in ONE call —
    ``{found, note_id, graph:{center,nodes,edges,clusters}, backlinks:{linked,unlinked,outbound}}``.
    The COMPOSING read (graph + backlinks together) so an agent/UI navigating a note gets both at
    once instead of 2-3 calls. 404 if the note is absent (the wiki REST convention). Same
    ``reader.context`` the MCP ``wiki_context`` tool calls → MCP≡REST byte-identical (#24)."""
    if service.get_note(note_id) is None:
        return _note_not_found(note_id)  # #61 item#3: agent-readable 404 shape
    return ok(data=reader.context(note_id, depth))


@router.get("/notes/{note_id}/suggested-links")
def get_suggested_links(note_id: int, limit: int = 5):
    """WIKI-SUGGEST-LINK (#34): top 3-5 NEW link candidates for a note —
    ``[{id, title, score, relevance}]`` (FTS over the note's text, self + already-linked EXCLUDED,
    more-relevant first). #107: ``relevance`` = the #99 1-exp 0..1 (agent-readable), ``score`` = raw
    bm25. The same suggestions the write-through response carries, fetchable
    standalone (e.g. an agent that wrote via the MCP proposal-apply path, not REST). 404 if the
    note is absent. Same ``reader.suggest_links`` the MCP ``wiki_suggest_links`` calls → MCP≡REST
    byte-identical (#24). Suggest-only — never applies a link."""
    if service.get_note(note_id) is None:
        return _note_not_found(note_id)  # #61 item#3: agent-readable 404 (4th GET note-id route)
    return ok(data={"suggestedLinks": reader.suggest_links(note_id, limit)})


@router.post("/notes/{note_id}/refine")
def refine_note(note_id: int, body: NoteUpdateInput):
    """REFINE a note (C6/D9): update-path + the ≥1-link HARD GATE. 404 if absent;
    422 if the note would have 0 links and the vault is past cold-start. On the
    cold-start exception (vault < threshold) it succeeds with a warning."""
    try:
        note, warning = service.refine_note(note_id, body)
    except service.NoteNotFound:
        return _note_not_found(note_id)  # #14: agent-readable 404 (return Response, not raise)
    except service.RefineGateError as exc:
        return agent_error_response("INVALID_INPUT", str(exc),
                                    hint="a refined note needs ≥1 link (past cold-start) — add a [[link]]")
    data = note.model_dump()
    data["suggestedLinks"] = reader.suggest_links(note.id)  # #34
    return ok(data=data, warning=warning)


def _override_feedback(reason: OverrideReason | None, text: str | None) -> dict | None:
    """#35: build the override-feedback dict from the optional query params, or None
    (silent override). The Literal type on ``reason`` makes a bad value a 422 at the
    FastAPI boundary. text is OPTIONAL (a reason with no text is fine)."""
    if reason is None:
        return None
    return {"reason": reason, "text": text}


@router.put("/notes/{note_id}")
def update_note(
    note_id: int,
    body: NoteUpdateInput,
    overrideReason: OverrideReason | None = Query(  # noqa: N803 (camelCase = the API param)
        default=None,
        description="#35: WHY a human is overriding an AGENT-written note (off-scope|wrong|"
                    "duplicate|low-quality|outdated|other). Captured as feedback ONLY when this "
                    "edit overrides agent work; omit for a silent edit. Bad value → 422."),
    overrideText: str | None = Query(  # noqa: N803
        default=None, description="#35: optional free-text detail for the override reason."),
):
    """Partial-update a note in place (preserve created+id; bump updated unless a
    no-op touch). Goes through the queue. 404 if absent. ``overrideReason``/``overrideText``
    (#35) record WHY when a human overrides an agent-written note → wiki_my_feedback."""
    try:
        note = service.update_note(
            note_id, body, feedback=_override_feedback(overrideReason, overrideText))
    except service.NoteNotFound:
        return _note_not_found(note_id)  # #14: agent-readable 404 (return Response, not raise)
    data = note.model_dump()
    data["suggestedLinks"] = reader.suggest_links(note.id)  # #34
    return ok(data=data)


@router.delete("/notes/{note_id}")
def delete_note(
    note_id: int,
    overrideReason: OverrideReason | None = Query(  # noqa: N803
        default=None,
        description="#35: WHY a human is deleting an AGENT-written note (off-scope|wrong|"
                    "duplicate|low-quality|outdated|other). Captured as feedback ONLY when this "
                    "delete overrides agent work; omit for a silent delete. Bad value → 422."),
    overrideText: str | None = Query(  # noqa: N803
        default=None, description="#35: optional free-text detail for the override reason."),
):
    """#94: SOFT-delete a note (recoverable) — sets a deletedAt tombstone, KEEPS the .md
    (reconcile-safe) + cache row + aliases/links, hides it from live views. Restore via
    POST /notes/{id}/restore. 404 if absent. ``overrideReason``/``overrideText`` (#35) record WHY
    when a human deletes an agent-written note → wiki_my_feedback."""
    try:
        note = service.soft_delete_note(
            note_id, feedback=_override_feedback(overrideReason, overrideText))
    except service.NoteNotFound:
        return _note_not_found(note_id)  # #14: agent-readable 404 (return Response, not raise)
    return ok(data={"deleted": note_id, "deletedAt": note.deletedAt})


@router.post("/notes/{note_id}/restore")
def restore_note(note_id: int):
    """#94: RESTORE a soft-deleted note — clears the tombstone, the note is fully BACK in every view
    (links/aliases intact). 404 if absent. Idempotent (already-live → returned unchanged)."""
    try:
        note = service.restore_note(note_id)
    except service.NoteNotFound:
        return _note_not_found(note_id)
    return ok(data=note.model_dump())


@router.post("/notes/bulk-delete")
def bulk_delete(body: BulkDeleteInput):
    """#94: BULK soft-delete by id — per-id results (fail-soft: a bad id yields its error row, the
    rest still soft-delete). ``{results:[{id, ok, error?}], deletedCount}``."""
    results = []
    deleted = 0
    for nid in body.ids:
        try:
            service.soft_delete_note(nid)
            results.append({"id": nid, "ok": True, "error": None})
            deleted += 1
        except service.NoteNotFound:
            results.append({"id": nid, "ok": False,
                            "error": agent_error("NOT_FOUND", f"no wiki note #{nid}",
                                                 hint="GET /wiki/notes for valid ids")["error"]})
    return ok(data={"results": results, "deletedCount": deleted})


@router.get("/trash")
def list_trash():
    """#94: the SOFT-DELETED notes (the restore/trash UI source) — lean rows {id, title, deletedAt,
    folder} from the cache, newest-deleted state. Honest-empty → []."""
    rows = wiki_store.trash_notes(order_by="id")
    items = [{"id": r["id"], "title": r["title"], "deletedAt": r["deleted_at"],
              "folder": r["folder"]} for r in rows]
    return ok(data={"trash": items, "count": len(items)})


@router.get("/feedback")
def wiki_feedback(limit: int = 50):
    """WIKI-WRITE-FEEDBACK (#35): the override-feedback the agent reads to learn WHY a
    human overrode its notes — newest-first ``{feedback: [{noteId, reason, text,
    overriddenAt, originalTitle, overrideKind}], count}``. Honest-empty → {feedback:[],
    count:0}. REST mirror of the wiki_my_feedback MCP tool (byte-identical data, #24)."""
    return ok(data=reader.my_feedback(limit=int(limit)))


# --------------------------------------------------------------------------- #
# W4a — Proposal / approval queue (M4 trust boundary in code)                   #
# Every AI mutation lands here as a PENDING proposal; a human accepts (applies   #
# via the M1 single-writer) or rejects (nothing applied). Static paths are       #
# declared BEFORE /proposals/{proposal_id} so "batch-accept" isn't captured as   #
# an id.                                                                         #
# --------------------------------------------------------------------------- #
@router.post("/proposals")
def create_proposal(body: ProposalCreateInput):
    """Enqueue a proposal (PENDING). Records intent only — NOTHING is written to
    the vault until a human accepts. Returns the stored proposal."""
    return ok(data=proposals_service.create_proposal(body))


@router.get("/proposals")
def list_proposals(status: str = "pending"):
    """Proposals newest-first. ``status`` defaults to ``pending`` (the P1 review
    queue's default view); pass ``accepted`` / ``rejected`` to filter, or ``all``
    for every proposal. Includes a ``counts`` map for the queue badge. Empty queue
    → ``proposals: []`` (honest empty state, never 500/null)."""
    filter_status = None if status == "all" else status
    data = proposals_service.list_proposals(filter_status)
    return ok(data={"proposals": data, "counts": proposals_service.count_by_status()})


@router.post("/proposals/accept-batch")
def accept_batch_proposals(body: BatchAcceptInput):
    """Accept many proposals in one call (P1 batch action). Each applies
    independently — one failure never aborts the rest. Returns
    ``{results: [{id, ok, proposal?, error?}], accepted, failed}``."""
    return ok(data=proposals_service.batch_accept(body.ids, decided_by=body.decidedBy))


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int):
    """One proposal. 404 if absent."""
    p = proposals_service.get_proposal(proposal_id)
    if p is None:
        return agent_error_response("NOT_FOUND", f"wiki proposal {proposal_id} not found",
                                    hint="GET /wiki/proposals for valid ids")
    return ok(data=p)


@router.post("/proposals/{proposal_id}/accept")
def accept_proposal(proposal_id: int, body: DecideInput | None = None):
    """ACCEPT: apply the mutation through the M1 single-writer, then mark accepted.
    404 absent · 409 already decided · 422 the payload/mutation is invalid (the
    proposal stays pending so it can be retried)."""
    decided_by = (body or DecideInput()).decidedBy
    try:
        p = proposals_service.accept_proposal(proposal_id, decided_by=decided_by)
    except proposals_service.ProposalNotFound:
        return agent_error_response("NOT_FOUND", f"wiki proposal {proposal_id} not found",
                                    hint="GET /wiki/proposals for valid ids")
    except proposals_service.AlreadyDecided as exc:
        return agent_error_response("CONFLICT", str(exc),
                                    hint="this proposal is already accepted/rejected — it can't be decided again")
    except proposals_service.ApplyError as exc:
        return agent_error_response("INVALID_INPUT", str(exc),
                                    hint="the proposal payload/mutation is invalid — it stays pending to retry")
    return ok(data=p, warning=f"applied proposal #{proposal_id} → note #{p['appliedNoteId']}")


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: int, body: DecideInput | None = None):
    """REJECT: mark rejected. NOTHING is applied. 404 absent · 409 already decided."""
    decided_by = (body or DecideInput()).decidedBy
    try:
        p = proposals_service.reject_proposal(proposal_id, decided_by=decided_by)
    except proposals_service.ProposalNotFound:
        return agent_error_response("NOT_FOUND", f"wiki proposal {proposal_id} not found",
                                    hint="GET /wiki/proposals for valid ids")
    except proposals_service.AlreadyDecided as exc:
        return agent_error_response("CONFLICT", str(exc),
                                    hint="this proposal is already accepted/rejected — it can't be decided again")
    return ok(data=p)


MODULE = BaseModule(name="wiki", router=router)
