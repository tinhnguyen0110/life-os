"use client";
/* ============================================================
   useDecision — the /decision cockpit hook (FINANCE-ASSISTANT P1–P4).
   Fetches the 5 tower endpoints in PARALLEL and exposes each independently so the
   cockpit can render whatever loaded and degrade a section that errored (a thin
   tower must still show what it can). Types MIRROR the LIVE /decision/* payloads
   (lib/types.ts). SELF-DESCRIBING RAW: every q/W/delta is backend-computed — this
   hook only FETCHES; it never recomputes (a wrong number is a backend bug).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getDecisionWeight,
  getMacroCycle,
  getDecisionAllocation,
  getDecisionGuardian,
  getNavHistory,
  ApiError,
} from "@/lib/api";
import type {
  DecisionWeight,
  MacroCycle,
  DecisionAllocation,
  DecisionGuardian,
  NavHistory,
} from "@/lib/types";

export type DecisionStatus = "loading" | "error" | "ready";

/** One sub-section's state: its data (or null while loading/errored) + a per-section
 *  error message. A section that fails does NOT fail the whole cockpit. */
export interface Section<T> {
  data: T | null;
  errMsg: string;
}

export interface UseDecision {
  weight: Section<DecisionWeight>;
  macroCycle: Section<MacroCycle>;
  allocation: Section<DecisionAllocation>;
  guardian: Section<DecisionGuardian>;
  navHistory: Section<NavHistory>;
  /** "loading" until the parallel fetch settles; "error" only when ALL five failed
   *  (a hard backend-down); "ready" when at least one section resolved. */
  status: DecisionStatus;
  reload: () => void;
}

const EMPTY = <T,>(): Section<T> => ({ data: null, errMsg: "" });

function errText(e: unknown): string {
  return e instanceof ApiError ? e.message : (e as Error).message;
}

export function useDecision(): UseDecision {
  const [weight, setWeight] = useState<Section<DecisionWeight>>(EMPTY);
  const [macroCycle, setMacroCycle] = useState<Section<MacroCycle>>(EMPTY);
  const [allocation, setAllocation] = useState<Section<DecisionAllocation>>(EMPTY);
  const [guardian, setGuardian] = useState<Section<DecisionGuardian>>(EMPTY);
  const [navHistory, setNavHistory] = useState<Section<NavHistory>>(EMPTY);
  const [status, setStatus] = useState<DecisionStatus>("loading");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    // reset sections so a reload re-shows per-section pending (not stale data).
    setWeight(EMPTY); setMacroCycle(EMPTY); setAllocation(EMPTY);
    setGuardian(EMPTY); setNavHistory(EMPTY);

    // #71 PROGRESSIVE: update each section AS ITS OWN promise settles — do NOT
    // batch behind Promise.allSettled (that made the page wait for the SLOWEST
    // endpoint, e.g. weight ~3s, before ANY section painted → a long blank-hang).
    // settled[] tracks completion to flip status: "ready" on the FIRST success,
    // "error" only when ALL FIVE have settled AND every one failed (backend down).
    const results: ("ok" | "fail")[] = [];
    const mark = (outcome: "ok" | "fail") => {
      if (!alive) return;
      results.push(outcome);
      if (outcome === "ok") setStatus("ready"); // first success → render the tower
      else if (results.length === 5 && !results.includes("ok")) setStatus("error"); // all 5 failed
    };
    const wire = <T,>(p: Promise<{ data: T }>, set: (s: Section<T>) => void) => {
      p.then(
        (res) => { if (alive) { set({ data: res.data, errMsg: "" }); mark("ok"); } },
        (err) => { if (alive) { set({ data: null, errMsg: errText(err) }); mark("fail"); } },
      );
    };

    wire(getDecisionWeight(), setWeight);
    wire(getMacroCycle(), setMacroCycle);
    wire(getDecisionAllocation(), setAllocation);
    wire(getDecisionGuardian(), setGuardian);
    wire(getNavHistory(), setNavHistory);

    return () => {
      alive = false;
    };
  }, [nonce]);

  return { weight, macroCycle, allocation, guardian, navHistory, status, reload };
}

/* ------------------------------------------------------------------ */
/*  Render-only helpers — interpret the backend's numbers for display, */
/*  NEVER recompute them. Pure + null-safe.                            */
/* ------------------------------------------------------------------ */

/** Confidence band for the HONEST-CONFIDENCE render (§116). Buckets the backend's
 *  `confidence` 0–1 into a tone so low trust DE-EMPHASIZES (reads "thin"), never a
 *  false-confident green. Thresholds are a DISPLAY choice on the backend value,
 *  NOT a recomputation of confidence. */
export function confidenceBand(
  confidence: number | null | undefined,
): { label: string; tone: "low" | "mid" | "high"; cls: string } {
  if (confidence == null || !Number.isFinite(confidence)) {
    return { label: "—", tone: "low", cls: "faint" };
  }
  if (confidence < 0.4) return { label: "thấp", tone: "low", cls: "neg" };
  if (confidence < 0.7) return { label: "vừa", tone: "mid", cls: "mid" };
  return { label: "cao", tone: "high", cls: "pos" };
}

/** Map a layer key to a short Vietnamese label (render-only display alias). */
export function layerLabel(layer: string): string {
  switch (layer) {
    case "q_cycle":
      return "Chu kỳ (cycle)";
    case "q_macro":
      return "Vĩ mô (macro)";
    case "q_flow":
      return "Dòng tiền (flow)";
    case "s_asset":
      return "Tài sản nắm giữ (asset)";
    default:
      return layer;
  }
}

/** A signed delta (vsStaticGoldenPath pp) → display text + tone. 0 → neutral "—" tone.
 *  render-only: the delta is the BACKEND's number; this only formats + colors it. */
export function deltaText(pp: number | null | undefined): { text: string; cls: string } {
  if (pp == null || !Number.isFinite(pp) || pp === 0) return { text: "0pp", cls: "faint" };
  const sign = pp > 0 ? "+" : "−";
  return { text: `${sign}${Math.abs(pp).toFixed(0)}pp`, cls: pp > 0 ? "pos" : "neg" };
}
