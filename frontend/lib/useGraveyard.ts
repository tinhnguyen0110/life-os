"use client";
/* ============================================================
   useGraveyard — S4 Graveyard data + restore write.
   GET /graveyard (read) + restore (POST /projects/{id}/restore → refetch).
   Types mirror frozen graveyard/schema.py. render-only: avgPeak/reached/before
   are backend-computed; lesson null → "—" (never fabricated). Malformed-body
   guard (Sprint-5). Restore is FAIL-CLOSED: on failure it throws → caller shows
   the error; the grave is NOT optimistically removed (no phantom-restore).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getGraveyard, restoreProject, ApiError } from "@/lib/api";
import type { GraveyardStats } from "@/lib/types";

export type GraveyardStatus = "loading" | "error" | "ready";

const EMPTY: GraveyardStats = {
  graves: [], count: 0, avgPeak: 0, commonReasons: [], reachedUser: 0, beforeUser: 0, lessons: [],
};

export interface UseGraveyard {
  data: GraveyardStats;
  status: GraveyardStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  /** restore a grave (POST /restore) → refetch. Throws ApiError on failure. */
  restore: (id: string) => Promise<void>;
}

export function useGraveyard(): UseGraveyard {
  const [data, setData] = useState<GraveyardStats>(EMPTY);
  const [status, setStatus] = useState<GraveyardStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getGraveyard();
        if (!alive) return;
        if (res?.data == null) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setData({ ...EMPTY, ...res.data });
        setWarning(res.warning ?? null);
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

  const restore = useCallback(
    async (id: string) => {
      await restoreProject(id); // fail-closed: throws → caller surfaces, no optimistic removal
      reload();
    },
    [reload],
  );

  return { data, status, errMsg, warning, reload, restore };
}
