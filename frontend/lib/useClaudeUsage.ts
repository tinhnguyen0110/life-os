"use client";
/* ============================================================
   useClaudeUsage — S9 Claude token usage (GET /claude-usage). Read-only.
   Types mirror the FROZEN claude_usage/schema.py (lib/types.ts). render-only:
   pct/remaining/cost are backend-derived, FE formats. resetIn/weekly/byProject
   are honest STUBS (null) — render "—"/"sắp có", never a fabricated number.
   Guards a fulfilled-but-malformed response (Sprint-5 lesson) → error, no crash.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getClaudeUsage, ApiError } from "@/lib/api";
import type { ClaudeUsage } from "@/lib/types";

export type UsageStatus = "loading" | "error" | "ready";

export interface UseClaudeUsage {
  data: ClaudeUsage | null;
  status: UsageStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
}

export function useClaudeUsage(): UseClaudeUsage {
  const [data, setData] = useState<ClaudeUsage | null>(null);
  const [status, setStatus] = useState<UsageStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getClaudeUsage();
        if (!alive) return;
        // fulfilled-but-malformed guard (Sprint-5): a 200 with no .data → error.
        if (res?.data == null) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setData(res.data);
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
