"use client";
/* ============================================================
   useWiki* — Wiki (W2/W3) data + WRITE operations. Mirrors the useNotes.ts
   pattern: loading/error/ready state machine, REFETCH-AFTER-WRITE (re-GET on
   success), FAIL-CLOSED on write errors (a failed PUT/POST/DELETE throws to the
   caller; the view is NOT optimistically mutated, so a failed write never shows a
   phantom-saved note). The W1c-frozen recompute (backlinks / linkCount) comes from
   the server refetch — never spliced client-side (single source of truth).

   Hooks: useWikiNote(id) → W2 (note + backlinks + edit).
   WIKI-AIFIRST: the /wiki/inbox triage screen + its useWikiInbox/refine hook were
   removed (AI-first: writes land directly, fleeting notes refine in place at /wiki/{id}).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getWikiNote,
  getWikiBacklinks,
  updateWikiNote,
  deleteWikiNote,
  getWikiOverview,
  getWikiGraph,
  getWikiGraphGlobal,
  getWikiProposals,
  acceptWikiProposal,
  rejectWikiProposal,
  batchAcceptWikiProposals,
  getWikiTree,
} from "@/lib/api";
import { ApiError } from "@/lib/api";
import { subscribeWikiTree, wikiTreeVersion } from "@/lib/wikiTreeBus";
import type {
  WikiNote,
  WikiBacklinks,
  WikiNoteUpdateInput,
  WikiOverview,
  WikiGraph,
  WikiProposal,
  WikiProposalStatus,
  WikiBatchAcceptResult,
  WikiTreeNode,
} from "@/lib/types";

export type WikiStatusState = "loading" | "error" | "ready";

function errMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : (e as Error).message;
}

/* ------------------------------------------------------------------ */
/* W2 — one note + its backlinks + edit                               */
/* ------------------------------------------------------------------ */
export interface UseWikiNote {
  note: WikiNote | null;
  backlinks: WikiBacklinks | null;
  status: WikiStatusState;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  /** edit (PUT /wiki/notes/{id}) → refetch note+backlinks. Throws on failure (fail-closed). */
  save: (input: WikiNoteUpdateInput) => Promise<void>;
  /** delete (DELETE /wiki/notes/{id}) → refetch. Throws on failure. */
  remove: () => Promise<void>;
}

export function useWikiNote(id: number | null): UseWikiNote {
  const [note, setNote] = useState<WikiNote | null>(null);
  const [backlinks, setBacklinks] = useState<WikiBacklinks | null>(null);
  const [status, setStatus] = useState<WikiStatusState>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (id == null || Number.isNaN(id)) {
      setStatus("error");
      setErrMsg("Note id không hợp lệ.");
      return;
    }
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        // Note is the gate (404 → error); backlinks fail-soft to empty (a note with
        // no connections is valid, and a backlinks error shouldn't blank the note).
        const noteRes = await getWikiNote(id);
        let bl: WikiBacklinks | null = null;
        try {
          const blRes = await getWikiBacklinks(id);
          bl = blRes?.data ?? null;
        } catch {
          bl = { linked: [], unlinked: [], outbound: [] };
        }
        if (!alive) return;
        setNote(noteRes?.data ?? null);
        setBacklinks(bl);
        setWarning(noteRes?.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(errMessage(e));
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [id, nonce]);

  const save = useCallback(
    async (input: WikiNoteUpdateInput) => {
      if (id == null) return;
      await updateWikiNote(id, input); // throws on non-2xx → caller surfaces (fail-closed)
      reload();
    },
    [id, reload],
  );

  const remove = useCallback(async () => {
    if (id == null) return;
    await deleteWikiNote(id);
    reload();
  }, [id, reload]);

  return { note, backlinks, status, errMsg, warning, reload, save, remove };
}

/* ------------------------------------------------------------------ */
/* W1 — vault overview (read-only: stats + summaries + op-log)        */
/* ------------------------------------------------------------------ */
export interface UseWikiOverview {
  overview: WikiOverview | null;
  status: WikiStatusState;
  errMsg: string;
  /** empty-vault / cold-start note (shown as info, not an error). */
  warning: string | null;
  reload: () => void;
}

export function useWikiOverview(): UseWikiOverview {
  const [overview, setOverview] = useState<WikiOverview | null>(null);
  const [status, setStatus] = useState<WikiStatusState>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getWikiOverview();
        if (!alive) return;
        setOverview(res?.data ?? null);
        setWarning(res?.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(errMessage(e));
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  return { overview, status, errMsg, warning, reload };
}

/* ------------------------------------------------------------------ */
/* W4 — ego-graph around a center note (read-only)                    */
/* ------------------------------------------------------------------ */
export interface UseWikiGraph {
  graph: WikiGraph | null;
  status: WikiStatusState;
  errMsg: string;
  warning: string | null;
  /** current center / depth (echoed so the UI controls reflect the loaded graph). */
  center: number | null;
  depth: number;
  reload: () => void;
}

/** Loads /wiki/graph?note=center&depth=depth. When `center` is null (no note
 *  chosen yet) the hook stays in a non-error "ready" idle state with graph=null
 *  so the screen can show the "pick a center note" prompt rather than an error. */
export function useWikiGraph(center: number | null, depth: number): UseWikiGraph {
  const [graph, setGraph] = useState<WikiGraph | null>(null);
  const [status, setStatus] = useState<WikiStatusState>("ready");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        // GLOBAL-GRAPH: center null → whole-vault global graph (the DEFAULT view);
        // a numeric center → ego-graph around it. Same {center,nodes,edges,clusters}
        // shape either way (center now nullable for global).
        const res =
          center == null || Number.isNaN(center)
            ? await getWikiGraphGlobal()
            : await getWikiGraph(center, depth);
        if (!alive) return;
        setGraph(res?.data ?? null);
        setWarning(res?.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(errMessage(e));
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [center, depth, nonce]);

  return { graph, status, errMsg, warning, center, depth, reload };
}

/* ------------------------------------------------------------------ */
/* P1 — proposal queue (list + accept/reject/batch, fail-closed)      */
/* ------------------------------------------------------------------ */
export type ProposalFilter = WikiProposalStatus | "all";

export interface UseWikiProposals {
  proposals: WikiProposal[];
  counts: Partial<Record<WikiProposalStatus, number>>;
  filter: ProposalFilter;
  setFilter: (f: ProposalFilter) => void;
  status: WikiStatusState;
  errMsg: string;
  reload: () => void;
  /** accept ONE → refetch. THROWS ApiError(4xx) when the apply can't proceed
   *  (target missing / bad payload) — caller surfaces it visibly (fail-closed). */
  accept: (id: number, decidedBy?: string) => Promise<void>;
  /** reject ONE → refetch. Throws on failure. */
  reject: (id: number, decidedBy?: string) => Promise<void>;
  /** batch-accept many → refetch. Returns the per-id result summary so the caller
   *  can surface a PARTIAL failure (200 + failed>0). Throws only on a whole-call
   *  error (network / 4xx envelope). */
  batchAccept: (ids: number[], decidedBy?: string) => Promise<WikiBatchAcceptResult | null>;
}

export function useWikiProposals(initial: ProposalFilter = "pending"): UseWikiProposals {
  const [proposals, setProposals] = useState<WikiProposal[]>([]);
  const [counts, setCounts] = useState<Partial<Record<WikiProposalStatus, number>>>({});
  const [filter, setFilter] = useState<ProposalFilter>(initial);
  const [status, setStatus] = useState<WikiStatusState>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getWikiProposals(filter);
        if (!alive) return;
        setProposals(Array.isArray(res?.data?.proposals) ? res.data.proposals : []);
        setCounts(res?.data?.counts ?? {});
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(errMessage(e));
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [filter, nonce]);

  const accept = useCallback(
    async (id: number, decidedBy?: string) => {
      // throws on non-2xx (e.g. "target note N not found") → caller surfaces (fail-closed);
      // the queue is NOT optimistically mutated, so a failed apply leaves the card in place.
      await acceptWikiProposal(id, decidedBy ? { decidedBy } : undefined);
      reload();
    },
    [reload],
  );

  const reject = useCallback(
    async (id: number, decidedBy?: string) => {
      await rejectWikiProposal(id, decidedBy ? { decidedBy } : undefined);
      reload();
    },
    [reload],
  );

  const batchAccept = useCallback(
    async (ids: number[], decidedBy?: string): Promise<WikiBatchAcceptResult | null> => {
      if (!ids.length) return null;
      const res = await batchAcceptWikiProposals({ ids, ...(decidedBy ? { decidedBy } : {}) });
      reload();
      return res?.data ?? null;
    },
    [reload],
  );

  return { proposals, counts, filter, setFilter, status, errMsg, reload, accept, reject, batchAccept };
}

/* ------------------------------------------------------------------ */
/* WIKI-TRIM — useWikiMoc (W5 MOC screen) + useWikiConflicts (A1c Sync */
/* screen) were REMOVED with their screens. The BE endpoints (clusters/ */
/* mocs/conflicts/resolve) stay for MCP/agent; their typed api/wiki.ts  */
/* clients are kept but no longer consumed by the FE.                   */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/* WEXP — wiki folder tree (explorer pane) + move-note                */
/* ------------------------------------------------------------------ */
export interface UseWikiTree {
  /** the root tree node (null until loaded / on error). */
  tree: WikiTreeNode | null;
  status: WikiStatusState;
  errMsg: string;
  reload: () => void;
  /** move a note to a folder (PUT {folder}) → refetch the tree. THROWS on failure
   *  (fail-closed — the tree is NOT optimistically mutated). folder "" = vault root. */
  move: (id: number, folder: string) => Promise<void>;
}

export function useWikiTree(): UseWikiTree {
  const [tree, setTree] = useState<WikiTreeNode | null>(null);
  const [status, setStatus] = useState<WikiStatusState>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  // #108 — subscribe to the wiki-tree bus: ANY tree-mutating write (create / import /
  // move-folder / delete / restore / bulk-delete) done in ANOTHER component bumps the
  // bus → this Explorer instance refetches its folder counts. Fixes the stale-count
  // (e.g. write a note to a new folder → Explorer still showed Projects=0 until a manual
  // reload). lastSeen-vs-version guards a bump that landed between mount + subscribe.
  useEffect(() => {
    const lastSeen = wikiTreeVersion();
    const unsub = subscribeWikiTree(() => setNonce((n) => n + 1));
    // a write may have bumped the version between this effect's mount and the subscribe
    // (or before mount) — catch up so we don't miss it.
    if (wikiTreeVersion() !== lastSeen) setNonce((n) => n + 1);
    return unsub;
  }, []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getWikiTree();
        if (!alive) return;
        setTree(res?.data ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(errMessage(e));
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  const move = useCallback(
    async (id: number, folder: string) => {
      await updateWikiNote(id, { folder }); // throws → caller surfaces (fail-closed)
      reload();
    },
    [reload],
  );

  return { tree, status, errMsg, reload, move };
}
