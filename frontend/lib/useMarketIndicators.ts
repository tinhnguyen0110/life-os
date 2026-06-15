"use client";
/* ============================================================
   useMarketIndicators (FE-2A) — technical-indicator overlays for MarketChart.
   Reads GET /market/indicators/{symbol}?indicators=sma,ema,bollinger&hours=N&full=true
   via the existing read-only apiGet. NO backend / api.ts / types.ts edits — the
   indicator payload types live HERE locally, mirroring market/router.py + ta.py.

   `hours` is passed to MATCH the chart's active range so the indicator series spans
   the SAME time window as the candles (both oldest→newest); the component then
   resamples each series to the candle count for a positional overlay.

   DEFENSIVE: a short window → backend returns latest=null + a per-indicator warning
   + an all-null series (NOT a 500). We expose that so the component hides an
   insufficient-data overlay gracefully instead of drawing rubbish.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";

/** One line indicator (SMA / EMA): aligned series + latest value + optional warning. */
export interface LineIndicator {
  period: number;
  latest: number | null;
  warning: string | null;
  series: (number | null)[];
}

/** Bollinger bands: three aligned series + latest band values. */
export interface BollingerIndicator {
  period: number;
  numStd: number;
  latestUpper: number | null;
  latestMiddle: number | null;
  latestLower: number | null;
  warning: string | null;
  upper: (number | null)[];
  middle: (number | null)[];
  lower: (number | null)[];
}

export interface IndicatorsData {
  symbol: string;
  points: number;
  asOf: string;
  indicators: {
    sma?: LineIndicator;
    ema?: LineIndicator;
    bollinger?: BollingerIndicator;
  };
}

export type IndicatorStatus = "idle" | "loading" | "error" | "ready";

export interface UseMarketIndicators {
  data: IndicatorsData | null;
  status: IndicatorStatus;
  errMsg: string;
  reload: () => void;
}

/**
 * @param symbol  tracked asset symbol (null → no fetch)
 * @param hours   window in hours — pass the SAME value the chart used for its range
 * @param enabled when false, skips the fetch entirely (overlays toggled off → no work)
 */
export function useMarketIndicators(
  symbol: string | null,
  hours: number,
  enabled: boolean,
): UseMarketIndicators {
  const [data, setData] = useState<IndicatorsData | null>(null);
  const [status, setStatus] = useState<IndicatorStatus>("idle");
  const [errMsg, setErrMsg] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!symbol || !enabled) { setStatus("idle"); return; }
    let alive = true;
    setStatus("loading");
    setErrMsg("");
    (async () => {
      try {
        const res = await apiGet<IndicatorsData>(
          `/market/indicators/${encodeURIComponent(symbol)}?indicators=sma,ema,bollinger&hours=${hours}&full=true`,
        );
        if (!alive) return;
        setData(res.data ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [symbol, hours, enabled, nonce]);

  return { data, status, errMsg, reload };
}
