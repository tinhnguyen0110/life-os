"use client";
/* ============================================================
   News feed view · /news (FE-5). Read-mostly: a neutral digest roll-up + the full
   headline list (source + published time, clickable source links) + tag-filter
   chips + a "Capture now" button (the ONE write → POST /news/capture).

   PER-PANEL ERROR ISOLATION (FE-4 lesson): digest + list each have their OWN
   status — one panel erroring shows error+retry on THAT panel only, the page lives.
   NEUTRAL: the digest is rendered verbatim; the FE adds no sentiment/advice.
   Capture is fail-closed: a failed POST surfaces inline + the page stays alive.
   ============================================================ */
import { useState } from "react";
import { useNews, type NewsItem, type NewsDigestItem } from "@/lib/useNews";
import { ApiError } from "@/lib/api";

const TAGS = ["BTC", "CRYPTO", "ETH", "FINANCE", "MACRO", "NASDAQ", "SOL", "SPX"];

function ago(iso: string): string {
  // descriptive published time; falls back to the raw string if unparseable.
  return iso ? iso.replace("T", " ").slice(0, 16) : "";
}

function DigestRow({ it }: { it: NewsDigestItem }) {
  return (
    <a className="news-digest-row" href={it.url} target="_blank" rel="noreferrer" data-testid="news-digest-row">
      <div className="news-digest-title">{it.title}</div>
      <div className="news-digest-meta faint">
        {it.source} · {ago(it.publishedTs)}
        {it.tags?.length ? <span className="news-tags"> · {it.tags.join(", ")}</span> : null}
      </div>
    </a>
  );
}

function HeadlineRow({ it }: { it: NewsItem }) {
  return (
    <div className="news-row" data-testid="news-row">
      <a className="news-row-title" href={it.url} target="_blank" rel="noreferrer" data-testid="news-row-link">
        {it.title}
      </a>
      {it.summary && <div className="news-row-summary mut">{it.summary}</div>}
      <div className="news-row-meta faint">
        <span className="news-src">{it.source}</span> · {ago(it.publishedTs)}
        {it.tags?.map((t) => <span key={t} className="news-tag-chip sm" data-testid="news-row-tag">{t}</span>)}
      </div>
    </div>
  );
}

export default function NewsPage() {
  const { digest, digestStatus, digestErr, items, listStatus, listErr, tag, setTag, reload, capture } = useNews();
  const [capturing, setCapturing] = useState(false);
  const [captureMsg, setCaptureMsg] = useState("");
  const [captureErr, setCaptureErr] = useState("");

  async function onCapture() {
    setCaptureErr(""); setCaptureMsg(""); setCapturing(true);
    try {
      const res = await capture();
      setCaptureMsg(`✓ Đã capture ${res.new} tin mới (tổng ${res.total}).`);
    } catch (e) {
      // fail-closed: surface, page stays alive
      setCaptureErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setCapturing(false);
    }
  }

  return (
    <section className="view" data-screen="NEWS" data-testid="news-screen">
      <div className="vtitle">
        <h1>Tin tức</h1>
        <span className="sub">digest trung lập + headline (mỗi tin kèm nguồn) — không bình luận, không khuyến nghị</span>
        <span className="sp" style={{ flex: 1 }} />
        <button className="btn accent" type="button" onClick={onCapture} disabled={capturing} data-testid="news-capture">
          {capturing ? "Đang capture…" : "Capture now"}
        </button>
      </div>

      {captureMsg && <div className="hint pos" style={{ marginBottom: 10 }} data-testid="news-capture-ok">{captureMsg}</div>}
      {captureErr && <div className="hint neg" style={{ marginBottom: 10 }} data-testid="news-capture-error">⚠ {captureErr}</div>}

      {/* tag filter chips */}
      <div className="news-filter" data-testid="news-filter">
        <button type="button" className={`news-tag-chip ${tag === null ? "on" : ""}`} onClick={() => setTag(null)} data-testid="news-tag-all">tất cả</button>
        {TAGS.map((t) => (
          <button key={t} type="button" className={`news-tag-chip ${tag === t ? "on" : ""}`} onClick={() => setTag(t)} data-testid={`news-tag-${t}`}>
            {t}
          </button>
        ))}
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1.4fr", alignItems: "start", gap: 14 }}>
        {/* DIGEST panel — own status (per-panel isolation) */}
        <div className="panel" data-testid="news-digest-panel">
          <div className="phead"><span className="kicker">Digest · roll-up trung lập</span></div>
          {digestStatus === "loading" ? (
            <div className="hint" style={{ padding: "16px 14px" }} data-testid="news-digest-loading">Đang tải digest…</div>
          ) : digestStatus === "error" ? (
            <div className="hint neg" style={{ padding: "16px 14px" }} data-testid="news-digest-error">
              {digestErr || "Lỗi digest."} <button className="link" type="button" onClick={reload}>thử lại</button>
            </div>
          ) : digest.items.length === 0 ? (
            <div className="hint" style={{ padding: "16px 14px" }} data-testid="news-digest-empty">
              Chưa có tin nào được capture{tag ? ` cho tag ${tag}` : ""}. Bấm “Capture now”.
            </div>
          ) : (
            <>
              {digest.headline && <div className="news-digest-headline" data-testid="news-digest-headline">{digest.headline}</div>}
              <div className="news-digest-list">{digest.items.map((it, i) => <DigestRow key={`${it.url}-${i}`} it={it} />)}</div>
              <div className="news-digest-foot faint">{digest.count} tin · {ago(digest.asOf)}</div>
            </>
          )}
        </div>

        {/* LIST panel — own status (isolated from digest) */}
        <div className="panel" data-testid="news-list-panel">
          <div className="phead">
            <span className="kicker">Headlines{tag ? ` · ${tag}` : ""}</span>
            <span className="hint" style={{ marginLeft: "auto" }}>{listStatus === "ready" ? items.length : "…"}</span>
          </div>
          {listStatus === "loading" ? (
            <div className="hint" style={{ padding: "16px 14px" }} data-testid="news-list-loading">Đang tải tin…</div>
          ) : listStatus === "error" ? (
            <div className="hint neg" style={{ padding: "16px 14px" }} data-testid="news-list-error">
              {listErr || "Lỗi danh sách tin."} <button className="link" type="button" onClick={reload}>thử lại</button>
            </div>
          ) : items.length === 0 ? (
            <div className="hint" style={{ padding: "16px 14px" }} data-testid="news-list-empty">
              Không có headline nào{tag ? ` cho tag ${tag}` : ""}.
            </div>
          ) : (
            <div className="news-list">{items.map((it) => <HeadlineRow key={it.id} it={it} />)}</div>
          )}
        </div>
      </div>
    </section>
  );
}
