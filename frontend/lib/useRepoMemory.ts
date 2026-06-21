"use client";
/* ============================================================
   useRepoMemory — #64-P3 Repo Memory (REPOMEM): read a repo's fresh code_insight
   + its durable repo_memory note.
   GET /code_insight?repo=<name>      (fresh-now structural read)
   GET /code_insight/memory?repo=<name> (the durable Repos/<name> note)
   Types mirror the FROZEN #64 BE schema. RENDER-ONLY: the backend computes both;
   the FE displays. honest-empty: code_insight found:false → "not found"; repo_memory
   found:false → "no note yet" — both real empty-states, NOT errors.

   The two reads are INDEPENDENT — each settles on its own (one slow/failing endpoint
   never blocks the other panel). `repo == null` (nothing picked yet) → idle.
   Selecting a new repo re-fetches both; an `alive`/`reqId` guard drops stale responses
   from a previous selection (no flash of the wrong repo's data).
   ============================================================ */
import { useCallback, useEffect, useRef, useState } from "react";
import { getCodeInsight, getRepoMemory, ApiError } from "@/lib/api";
import type { CodeInsight, RepoMemory } from "@/lib/types";

/** idle = no repo picked yet; loading/error/ready per-panel. */
export type PanelStatus = "idle" | "loading" | "error" | "ready";

export interface UseRepoMemory {
  /** the currently-selected repo (null until the user picks one). */
  repo: string | null;
  select: (repo: string) => void;
  /** re-fetch both panels for the current repo. */
  reload: () => void;

  insight: CodeInsight | null;
  insightStatus: PanelStatus;
  insightErr: string;

  memory: RepoMemory | null;
  memoryStatus: PanelStatus;
  memoryErr: string;
}

export function useRepoMemory(initialRepo: string | null = null): UseRepoMemory {
  const [repo, setRepo] = useState<string | null>(initialRepo);
  const [nonce, setNonce] = useState(0);

  const [insight, setInsight] = useState<CodeInsight | null>(null);
  const [insightStatus, setInsightStatus] = useState<PanelStatus>(initialRepo ? "loading" : "idle");
  const [insightErr, setInsightErr] = useState("");

  const [memory, setMemory] = useState<RepoMemory | null>(null);
  const [memoryStatus, setMemoryStatus] = useState<PanelStatus>(initialRepo ? "loading" : "idle");
  const [memoryErr, setMemoryErr] = useState("");

  // monotonic request id — only the LATEST selection's responses may land (drops
  // a slow previous-repo response that resolves after a newer pick).
  const reqId = useRef(0);

  const select = useCallback((next: string) => setRepo(next), []);
  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (repo == null) {
      setInsightStatus("idle");
      setMemoryStatus("idle");
      return;
    }
    const id = ++reqId.current;
    const fresh = () => id === reqId.current;

    setInsightStatus("loading");
    setInsightErr("");
    setMemoryStatus("loading");
    setMemoryErr("");

    // code_insight — independent settle
    (async () => {
      try {
        const res = await getCodeInsight(repo);
        if (!fresh()) return;
        const d = res?.data;
        if (d == null || typeof d.found !== "boolean" || !Array.isArray(d.structure)) {
          setInsightErr("phản hồi không hợp lệ");
          setInsightStatus("error");
          return;
        }
        setInsight(d);
        setInsightStatus("ready");
      } catch (e) {
        if (!fresh()) return;
        setInsightErr(e instanceof ApiError ? e.message : (e as Error).message);
        setInsightStatus("error");
      }
    })();

    // repo_memory — independent settle
    (async () => {
      try {
        const res = await getRepoMemory(repo);
        if (!fresh()) return;
        const d = res?.data;
        if (d == null || typeof d.found !== "boolean") {
          setMemoryErr("phản hồi không hợp lệ");
          setMemoryStatus("error");
          return;
        }
        setMemory(d);
        setMemoryStatus("ready");
      } catch (e) {
        if (!fresh()) return;
        setMemoryErr(e instanceof ApiError ? e.message : (e as Error).message);
        setMemoryStatus("error");
      }
    })();

    // No cleanup increment needed: the NEXT effect run does `++reqId.current` first,
    // so this run's captured `id` !== reqId.current → its `fresh()` returns false and
    // any late response is dropped. One invalidation point keeps the guard simple.
  }, [repo, nonce]);

  return {
    repo, select, reload,
    insight, insightStatus, insightErr,
    memory, memoryStatus, memoryErr,
  };
}
