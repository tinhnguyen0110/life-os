"use client";
/* ============================================================
   useNews — FE-5 News feed view data. GET /news/digest (neutral roll-up) + GET
   /news (headlines + source + published) with a tag filter, + POST /news/capture
   (the ONE write — capture-now). Types LOCAL (per dispatch). apiGet/apiPost.

   PER-PANEL ERROR ISOLATION (FE-4 lesson): digest and list each carry their OWN
   status — one panel's API error shows error+retry on THAT panel only, never kills
   the page. NEUTRAL: the FE adds no sentiment; it renders the backend's neutral
   digest verbatim. Capture is fail-closed: a failed POST surfaces + the page lives.
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { ApiError } from "@/lib/api";

export interface NewsItem {
  id: number;
  title: string;
  summary?: string | null;
  url: string;
  source: string;
  publishedTs: string;
  tags: string[];
}
export interface NewsDigestItem {
  title: string;
  source: string;
  url: string;
  publishedTs: string;
  tags: string[];
}
export interface NewsDigest {
  headline: string;
  items: NewsDigestItem[];
  count: number;
  asOf: string;
  note?: string | null;
}
export interface NewsCaptureResult {
  new: number;
  total: number;
}

export type PanelStatus = "loading" | "error" | "ready";

const EMPTY_DIGEST: NewsDigest = { headline: "", items: [], count: 0, asOf: "" };

export interface UseNews {
  /** digest panel (own status — per-panel isolation). */
  digest: NewsDigest;
  digestStatus: PanelStatus;
  digestErr: string;
  /** list panel (own status). */
  items: NewsItem[];
  listStatus: PanelStatus;
  listErr: string;
  /** active tag filter (null = all). */
  tag: string | null;
  setTag: (t: string | null) => void;
  reload: () => void;
  /** capture-now (POST /news/capture) → refetch. Returns {new,total}. THROWS on
   *  failure (fail-closed — caller surfaces; the page stays alive). */
  capture: () => Promise<NewsCaptureResult>;
}

export function useNews(limit = 30): UseNews {
  const [digest, setDigest] = useState<NewsDigest>(EMPTY_DIGEST);
  const [digestStatus, setDigestStatus] = useState<PanelStatus>("loading");
  const [digestErr, setDigestErr] = useState("");

  const [items, setItems] = useState<NewsItem[]>([]);
  const [listStatus, setListStatus] = useState<PanelStatus>("loading");
  const [listErr, setListErr] = useState("");

  const [tag, setTag] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  // digest panel (re-fetches on tag/nonce). Isolated try/catch → own status.
  useEffect(() => {
    let alive = true;
    setDigestStatus("loading");
    (async () => {
      try {
        const q = `?limit=${limit}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`;
        const res = await apiGet<NewsDigest>(`/news/digest${q}`);
        if (!alive) return;
        const d = res?.data;
        setDigest({
          headline: d?.headline ?? "",
          items: Array.isArray(d?.items) ? d.items : [],
          count: d?.count ?? 0,
          asOf: d?.asOf ?? "",
          note: d?.note ?? null,
        });
        setDigestStatus("ready");
      } catch (e) {
        if (!alive) return;
        setDigestErr(e instanceof ApiError ? e.message : (e as Error).message);
        setDigestStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [tag, nonce, limit]);

  // list panel (independent — a digest error must not blank the list, and vice-versa).
  useEffect(() => {
    let alive = true;
    setListStatus("loading");
    (async () => {
      try {
        const q = `?limit=${limit}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`;
        const res = await apiGet<{ items: NewsItem[] }>(`/news${q}`);
        if (!alive) return;
        setItems(Array.isArray(res?.data?.items) ? res.data.items : []);
        setListStatus("ready");
      } catch (e) {
        if (!alive) return;
        setListErr(e instanceof ApiError ? e.message : (e as Error).message);
        setListStatus("error");
      }
    })();
    return () => { alive = false; };
  }, [tag, nonce, limit]);

  const capture = useCallback(async (): Promise<NewsCaptureResult> => {
    const res = await apiPost<NewsCaptureResult>("/news/capture", {}); // throws → caller surfaces
    reload();
    return res?.data ?? { new: 0, total: 0 };
  }, [reload]);

  return { digest, digestStatus, digestErr, items, listStatus, listErr, tag, setTag, reload, capture };
}
