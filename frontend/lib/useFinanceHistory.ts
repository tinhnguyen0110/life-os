"use client";
/* ============================================================
   useFinanceHistory (FE-3) — fetch the portfolio equity curve.
   Reads GET /finance/history?days=N (daily {day, ts, totalValue, byChannel}
   points, oldest→newest) via the existing read-only apiGet. NO backend edits,
   NO lib/api.ts / lib/types.ts edits (career lane owns those) — the point type
   lives HERE locally, mirroring finance/router.py + service.value_history().

   Empty list is a valid state (no snapshots yet) and the backend ships a warning
   to that effect — surfaced so the chart shows an honest empty-state, never NaN.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, ApiError } from "@/lib/api";

/** One daily equity snapshot (mirror of finance service.value_history() row). */
export interface EquityPoint {
  day: string;        // "YYYY-MM-DD" (UTC day)
  ts: string;         // ISO-8601 UTC capture time
  totalValue: number; // portfolio total that day
  byChannel?: Record<string, number>;
}

/** GET /finance/history payload. */
export interface FinanceHistory {
  points: EquityPoint[];
  days: number;
}

export type RangeDays = 7 | 30 | 90 | 365;
export type HistoryStatus = "loading" | "error" | "ready";

export const RANGE_DAYS: { value: RangeDays; label: string }[] = [
  { value: 7, label: "7N" },
  { value: 30, label: "30N" },
  { value: 90, label: "90N" },
  { value: 365, label: "1 năm" },
];

export interface UseFinanceHistory {
  points: EquityPoint[];
  status: HistoryStatus;
  errMsg: string;
  /** "no snapshots yet" warning from the backend (cold-start equity curve). */
  warning: string | null;
  /** totalValue series oldest→newest (for the line/area path). */
  values: number[];
  days: RangeDays;
  setDays: (d: RangeDays) => void;
  reload: () => void;
  /** Optional WRITE: record today's snapshot (POST /finance/snapshot), then reload. */
  snapshotToday: () => Promise<void>;
  /** True while a snapshot POST is in flight (button busy state). */
  snapshotting: boolean;
}

export function useFinanceHistory(): UseFinanceHistory {
  const [points, setPoints] = useState<EquityPoint[]>([]);
  const [status, setStatus] = useState<HistoryStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [days, setDays] = useState<RangeDays>(30);
  const [nonce, setNonce] = useState(0);
  const [snapshotting, setSnapshotting] = useState(false);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    setErrMsg("");
    (async () => {
      try {
        const res = await apiGet<FinanceHistory>(`/finance/history?days=${days}`);
        if (!alive) return;
        setPoints(res.data?.points ?? []);
        setWarning(res.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [days, nonce]);

  const snapshotToday = useCallback(async () => {
    setSnapshotting(true);
    try {
      await apiPost("/finance/snapshot");
      reload();
    } finally {
      setSnapshotting(false);
    }
  }, [reload]);

  const values = points.map((p) => p.totalValue);

  return { points, status, errMsg, warning, values, days, setDays, reload, snapshotToday, snapshotting };
}
