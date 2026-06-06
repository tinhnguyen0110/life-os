"use client";
/* ============================================================
   useHome — S1 Command Center aggregator. Fetches the 3 source endpoints
   (finance + projects + market) and exposes them per-tile with PER-TILE
   FAIL-OPEN: one endpoint down NEVER blanks the whole screen — that tile shows
   its own error, the others render, and a top-level warning names what failed.

   Uses Promise.allSettled (not Promise.all) so a single rejection can't reject
   the batch. RENDER-ONLY: every number comes from the source endpoints (already
   mirrored types) — the Home screen formats + displays, never recomputes.

   No new backend contract — composes existing FinanceOverview / ProjectsListData
   / MarketData. So this is buildable + verifiable immediately (no schema gate).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { getFinance, getProjects, getMarket, ApiError } from "@/lib/api";
import type { FinanceOverview, ProjectsListData, MarketData, ApiResponse } from "@/lib/types";

export type TileStatus = "loading" | "error" | "ready";

/** One source tile: its data (or null) + independent status + error message. */
export interface Tile<T> {
  data: T | null;
  status: TileStatus;
  errMsg: string;
}

export interface HomeData {
  finance: Tile<FinanceOverview>;
  projects: Tile<ProjectsListData>;
  market: Tile<MarketData>;
}

export interface UseHome extends HomeData {
  /** overall: "loading" until all settle, then "ready" (even if some tiles errored). */
  status: "loading" | "ready";
  /** human summary of which tiles failed (null if all ok) — for the top warning bar. */
  warning: string | null;
  reload: () => void;
}

const loadingTile = <T,>(): Tile<T> => ({ data: null, status: "loading", errMsg: "" });

function errOf(e: unknown): string {
  return e instanceof ApiError ? e.message : (e as Error).message;
}

export function useHome(): UseHome {
  const [finance, setFinance] = useState<Tile<FinanceOverview>>(loadingTile);
  const [projects, setProjects] = useState<Tile<ProjectsListData>>(loadingTile);
  const [market, setMarket] = useState<Tile<MarketData>>(loadingTile);
  const [status, setStatus] = useState<"loading" | "ready">("loading");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    setFinance(loadingTile);
    setProjects(loadingTile);
    setMarket(loadingTile);

    (async () => {
      // allSettled → one rejection never sinks the others (per-tile fail-open).
      const [f, p, m] = await Promise.allSettled([getFinance(), getProjects(), getMarket()]);
      if (!alive) return;

      // TRULY fail-open: a rejection OR a fulfilled-but-malformed response
      // (value/value.data missing — an unexpected 200 body, proxy returning {},
      // a serialization edge, or an exhausted test mock) degrades to that tile's
      // ERROR state. It must NEVER throw here (an unhandled rejection in this IIFE
      // would crash Home — the exact thing "fail-open" exists to prevent).
      const resolve = <T,>(r: PromiseSettledResult<ApiResponse<T>>): Tile<T> => {
        if (r.status === "rejected") return { data: null, status: "error", errMsg: errOf(r.reason) };
        const data = r.value?.data;
        return data != null
          ? { data, status: "ready", errMsg: "" }
          : { data: null, status: "error", errMsg: "phản hồi không hợp lệ" };
      };

      setFinance(resolve(f));
      setProjects(resolve(p));
      setMarket(resolve(m));
      setStatus("ready");
    })();

    return () => {
      alive = false;
    };
  }, [nonce]);

  // Top-level warning names the failed tiles (fail-open is visible, not silent).
  const failed: string[] = [];
  if (finance.status === "error") failed.push("Tài chính");
  if (projects.status === "error") failed.push("Dự án");
  if (market.status === "error") failed.push("Thị trường");
  const warning =
    failed.length > 0
      ? `Không tải được: ${failed.join(", ")} — các phần còn lại vẫn hiển thị.`
      : null;

  return { finance, projects, market, status, warning, reload };
}
