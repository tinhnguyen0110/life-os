"use client";
/* ============================================================
   useTracing — #65-P3 Daily Tracing (G-HABIT): read the board + log a
   session + add/edit/archive activities.
   GET /tracing (board) · POST /tracing/{id}/log · POST /tracing/activities ·
   PUT /tracing/activities/{id} · DELETE /tracing/activities/{id}.
   Types mirror the FROZEN tracing/schema.py. RENDER-ONLY: the backend computes
   ALL derived metrics (streak/pct/week/heatmap/score) — the FE never recomputes.
   Writes are REFETCH-after + FAIL-CLOSED (throw → caller surfaces; no optimistic
   mutation). Malformed-body guard.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getTracing,
  logTracingSession,
  untickActivity,
  createActivity,
  updateActivity,
  archiveActivity,
  ApiError,
} from "@/lib/api";
import type {
  TracingOverview,
  ActivityView,
  Activity,
  TracingLogInput,
  ActivityInput,
  ActivityPatch,
} from "@/lib/types";

export type TracingStatus = "loading" | "error" | "ready";

const EMPTY: TracingOverview = {
  date: "",
  activities: [],
  heatmap12w: Array(84).fill(0),
  score: { total: 0, done: 0, pct: 0, timeActive: "", topStreak: 0 },
};

export interface UseTracing {
  data: TracingOverview;
  status: TracingStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  /** log one session; returns the updated ActivityView. fail-closed (throws → caller surfaces). */
  log: (id: string, body: TracingLogInput) => Promise<ActivityView>;
  /** #136 — un-tick: clear today's log → done=false (the tick-toggle un-complete). */
  untick: (id: string) => Promise<void>;
  add: (body: ActivityInput) => Promise<Activity>;
  edit: (id: string, body: ActivityPatch) => Promise<Activity>;
  archive: (id: string) => Promise<void>;
}

export function useTracing(): UseTracing {
  const [data, setData] = useState<TracingOverview>(EMPTY);
  const [status, setStatus] = useState<TracingStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getTracing();
        if (!alive) return;
        if (res?.data == null || !Array.isArray(res.data.activities) || !Array.isArray(res.data.heatmap12w)) {
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

  const log = useCallback(
    async (id: string, body: TracingLogInput) => {
      const res = await logTracingSession(id, body); // fail-closed: throws → caller surfaces
      reload();
      return res.data;
    },
    [reload],
  );

  const untick = useCallback(
    async (id: string) => {
      await untickActivity(id); // #136 — clear today's log → done=false; fail-closed
      reload();
    },
    [reload],
  );

  const add = useCallback(
    async (body: ActivityInput) => {
      const res = await createActivity(body);
      reload();
      return res.data;
    },
    [reload],
  );

  const edit = useCallback(
    async (id: string, body: ActivityPatch) => {
      const res = await updateActivity(id, body);
      reload();
      return res.data;
    },
    [reload],
  );

  const archive = useCallback(
    async (id: string) => {
      await archiveActivity(id);
      reload();
    },
    [reload],
  );

  return { data, status, errMsg, warning, reload, log, untick, add, edit, archive };
}
