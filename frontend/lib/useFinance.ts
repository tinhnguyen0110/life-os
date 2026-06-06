"use client";
/* ============================================================
   useFinance — client hook for the S5 Finance Overview screen.
   Fetches GET /finance → FinanceOverview (totalValue + change + allocations +
   dryPowder + pnlTotal). Types MIRROR backend finance/schema.py (lib/types.ts) —
   no placeholders. SELF-DESCRIBING RAW: drift/pnl are backend-computed + ship
   with inputs; the FE renders + formats + colors, NEVER recomputes. A wrong
   number is a backend bug — reported, not patched.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";
import type { FinanceOverview, ChannelAlloc } from "@/lib/types";

export type FinanceStatus = "loading" | "error" | "ready";

const EMPTY: FinanceOverview = {
  totalValue: 0,
  change: null,
  holdings: [],
  allocations: [],
  pnlTotal: { cost: 0, current: 0, abs: 0, pct: null },
  dryPowder: 0,
  series: [],
};

export interface UseFinance {
  data: FinanceOverview;
  status: FinanceStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
}

export function useFinance(): UseFinance {
  const [data, setData] = useState<FinanceOverview>(EMPTY);
  const [status, setStatus] = useState<FinanceStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await apiGet<FinanceOverview>("/finance");
        if (!alive) return;
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

  return { data, status, errMsg, warning, reload };
}

/** ChannelAlloc.drift (signed number = pct - target) → display label + alert flag.
 *  render-only: drift is the BACKEND's number; |drift|>5 is a DISPLAY threshold on
 *  that value (rebalance alert), NOT a recomputation. */
export function driftLabel(a: Pick<ChannelAlloc, "drift" | "target" | "pct"> | null | undefined): {
  text: string;
  alert: boolean;
} | null {
  if (!a || !Number.isFinite(a.drift)) return null;
  const sign = a.drift > 0 ? "+" : a.drift < 0 ? "−" : "";
  return {
    // show actual vs target + the backend drift (all self-describing)
    text: `${a.pct.toFixed(0)}% vs ${a.target.toFixed(0)}% (${sign}${Math.abs(a.drift).toFixed(1)})`,
    alert: Math.abs(a.drift) > 5,
  };
}
