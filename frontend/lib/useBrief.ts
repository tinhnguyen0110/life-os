"use client";
/* ============================================================
   useBrief — S11 daily Brief (read-only, template-based). Fetches /brief (today)
   + /brief/history (past) with PER-SOURCE fail-open: history down → brief still
   renders (history is secondary). Types mirror frozen brief/schema.py.
   render-only: summary numbers / priorities / severity are backend-computed; the
   FE only composes + styles. Malformed-body guard on the primary brief.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getBrief, getBriefHistory, ApiError } from "@/lib/api";
import type { Brief } from "@/lib/types";

export type BriefStatus = "loading" | "error" | "ready";

export interface UseBrief {
  brief: Brief | null;
  history: Brief[];
  historyError: string | null;
  status: BriefStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
}

export function useBrief(): UseBrief {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [history, setHistory] = useState<Brief[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [status, setStatus] = useState<BriefStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    setHistoryError(null);
    (async () => {
      const [briefRes, histRes] = await Promise.allSettled([getBrief(), getBriefHistory()]);

      if (!alive) return;

      // primary brief — drives the screen's loading/error/ready
      if (briefRes.status === "rejected") {
        const e = briefRes.reason;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error)?.message ?? "lỗi không xác định");
        setStatus("error");
      } else if (briefRes.value?.data == null) {
        setErrMsg("phản hồi không hợp lệ");
        setStatus("error");
      } else {
        setBrief(briefRes.value.data);
        setWarning(briefRes.value.warning ?? null);
        setStatus("ready");
      }

      // history — secondary, fail-open (its own error, never blanks the brief)
      if (histRes.status === "rejected") {
        const e = histRes.reason;
        setHistoryError(e instanceof ApiError ? e.message : (e as Error)?.message ?? "lỗi");
        setHistory([]);
      } else if (Array.isArray(histRes.value?.data)) {
        setHistory(histRes.value.data);
      } else {
        setHistory([]);
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  return { brief, history, historyError, status, errMsg, warning, reload };
}
