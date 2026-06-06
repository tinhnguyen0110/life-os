"use client";
/* ============================================================
   useActivity — S14 Activity Feed (read-only run_log projection + stats).
   GET /activity?status=&range= — status/range filters re-fetch SERVER-side (so the
   newest-100 cap + count stay correct per filter). Types mirror frozen
   activity/schema.py. render-only: successRate/avgDurationMs backend-computed;
   successRate null when count==0 → "—" (NOT 0%). Malformed-body guard.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getActivity, ApiError } from "@/lib/api";
import type { ActivityFeed } from "@/lib/types";

export type ActivityStatus = "loading" | "error" | "ready";
export type StatusFilter = "all" | "ok" | "error";
export type RangeFilter = "today" | "week";

const EMPTY: ActivityFeed = {
  runs: [], count: 0, runsToday: 0, okCount: 0, warnCount: 0, errorCount: 0,
  successRate: null, avgDurationMs: null, byRoutine: [],
};

export interface UseActivity {
  data: ActivityFeed;
  status: ActivityStatus;
  errMsg: string;
  warning: string | null;
  statusFilter: StatusFilter;
  rangeFilter: RangeFilter;
  setStatusFilter: (f: StatusFilter) => void;
  setRangeFilter: (f: RangeFilter) => void;
  reload: () => void;
}

export function useActivity(): UseActivity {
  const [data, setData] = useState<ActivityFeed>(EMPTY);
  const [status, setStatus] = useState<ActivityStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [rangeFilter, setRangeFilter] = useState<RangeFilter>("today");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getActivity({
          status: statusFilter === "all" ? undefined : statusFilter,
          range: rangeFilter,
        });
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
  }, [nonce, statusFilter, rangeFilter]);

  return { data, status, errMsg, warning, statusFilter, rangeFilter, setStatusFilter, setRangeFilter, reload };
}
