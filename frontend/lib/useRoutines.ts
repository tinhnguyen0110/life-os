"use client";
/* ============================================================
   useRoutines — S13 Automation/Routines: read + toggle + run-now.
   GET /routines (catalog + run_log stats) · PATCH /routines/{id} (toggle enabled)
   · POST /routines/{id}/run (run now). Types mirror frozen automation/schema.py.
   render-only stats. Writes REFETCH-after + FAIL-CLOSED (throw → caller surfaces;
   no optimistic toggle that lies if the PATCH fails). Malformed-body guard.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getRoutines, toggleRoutine, runRoutine, ApiError } from "@/lib/api";
import type { RoutinesView } from "@/lib/types";

export type RoutinesStatus = "loading" | "error" | "ready";

const EMPTY: RoutinesView = { routines: [], activeCount: 0, total: 0, runsToday: 0, lastRunAt: null };

export interface UseRoutines {
  data: RoutinesView;
  status: RoutinesStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  /** toggle enabled (PATCH) → refetch. Throws ApiError on failure. */
  toggle: (id: string, enabled: boolean) => Promise<void>;
  /** run now (POST /run) → refetch. Returns the recorded run's status/detail. */
  run: (id: string) => Promise<{ status: string; detail: string }>;
}

export function useRoutines(): UseRoutines {
  const [data, setData] = useState<RoutinesView>(EMPTY);
  const [status, setStatus] = useState<RoutinesStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getRoutines();
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

  const toggle = useCallback(
    async (id: string, enabled: boolean) => {
      await toggleRoutine(id, enabled); // fail-closed: throws → caller surfaces, no optimistic lie
      reload();
    },
    [reload],
  );

  const run = useCallback(
    async (id: string) => {
      const res = await runRoutine(id);
      reload(); // refresh runs/lastRun after the run
      return { status: res.data.status, detail: res.data.detail };
    },
    [reload],
  );

  return { data, status, errMsg, warning, reload, toggle, run };
}
