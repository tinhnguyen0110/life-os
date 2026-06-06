"use client";
/* ============================================================
   useMarket — client hook for the S8 Market screen + the live TickerTape.
   Fetches GET /market → {quotes, triggers, macro, alertHistory} and exposes a
   ticker-ready item list, falling back to TICKER_MOCK on error/empty so the
   bottom tape (always-visible shell furniture) never blanks.

   Types are the FROZEN mirror of backend market/schema.py (see lib/types.ts) —
   no placeholders. render-only: changePct/distance/state are server-derived; the
   FE only formats + colors. null changePct → "—" (never NaN / fabricated).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { TICKER_MOCK, type TickerItem } from "@/lib/ticker-mock";
import type { MarketData, AssetQuote, AlertRule, AlertRuleInput } from "@/lib/types";

export type MarketStatus = "loading" | "error" | "ready";

const EMPTY_MARKET: MarketData = { quotes: [], triggers: [], macro: [], alertHistory: [] };

/** Map a quote → the ticker tape's display item (string px + signed % + dir). */
export function quoteToTicker(q: AssetQuote): TickerItem {
  const change = q.changePct ?? 0;
  const dir: "pos" | "neg" = change < 0 ? "neg" : "pos";
  const px =
    Number.isFinite(q.price)
      ? q.price.toLocaleString("en-US", { maximumFractionDigits: 2 })
      : "—";
  const chg =
    q.changePct != null && Number.isFinite(q.changePct)
      ? `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`
      : "—";
  return { sym: q.symbol, px, chg, dir };
}

export interface UseMarket {
  data: MarketData;
  status: MarketStatus;
  errMsg: string;
  warning: string | null;
  /** quotes mapped to the bottom-tape shape; falls back to mock on empty/error. */
  tickerItems: TickerItem[];
  /** configured alert rules (carry server-assigned ids for delete). */
  rules: AlertRule[];
  reload: () => void;
  /** add/replace an alert rule (POST /market/alerts; upsert by symbol+op server-side). */
  setAlert: (rule: AlertRuleInput) => Promise<void>;
  /** delete an alert rule BY ID (DELETE /market/alerts/{id}). */
  deleteAlert: (ruleId: string) => Promise<void>;
  /** find the rule id for a symbol+op (trigger rows lack id; map via rules). */
  ruleIdFor: (symbol: string, op: AlertRule["op"]) => string | undefined;
}

export function useMarket(): UseMarket {
  const [data, setData] = useState<MarketData>(EMPTY_MARKET);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [status, setStatus] = useState<MarketStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const res = await apiGet<MarketData>("/market");
        if (!alive) return;
        setData({ ...EMPTY_MARKET, ...res.data });
        setWarning(res.warning ?? null);
        setStatus("ready");
        // Rules carry the ids needed to delete; fetch alongside (non-fatal).
        try {
          const r = await apiGet<AlertRule[]>("/market/alerts");
          if (alive) setRules(r.data ?? []);
        } catch {
          if (alive) setRules([]);
        }
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

  const setAlert = useCallback(
    async (rule: AlertRuleInput) => {
      await apiPost("/market/alerts", rule);
      reload();
    },
    [reload],
  );

  const deleteAlert = useCallback(
    async (ruleId: string) => {
      await apiDelete(`/market/alerts/${encodeURIComponent(ruleId)}`);
      reload();
    },
    [reload],
  );

  const ruleIdFor = useCallback(
    (symbol: string, op: AlertRule["op"]) =>
      rules.find((r) => r.symbol === symbol && r.op === op)?.id,
    [rules],
  );

  const quotes = data.quotes ?? [];
  // Tape must never blank → fall back to mock when no live quotes (error/empty).
  const tickerItems = quotes.length > 0 ? quotes.map(quoteToTicker) : TICKER_MOCK;

  return { data, status, errMsg, warning, tickerItems, rules, reload, setAlert, deleteAlert, ruleIdFor };
}
