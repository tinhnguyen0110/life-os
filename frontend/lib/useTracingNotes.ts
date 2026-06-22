"use client";
/* ============================================================
   useTracingNotes — #121 / #122 Tracing day-notes: read the note list + create /
   update / delete. GET/POST/PUT/DELETE /tracing/notes. Types mirror the FROZEN
   tracing/schema.py Note. RENDER-ONLY view of the BE list; writes are REFETCH-after +
   FAIL-CLOSED (throw → caller surfaces; no optimistic mutation). honest-empty {notes:[]}
   is a real state, not an error. Malformed-body guard.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getTracingNotes, createTracingNote, updateTracingNote, deleteTracingNote, ApiError,
} from "@/lib/api";
import type { TracingNote, TracingNoteInput, TracingNoteUpdate } from "@/lib/types";

export type TracingNotesStatus = "loading" | "error" | "ready";

export interface UseTracingNotes {
  notes: TracingNote[];
  status: TracingNotesStatus;
  errMsg: string;
  reload: () => void;
  /** create one; returns the new Note. fail-closed (throws → caller surfaces). */
  create: (body: TracingNoteInput) => Promise<TracingNote>;
  update: (id: string, body: TracingNoteUpdate) => Promise<TracingNote>;
  remove: (id: string) => Promise<void>;
}

export function useTracingNotes(): UseTracingNotes {
  const [notes, setNotes] = useState<TracingNote[]>([]);
  const [status, setStatus] = useState<TracingNotesStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getTracingNotes();
        if (!alive) return;
        if (res?.data == null || !Array.isArray(res.data.notes)) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setNotes(res.data.notes);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  const create = useCallback(async (body: TracingNoteInput) => {
    const res = await createTracingNote(body); // fail-closed: throws → caller surfaces
    reload();
    return res.data;
  }, [reload]);

  const update = useCallback(async (id: string, body: TracingNoteUpdate) => {
    const res = await updateTracingNote(id, body);
    reload();
    return res.data;
  }, [reload]);

  const remove = useCallback(async (id: string) => {
    await deleteTracingNote(id);
    reload();
  }, [reload]);

  return { notes, status, errMsg, reload, create, update, remove };
}
