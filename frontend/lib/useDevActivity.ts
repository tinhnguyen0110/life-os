"use client";
/* ============================================================
   useDevActivity — #63-P3 Dev Activity (DEVACT): read the git-contribution board
   + re-scan trigger.
   GET /dev_activity?days=N (board) · POST /dev_activity/scan?days=N (re-scan).
   Types mirror the FROZEN dev_activity/schema.py. RENDER-ONLY: the backend computes
   ALL derived metrics (commits/LOC/active-span/summary) from git — the FE displays.
   honest-empty "you" (DEV_TRACING_EMAILS unset) is a real state, not an error.
   Read is gated on status; scan is fail-closed (throws → caller surfaces).
   Malformed-body guard.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getDevActivity, scanDevActivity, ApiError } from "@/lib/api";
import type { DevActivityOverview, DevScanResult } from "@/lib/types";

export type DevActivityStatus = "loading" | "error" | "ready";

const EMPTY: DevActivityOverview = {
  rangeDays: 90,
  byDay: [],
  byRepo: [],
  otherRepos: [],
  summary: { totalCommits: 0, activeDays: 0, activeRepos: 0, locAdded: 0, locDeleted: 0, topRepos: [] },
  scannedRepos: 0,
  warnings: [],
};

export interface UseDevActivity {
  data: DevActivityOverview;
  status: DevActivityStatus;
  errMsg: string;
  /** the range currently loaded. */
  days: number;
  setDays: (d: number) => void;
  reload: () => void;
  /** re-scan now; returns the scan result. fail-closed (throws → caller surfaces). */
  scan: () => Promise<DevScanResult>;
}

export function useDevActivity(initialDays = 90): UseDevActivity {
  const [data, setData] = useState<DevActivityOverview>(EMPTY);
  const [status, setStatus] = useState<DevActivityStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [days, setDays] = useState(initialDays);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getDevActivity(days);
        if (!alive) return;
        const d = res?.data;
        if (d == null || !Array.isArray(d.byDay) || !Array.isArray(d.otherRepos) || d.summary == null) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setData({ ...EMPTY, ...d });
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
  }, [days, nonce]);

  const scan = useCallback(async () => {
    const res = await scanDevActivity(days); // fail-closed: throws → caller surfaces
    reload();
    return res.data;
  }, [days, reload]);

  return { data, status, errMsg, days, setDays, reload, scan };
}
