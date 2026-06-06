"use client";
/* ============================================================
   useJournal — S7 trade journal: read + create + close (PUT).
   GET /journal (entries + stats) · POST /journal (record) · PUT /journal/{id}
   (close: set pnl/outcome/lesson). Types mirror frozen journal/schema.py.
   render-only stats (winRate/avgPnl/etc backend-computed; null → "—"). Writes
   are REFETCH-after + FAIL-CLOSED (throw → caller surfaces; no optimistic add).
   Malformed-body guard (Sprint-5).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getJournal, createJournal, updateJournal, ApiError } from "@/lib/api";
import type { JournalStats, JournalInput } from "@/lib/types";

export type JournalStatus = "loading" | "error" | "ready";

const EMPTY: JournalStats = {
  entries: [], count: 0, winRate: null, avgPnl: null, ladderDiscipline: null,
  thisMonth: { total: 0, buy: 0, sell: 0, ladder: 0 }, calibration: [],
};

export interface UseJournal {
  data: JournalStats;
  status: JournalStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  create: (body: JournalInput) => Promise<void>;
  close: (id: string, body: JournalInput) => Promise<void>;
}

export function useJournal(): UseJournal {
  const [data, setData] = useState<JournalStats>(EMPTY);
  const [status, setStatus] = useState<JournalStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getJournal();
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

  const create = useCallback(
    async (body: JournalInput) => {
      await createJournal(body); // fail-closed: throws → caller surfaces
      reload();
    },
    [reload],
  );

  const close = useCallback(
    async (id: string, body: JournalInput) => {
      await updateJournal(id, body);
      reload();
    },
    [reload],
  );

  return { data, status, errMsg, warning, reload, create, close };
}
