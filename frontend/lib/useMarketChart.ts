"use client";
/* ============================================================
   useMarketChart (FE-2) — fetch price history for the market price chart.
   Reads GET /market/ohlc/{symbol} (close-derived OHLC candles, carries an honest
   "not real exchange candles" warning) via the existing read-only apiGet helper.
   NO backend edits, NO lib/api.ts / lib/types.ts edits (career lane owns those) —
   types for the chart payload live HERE, locally, mirroring market/router.py.

   Range → `hours` query param: 7d=168h, 30d=720h, all=8760h (≈1y cap; the series
   is whatever the backend has). Empty series is a valid state (raw-data-first) —
   the chart shows an empty-state, never NaN. 404 = untracked symbol (real error).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";

/** One close-derived OHLC bar (mirror of market service.candles() dict). */
export interface OhlcCandle {
  ts: string;       // ISO-8601 UTC bucket start
  open: number;
  high: number;
  low: number;
  close: number;
  ticks: number;    // how many real observations this bar aggregates
}

/** GET /market/ohlc/{symbol} payload. */
export interface OhlcData {
  symbol: string;
  interval: number; // minutes per bar
  candles: OhlcCandle[];
}

export type ChartRange = "7d" | "30d" | "all";
export type ChartStatus = "loading" | "error" | "ready";

/** Range → (hours window, candle interval minutes). Coarser bars for longer windows. */
export const RANGE_PARAMS: Record<ChartRange, { hours: number; interval: number }> = {
  "7d":  { hours: 168,  interval: 60 },   // hourly bars over a week
  "30d": { hours: 720,  interval: 240 },  // 4h bars over a month
  "all": { hours: 8760, interval: 720 },  // 12h bars, up to ~1y
};

export interface UseMarketChart {
  data: OhlcData | null;
  status: ChartStatus;
  errMsg: string;
  /** Honest "derived OHLC" warning from the backend (always present for ohlc). */
  warning: string | null;
  /** Close series oldest→newest (for the line/area path). */
  closes: number[];
  range: ChartRange;
  setRange: (r: ChartRange) => void;
  reload: () => void;
}

export function useMarketChart(symbol: string | null): UseMarketChart {
  const [data, setData] = useState<OhlcData | null>(null);
  const [status, setStatus] = useState<ChartStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [range, setRange] = useState<ChartRange>("7d");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!symbol) { setStatus("ready"); setData(null); setWarning(null); return; }
    let alive = true;
    setStatus("loading");
    setErrMsg("");
    const { hours, interval } = RANGE_PARAMS[range];
    (async () => {
      try {
        const res = await apiGet<OhlcData>(
          `/market/ohlc/${encodeURIComponent(symbol)}?hours=${hours}&interval=${interval}`,
        );
        if (!alive) return;
        setData(res.data ?? null);
        setWarning(res.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [symbol, range, nonce]);

  const closes = (data?.candles ?? []).map((c) => c.close);

  return { data, status, errMsg, warning, closes, range, setRange, reload };
}
