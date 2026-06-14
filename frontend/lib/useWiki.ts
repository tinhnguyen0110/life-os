"use client";
/* ============================================================
   useWiki* — Wiki (W2/W3) data + WRITE operations. Mirrors the useNotes.ts
   pattern: loading/error/ready state machine, REFETCH-AFTER-WRITE (re-GET on
   success), FAIL-CLOSED on write errors (a failed PUT/POST/DELETE throws to the
   caller; the view is NOT optimistically mutated, so a failed write never shows a
   phantom-saved note). The W1c-frozen recompute (backlinks / linkCount) comes from
   the server refetch — never spliced client-side (single source of truth).

   Hooks: useWikiNote(id) → W2 (note + backlinks + edit) · useWikiInbox() → W3
   (fleeting list + refine, ≥1-link gate is SERVER-enforced → the 422 surfaces).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getWikiNote,
  getWikiBacklinks,
  updateWikiNote,
  deleteWikiNote,
  refineWikiNote,
  getWikiInbox,
  getWikiOverview,
  getWikiGraph,
  getWikiProposals,
  acceptWikiProposal,
  rejectWikiProposal,
  batchAcceptWikiProposals,
  getWikiClusters,
  getWikiMocs,
} from "@/lib/api";
import { ApiError } from "@/lib/api";
import type {
  WikiNote,
  WikiBacklinks,
  WikiInboxItem,
  WikiNoteUpdateInput,
  WikiOverview,
  WikiGraph,
  WikiProposal,
  WikiProposalStatus,
  WikiBatchAcceptResult,
  WikiCluster,
  WikiMoc,
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
/* W3 — inbox (fleeting list) + refine (≥1-link gate is server-side)  */
/* ------------------------------------------------------------------ */
export interface UseWikiInbox {
  items: WikiInboxItem[];
  status: WikiStatusState;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  /** refine (POST /wiki/notes/{id}/refine) → refetch list. Returns the server
   *  warning (cold-start) on success; THROWS ApiError(422) when the ≥1-link gate
   *  fails (caller surfaces it visibly — the rule lives server-side, not here). */
  refine: (id: number, input: WikiNoteUpdateInput) => Promise<string | null>;
}

export function useWikiInbox(): UseWikiInbox {
  const [items, setItems] = useState<WikiInboxItem[]>([]);
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
        const res = await getWikiInbox();
        if (!alive) return;
        setItems(Array.isArray(res?.data?.items) ? res.data.items : []);
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

  const refine = useCallback(
    async (id: number, input: WikiNoteUpdateInput): Promise<string | null> => {
      // Throws ApiError(422) on a gate failure → the caller keeps the panel open
      // and shows the error (fail-closed). On success (incl. cold-start 200+warning)
      // → refetch the list so linkCount/status reflect the server truth.
      const res = await refineWikiNote(id, input);
      reload();
      return res?.warning ?? null;
    },
    [reload],
  );

  return { items, status, errMsg, warning, reload, refine };
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
    if (center == null || Number.isNaN(center)) {
      // idle: no center chosen — not an error, just nothing to draw yet.
      setGraph(null);
      setErrMsg("");
      setWarning(null);
      setStatus("ready");
      return;
    }
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getWikiGraph(center, depth);
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
/* W5 — MOC screen: clusters (candidates) + MOC notes (read-only)     */
/* ------------------------------------------------------------------ */
export interface UseWikiMoc {
  clusters: WikiCluster[];
  mocs: WikiMoc[];
  status: WikiStatusState;
  errMsg: string;
  /** true = the clusters endpoint errored OR didn't respond in time (hung). Lets the
   *  UI say "tạm thời không tải được" instead of the honest "no clusters" empty. */
  clustersUnavailable: boolean;
  mocsUnavailable: boolean;
  reload: () => void;
}

/** Reject if `p` doesn't settle within `ms`. Guards the screen against a HUNG
 *  endpoint (server never responds → fetch never settles → Promise.allSettled would
 *  pin the screen on "loading" forever). With a timeout the hung call degrades to a
 *  rejection → fail-soft to empty + an "unavailable" flag. (Seen live W5b: the W5a
 *  /wiki/clusters endpoint hung; the MOC list must still render.) */
function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`request timed out after ${ms}ms`)), ms);
    p.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); },
    );
  });
}

const MOC_FETCH_TIMEOUT_MS = 8000;

/** Loads /wiki/clusters + /wiki/mocs in parallel. FAIL-SOFT per call: if one
 *  endpoint errors OR HANGS (per-call timeout), the other still renders — a clusters
 *  failure shouldn't blank the MOC list and vice-versa. Only a TOTAL failure (both
 *  reject) → error state. */
export function useWikiMoc(): UseWikiMoc {
  const [clusters, setClusters] = useState<WikiCluster[]>([]);
  const [mocs, setMocs] = useState<WikiMoc[]>([]);
  const [status, setStatus] = useState<WikiStatusState>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [clustersUnavailable, setClustersUnavailable] = useState(false);
  const [mocsUnavailable, setMocsUnavailable] = useState(false);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      const [cRes, mRes] = await Promise.allSettled([
        withTimeout(getWikiClusters(), MOC_FETCH_TIMEOUT_MS),
        withTimeout(getWikiMocs(), MOC_FETCH_TIMEOUT_MS),
      ]);
      if (!alive) return;
      const cOk = cRes.status === "fulfilled";
      const mOk = mRes.status === "fulfilled";
      if (!cOk && !mOk) {
        // total failure → error state (surface the clusters error/timeout message).
        setErrMsg(errMessage((cRes as PromiseRejectedResult).reason));
        setStatus("error");
        return;
      }
      setClusters(cOk ? (cRes.value?.data?.clusters ?? []) : []);
      setMocs(mOk ? (mRes.value?.data?.items ?? []) : []);
      setClustersUnavailable(!cOk);
      setMocsUnavailable(!mOk);
      setStatus("ready");
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  return { clusters, mocs, status, errMsg, clustersUnavailable, mocsUnavailable, reload };
}
