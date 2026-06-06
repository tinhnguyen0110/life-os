"use client";
/* ============================================================
   HomeBriefTile — the S1 Home Brief tile, now LIVE (replaces the LAST coming-soon
   stub). Self-fetches /brief via getBrief so it fails INDEPENDENTLY (per-tile
   fail-open: brief down → this tile shows its own error, the rest of Home renders).
   briefcard: header (clock · template) + top-N numbered severity-styled priorities,
   click-through → /brief. HONEST-EMPTY: priorities=[] → calm "ổn định". render-only.
   NO AI "hỏi sâu" line (mock had one; this build is template, no chat).
   ============================================================ */
import { useEffect, useState } from "react";
import { getBrief, ApiError } from "@/lib/api";
import { fmtClock, orDash } from "@/lib/format";
import { useSafeRouter } from "@/lib/useNav";
import type { Brief, Severity } from "@/lib/types";

const SEV_CLS: Record<Severity, string> = { urgent: "urgent", warn: "warn", info: "info" };
const TOP_N = 3;

export function HomeBriefTile() {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [status, setStatus] = useState<"loading" | "error" | "ready">("loading");
  const [errMsg, setErrMsg] = useState("");
  const router = useSafeRouter();

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getBrief();
        if (!alive) return;
        if (res?.data == null) {
          setErrMsg("phản hồi không hợp lệ");
          setStatus("error");
          return;
        }
        setBrief(res.data);
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
  }, []);

  const priorities = (brief?.priorities ?? []).slice(0, TOP_N);

  return (
    <div
      className="card briefcard"
      style={{ cursor: "pointer" }}
      onClick={() => router.push("/brief")}
      data-testid="home-brief-tile"
    >
      <div className="bh">
        <div className="ic">✦</div>
        <b>Brief hôm nay</b>
        {status === "ready" && brief && (
          <span className="t">{fmtClock(brief.generatedAt)} · {orDash(brief.source, "template")}</span>
        )}
      </div>
      {status === "loading" && <div className="hint" style={{ padding: "10px 0" }} data-testid="home-brief-loading">Đang tạo…</div>}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "10px 0" }} data-testid="home-brief-error">Brief không tải được: {errMsg}</div>
      )}
      {status === "ready" && brief && (
        priorities.length === 0 ? (
          <div className="pr-calm" data-testid="home-brief-calm">✓ Ổn định — không có việc khẩn hôm nay.</div>
        ) : (
          priorities.map((p) => (
            <div className={`pr ${SEV_CLS[p.severity] ?? "info"}`} key={`${p.source}-${p.n}`} data-testid={`home-brief-pr-${p.n}`}>
              <span className="n">{String(p.n).padStart(2, "0")}</span>
              <span>{p.text}</span>
            </div>
          ))
        )
      )}
    </div>
  );
}
