"use client";
/* ============================================================
   useMarketOverview (FE-4) — multi-symbol market analytics for the overview
   dashboard. Fetches GET /market/compare + /market/correlation via the existing
   read-only apiGet. NO backend / api.ts / types.ts edits — payload types are
   LOCAL here, mirroring market/router.py + service.{compare,correlation}.

   The two fetches are INDEPENDENT (separate status/error) so one panel failing
   never blanks the other. Correlation needs ≥2 symbols; with <2 the backend 422s
   — we DON'T fire it (and surface a "need ≥2" hint) so a 422 never breaks the page.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, ApiError } from "@/lib/api";

export type Trend = "up" | "down" | "flat";

/** One row of GET /market/compare → data.comparison[]. */
export interface CompareRow {
  symbol: string;
  changePct: number | null;
  volatility: number | null;
  rsi: number | null;
  trend: Trend | null;
  points: number;
}

export interface CompareData {
  window_hours: number;
  asOf: string;
  comparison: CompareRow[];
}

/** GET /market/correlation → pairwise Pearson matrix (values in [-1,1], null = n/a). */
export interface CorrelationData {
  symbols: string[];
  matrix: Record<string, Record<string, number | null>>;
  window_hours: number;
  asOf: string;
}

export type PanelStatus = "idle" | "loading" | "error" | "ready";

export interface UseMarketOverview {
  compare: CompareData | null;
  compareStatus: PanelStatus;
  compareErr: string;
  compareWarning: string | null;

  correlation: CorrelationData | null;
  corrStatus: PanelStatus;
  corrErr: string;
  corrWarning: string | null;
  /** True when <2 symbols → correlation is intentionally not fetched (show a hint). */
  corrNeedsMore: boolean;

  reload: () => void;
}

/**
 * Heatmap cell style for a correlation value r ∈ [-1, 1].
 * - null / non-finite → neutral grey "n/a" (NEVER tinted — honest empty).
 * - r ≥ 0 → green tint scaled by |r| (1.0 = strong green).
 * - r < 0 → red tint scaled by |r|.
 * Returns a background rgba + a readable text color. Pure (unit-testable).
 */
export function corrCellStyle(r: number | null | undefined): { background: string; color: string; isNA: boolean } {
  if (r == null || !Number.isFinite(r)) {
    return { background: "var(--bg-2)", color: "var(--tx-2)", isNA: true };
  }
  const clamped = Math.max(-1, Math.min(1, r));
  const mag = Math.abs(clamped);
  // alpha 0.08..0.6 by magnitude so weak corr is faint, strong is vivid
  const alpha = (0.08 + mag * 0.52).toFixed(3);
  const rgb = clamped >= 0 ? "52, 211, 153" /* green */ : "248, 113, 113" /* red */;
  return {
    background: `rgba(${rgb}, ${alpha})`,
    color: mag > 0.55 ? "var(--tx-0)" : "var(--tx-1)",
    isNA: false,
  };
}

/** Format a correlation value for display: null → "n/a", else 2 decimals. */
export function fmtCorr(r: number | null | undefined): string {
  if (r == null || !Number.isFinite(r)) return "n/a";
  return r.toFixed(2);
}

/** Stable, de-duped, uppercased symbol list (order preserved). */
function normSymbols(symbols: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const s of symbols) {
    const u = (s ?? "").trim().toUpperCase();
    if (u && !seen.has(u)) { seen.add(u); out.push(u); }
  }
  return out;
}

export function useMarketOverview(symbols: string[], hours = 720): UseMarketOverview {
  const syms = normSymbols(symbols);
  const key = syms.join(",");

  const [compare, setCompare] = useState<CompareData | null>(null);
  const [compareStatus, setCompareStatus] = useState<PanelStatus>("idle");
  const [compareErr, setCompareErr] = useState("");
  const [compareWarning, setCompareWarning] = useState<string | null>(null);

  const [correlation, setCorrelation] = useState<CorrelationData | null>(null);
  const [corrStatus, setCorrStatus] = useState<PanelStatus>("idle");
  const [corrErr, setCorrErr] = useState("");
  const [corrWarning, setCorrWarning] = useState<string | null>(null);

  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);

  const corrNeedsMore = syms.length < 2;

  // compare — works with ≥1 symbol (backend min_n may differ, error handled per-panel).
  useEffect(() => {
    if (syms.length === 0) { setCompareStatus("idle"); return; }
    let alive = true;
    setCompareStatus("loading"); setCompareErr("");
    (async () => {
      try {
        const res = await apiGet<CompareData>(`/market/compare?symbols=${encodeURIComponent(key)}&hours=${hours}`);
        if (!alive) return;
        // Coerce defensively: a malformed/unexpected body must never crash the table
        // (comparison MUST be an array). Missing → empty, rendered as the empty-state.
        const d = res.data;
        setCompare(d ? { ...d, comparison: Array.isArray(d.comparison) ? d.comparison : [] } : null);
        setCompareWarning(res.warning ?? null);
        setCompareStatus("ready");
      } catch (e) {
        if (!alive) return;
        setCompareErr(e instanceof ApiError ? e.message : (e as Error).message);
        setCompareStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [key, hours, nonce]); // eslint-disable-line react-hooks/exhaustive-deps

  // correlation — needs ≥2 symbols; with <2 we DON'T fetch (avoids a guaranteed 422).
  useEffect(() => {
    if (corrNeedsMore) { setCorrStatus("idle"); setCorrelation(null); return; }
    let alive = true;
    setCorrStatus("loading"); setCorrErr("");
    (async () => {
      try {
        const res = await apiGet<CorrelationData>(`/market/correlation?symbols=${encodeURIComponent(key)}&hours=${hours}`);
        if (!alive) return;
        // Coerce: symbols MUST be an array + matrix an object, else the heatmap render crashes.
        const d = res.data;
        setCorrelation(d ? { ...d, symbols: Array.isArray(d.symbols) ? d.symbols : [], matrix: d.matrix ?? {} } : null);
        setCorrWarning(res.warning ?? null);
        setCorrStatus("ready");
      } catch (e) {
        if (!alive) return;
        setCorrErr(e instanceof ApiError ? e.message : (e as Error).message);
        setCorrStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [key, hours, nonce, corrNeedsMore]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    compare, compareStatus, compareErr, compareWarning,
    correlation, corrStatus, corrErr, corrWarning, corrNeedsMore,
    reload,
  };
}
