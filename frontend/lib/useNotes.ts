"use client";
/* ============================================================
   useNotes — S10 Notes data + WRITE operations (create/edit/delete).
   First write screen: REFETCH-AFTER-WRITE (GET /notes again on success) +
   FAIL-CLOSED on write errors — if a POST/PUT/DELETE fails, the change is NOT
   shown as saved; the caller gets the error to surface. A failed mutation must
   never silently lose a note or crash (the Sprint-5 fail-open lesson applies to
   mutations too: a 500/timeout on write surfaces, doesn't vanish).

   ⚠️ LOOSE/PLACEHOLDER TYPES (Sprint 6, S6-T3): shape mirrors the team-confirmed
   frozen Note ({id,title,body,tags[],pinned,attachedType,attachedId?,created/
   updatedAt}) — REPLACED verbatim by the notes/schema.py mirror when it freezes
   (mirror the FILE, not this). Field access isolated to the page mappers.
   render-only display; pinned/updatedAt are backend values, FE formats.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api";
import type { Note, NoteInput, Attach, AttachType } from "@/lib/types";

// Note shapes live in lib/types.ts (canonical mirror of notes/schema.py).
// Re-exported here so existing `@/lib/useNotes` imports keep working.
export type { Note, NoteInput, Attach, AttachType };

export type NotesStatus = "loading" | "error" | "ready";

export interface UseNotes {
  notes: Note[];
  status: NotesStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  /** create (POST /notes) → refetch. Throws ApiError on failure (caller surfaces). */
  createNote: (input: NoteInput) => Promise<void>;
  /** edit (PUT /notes/{id}) → refetch. Throws on failure. */
  updateNote: (id: string, input: Partial<NoteInput>) => Promise<void>;
  /** delete (DELETE /notes/{id}) → refetch. Throws on failure. */
  deleteNote: (id: string) => Promise<void>;
  /** toggle pin (PUT pinned) → refetch. */
  togglePin: (note: Note) => Promise<void>;
}

export function useNotes(): UseNotes {
  const [notes, setNotes] = useState<Note[]>([]);
  const [status, setStatus] = useState<NotesStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await apiGet<Note[]>("/notes");
        if (!alive) return;
        // Guard fulfilled-but-malformed (Sprint-5 lesson): bad body → error, not crash.
        setNotes(Array.isArray(res?.data) ? res.data : []);
        setWarning(res?.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  // Write ops: REFETCH on success (simplest-correct), THROW on failure (fail-closed
  // — the caller shows the error; the list is NOT optimistically mutated, so a
  // failed write never shows a phantom-saved note).
  const createNote = useCallback(
    async (input: NoteInput) => {
      await apiPost("/notes", input);
      reload();
    },
    [reload],
  );

  const updateNote = useCallback(
    async (id: string, input: Partial<NoteInput>) => {
      await apiPut(`/notes/${encodeURIComponent(id)}`, input);
      reload();
    },
    [reload],
  );

  const deleteNote = useCallback(
    async (id: string) => {
      await apiDelete(`/notes/${encodeURIComponent(id)}`);
      reload();
    },
    [reload],
  );

  const togglePin = useCallback(
    async (note: Note) => {
      // Pin toggle = PUT with the FULL body + pinned flipped (no /pin endpoint;
      // NoteInput.title is required, so we can't PUT {pinned} alone).
      await apiPut(`/notes/${encodeURIComponent(note.id)}`, {
        title: note.title,
        body: note.body,
        tags: note.tags,
        attach: note.attach,
        pinned: !note.pinned,
      });
      reload();
    },
    [reload],
  );

  return { notes, status, errMsg, warning, reload, createNote, updateNote, deleteNote, togglePin };
}
