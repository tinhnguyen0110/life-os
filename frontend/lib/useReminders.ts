"use client";
/* ============================================================
   useReminders — #31 reminders (GAP-4): read + create + tick + delete.
   GET /reminders?filter= (today|week|undone|all) · POST /reminders ·
   PUT /reminders/{id}/tick (idempotent) · DELETE /reminders/{id}.
   Types mirror the FROZEN reminders/schema.py. RENDER-ONLY: the backend
   computes `overdue` / done_at — the FE never derives state.
   Writes are REFETCH-after + FAIL-CLOSED (throw → caller surfaces; no
   optimistic mutation). Malformed-body guard.

   The server has NO `done` filter — the UI "Done" view is a render-only
   client filter (done_at != null) over a fetched `all`. So this hook fetches
   `all` for both the "all" and "done" UI tabs and lets the screen subset; the
   3 real server filters (today|week|undone) are passed through.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getReminders,
  createReminder,
  tickReminder,
  deleteReminder,
  ApiError,
} from "@/lib/api";
import type { Reminder, ReminderInput, ReminderList } from "@/lib/types";

export type ReminderStatus = "loading" | "error" | "ready";

/** The UI tabs. "done" is a CLIENT view (no server filter) → it fetches `all`. */
export type ReminderTab = "today" | "week" | "undone" | "all" | "done";

const EMPTY: ReminderList = { reminders: [], count: 0, undoneCount: 0, filter: "all" };

/** Map a UI tab to the actual SERVER filter to request. "done"/"all" both fetch
 *  `all` (the screen client-subsets "done" to done_at != null). */
function serverFilterFor(tab: ReminderTab): "today" | "week" | "undone" | "all" {
  if (tab === "today" || tab === "week" || tab === "undone") return tab;
  return "all"; // "all" and "done" both fetch the full list
}

export interface UseReminders {
  data: ReminderList;
  status: ReminderStatus;
  errMsg: string;
  warning: string | null;
  /** the UI tab currently driving the fetch. */
  tab: ReminderTab;
  setTab: (t: ReminderTab) => void;
  reload: () => void;
  create: (body: ReminderInput) => Promise<Reminder>;
  tick: (id: number) => Promise<void>;
  remove: (id: number) => Promise<void>;
}

export function useReminders(initialTab: ReminderTab = "undone"): UseReminders {
  const [data, setData] = useState<ReminderList>(EMPTY);
  const [status, setStatus] = useState<ReminderStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [tab, setTab] = useState<ReminderTab>(initialTab);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await getReminders(serverFilterFor(tab));
        if (!alive) return;
        if (res?.data == null || !Array.isArray(res.data.reminders)) {
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
  }, [tab, nonce]);

  const create = useCallback(
    async (body: ReminderInput) => {
      const res = await createReminder(body); // fail-closed: throws → caller surfaces
      reload();
      return res.data;
    },
    [reload],
  );

  const tick = useCallback(
    async (id: number) => {
      await tickReminder(id); // idempotent; throws → caller surfaces
      reload();
    },
    [reload],
  );

  const remove = useCallback(
    async (id: number) => {
      await deleteReminder(id);
      reload();
    },
    [reload],
  );

  return { data, status, errMsg, warning, tab, setTab, reload, create, tick, remove };
}
