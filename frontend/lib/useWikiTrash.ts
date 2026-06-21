"use client";
/* ============================================================
   useWikiTrash — #94 wiki soft-delete recovery. List the trash (GET /wiki/trash) +
   restore a note (POST /wiki/notes/{id}/restore). RENDER-ONLY: the backend owns the
   soft-delete store; the FE displays + triggers restore. Reads gated on status +
   honest empty (count 0). Restore is FAIL-CLOSED (throws → caller surfaces) +
   refetch-after-restore. A nonce drives reload; an alive-guard drops a stale list.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getWikiTrash, restoreWikiNote, ApiError } from "@/lib/api";
import type { WikiTrashItem } from "@/lib/types";

export type TrashStatus = "loading" | "error" | "ready";

export interface UseWikiTrash {
  items: WikiTrashItem[];
  count: number;
  status: TrashStatus;
  errMsg: string;
  reload: () => void;
  /** restore a soft-deleted note → refetch the trash. fail-closed. */
  restore: (id: number) => Promise<void>;
}

export function useWikiTrash(): UseWikiTrash {
  const [items, setItems] = useState<WikiTrashItem[]>([]);
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState<TrashStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getWikiTrash();
        if (!alive) return;
        const d = res?.data;
        if (d == null || !Array.isArray(d.trash)) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setItems(d.trash);
        setCount(d.count ?? d.trash.length);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [nonce]);

  const restore = useCallback(async (id: number) => {
    await restoreWikiNote(id); // fail-closed: throws → caller surfaces
    reload();
  }, [reload]);

  return { items, count, status, errMsg, reload, restore };
}
