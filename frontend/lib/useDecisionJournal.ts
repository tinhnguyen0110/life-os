"use client";
/* ============================================================
   useDecisionJournal — Decision Journal (F1-H1) data + writes. Mirrors the
   useJournal / useWiki pattern: loading/error/ready, REFETCH-AFTER-WRITE,
   FAIL-CLOSED on writes (a failed POST/PUT/DELETE throws to the caller; the view
   is NOT optimistically mutated). Calibration stats (brier/bands/biasFlags) are
   BACKEND-computed — the FE renders only, never recomputes (single source of truth).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getDecisionJournal,
  createDecision,
  updateDecision,
  deleteDecision,
  ApiError,
} from "@/lib/api";
import type {
  DecisionJournalData,
  DecisionCreateInput,
  DecisionPatchInput,
} from "@/lib/types";

export type DJStatusState = "loading" | "error" | "ready";

function errMessage(e: unknown): string {
  return e instanceof ApiError ? e.message : (e as Error).message;
}

const EMPTY: DecisionJournalData = {
  entries: [], count: 0, resolvedCount: 0, brier: null, calibration: [], biasFlags: [],
};

export interface UseDecisionJournal {
  data: DecisionJournalData;
  status: DJStatusState;
  errMsg: string;
  reload: () => void;
  /** log a decision → refetch. Throws (fail-closed) on 422/error → caller surfaces. */
  create: (input: DecisionCreateInput) => Promise<void>;
  /** partial update / resolve → refetch. Throws on failure. */
  update: (id: string, input: DecisionPatchInput) => Promise<void>;
  /** delete → refetch. Throws on failure. */
  remove: (id: string) => Promise<void>;
}

export function useDecisionJournal(): UseDecisionJournal {
  const [data, setData] = useState<DecisionJournalData>(EMPTY);
  const [status, setStatus] = useState<DJStatusState>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getDecisionJournal();
        if (!alive) return;
        setData(res?.data ?? EMPTY);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(errMessage(e));
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  const create = useCallback(
    async (input: DecisionCreateInput) => {
      await createDecision(input); // throws on 422/error → caller surfaces (fail-closed)
      reload();
    },
    [reload],
  );

  const update = useCallback(
    async (id: string, input: DecisionPatchInput) => {
      await updateDecision(id, input);
      reload();
    },
    [reload],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteDecision(id);
      reload();
    },
    [reload],
  );

  return { data, status, errMsg, reload, create, update, remove };
}
