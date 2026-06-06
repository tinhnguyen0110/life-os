"use client";
/* ============================================================
   usePortfolio — S6 Portfolio LIST (read GET /finance + add-holding write).
   Reuses the /finance overview (totalValue + holdings[] + allocations[]). render-only:
   value/pct/drift/pnl are backend-computed, FE formats. addHolding is FAIL-CLOSED:
   POST → on success REFETCH GET /finance (the POST returns only the Holding, not the
   overview) → on 422 surface per-field errors. Malformed-body guard on read.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getFinance, createHolding, ApiError } from "@/lib/api";
import type { FinanceOverview, HoldingInput } from "@/lib/types";

export type PortfolioStatus = "loading" | "error" | "ready";

const EMPTY: FinanceOverview = {
  totalValue: 0, change: null, holdings: [], allocations: [],
  pnlTotal: { cost: 0, current: 0, abs: 0, pct: null }, dryPowder: 0, series: [],
};

export interface AddResult {
  ok: boolean;
  fieldErrors?: Record<string, string>;
  formError?: string;
}

export interface UsePortfolio {
  data: FinanceOverview;
  status: PortfolioStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  addHolding: (input: HoldingInput) => Promise<AddResult>;
}

export function usePortfolio(): UsePortfolio {
  const [data, setData] = useState<FinanceOverview>(EMPTY);
  const [status, setStatus] = useState<PortfolioStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getFinance();
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

  const addHolding = useCallback(async (input: HoldingInput): Promise<AddResult> => {
    try {
      await createHolding(input);
      // FAIL-CLOSED: POST returns only the Holding → refetch the overview for the
      // recomputed allocations/pnl. Don't optimistically splice the new row.
      const res = await getFinance();
      if (res?.data != null) setData({ ...EMPTY, ...res.data });
      return { ok: true };
    } catch (e) {
      if (e instanceof ApiError) {
        const fieldErrors = e.fieldErrors();
        if (Object.keys(fieldErrors).length > 0) return { ok: false, fieldErrors };
        return { ok: false, formError: e.message };
      }
      return { ok: false, formError: (e as Error).message };
    }
  }, []);

  return { data, status, errMsg, warning, reload, addHolding };
}
