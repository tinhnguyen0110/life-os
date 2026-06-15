"use client";
/* ============================================================
   useMacro — FE-5 Macro context view data. GET /macro/overview (Fed/CPI/DXY +
   trend + source) + GET /macro/history (per-indicator series for a sparkline).
   Types are LOCAL (per dispatch — do NOT touch lib/types.ts). apiGet only (read).

   HONEST-MIRROR: `source` is surfaced verbatim — when source="mock" the page MUST
   show the mock badge + warning so the user never mistakes it for live (the gate).
   NEUTRAL: trend is descriptive (up/down/flat) — the FE adds NO forecast/advice.
   loading/error/ready; the overview error is the page gate, history is fail-soft
   (a sparkline that won't load must not blank the indicator card).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { ApiError } from "@/lib/api";

export type MacroTrend = "up" | "down" | "flat";

export interface MacroIndicator {
  indicator: string;
  label: string;
  unit: string;
  latest: number;
  asOf: string;
  previous: number | null;
  change: number | null;
  trend: MacroTrend;
  source: string;
  points: number;
}
export interface MacroOverview {
  indicators: MacroIndicator[];
  asOf: string;
  source: string;
}
export interface MacroPoint {
  indicator: string;
  value: number;
  ts: string;
  source: string;
}

export type MacroStatus = "loading" | "error" | "ready";

const EMPTY: MacroOverview = { indicators: [], asOf: "", source: "" };

export interface UseMacro {
  overview: MacroOverview;
  status: MacroStatus;
  errMsg: string;
  /** the backend warning (mock-data notice) — shown verbatim. */
  warning: string | null;
  reload: () => void;
  /** per-indicator history for a sparkline. Fail-soft: returns [] on error (a
   *  missing sparkline must not blank the card). */
  loadHistory: (indicator: string, days?: number) => Promise<number[]>;
}

export function useMacro(): UseMacro {
  const [overview, setOverview] = useState<MacroOverview>(EMPTY);
  const [status, setStatus] = useState<MacroStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await apiGet<MacroOverview>("/macro/overview");
        if (!alive) return;
        const d = res?.data;
        setOverview({
          indicators: Array.isArray(d?.indicators) ? d.indicators : [],
          asOf: d?.asOf ?? "",
          source: d?.source ?? "",
        });
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

  const loadHistory = useCallback(async (indicator: string, days = 30): Promise<number[]> => {
    try {
      const res = await apiGet<{ indicator: string; points: MacroPoint[] }>(
        `/macro/history?indicator=${encodeURIComponent(indicator)}&days=${days}`,
      );
      const pts = Array.isArray(res?.data?.points) ? res.data.points : [];
      return pts.map((p) => p.value).filter((v) => typeof v === "number" && Number.isFinite(v));
    } catch {
      return []; // fail-soft — no sparkline, card still renders
    }
  }, []);

  return { overview, status, errMsg, warning, reload, loadHistory };
}
