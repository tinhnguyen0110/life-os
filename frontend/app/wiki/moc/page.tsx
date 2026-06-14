"use client";
/* ============================================================
   W5 — MOC / Synthesize · /wiki/moc. The spec's "payoff" surface, built to the
   W5a SUBSTRATE contract (GET /wiki/clusters + GET /wiki/mocs).

   ARCHITECTURE (D-W5.4 + ARCH §11 — NO in-app LLM): clusters are detected by CODE
   (deterministic graph community detection); the DRAFTING of an MOC (scaffold +
   throughline + contradiction surfacing) is the EXTERNAL Claude Code (MCP) job.
   So this screen is the SUBSTRATE LISTING, NOT the mock's fake-AI workspace:
     (1) existing MOC notes (noteType="moc", ratified via P1)
     (2) cluster candidates = "MOC suggestions" (members + size/density/importance)
         with an HONEST "ask Claude Code to draft" hint — we do NOT fabricate a draft.
   importance is ADVISORY (D-W5.3) — it ranks, never gates.
   States: loading · error (both endpoints down) · empty (no clusters / no mocs) · data.
   ============================================================ */
import Link from "next/link";
import { useWikiMoc } from "@/lib/useWiki";
import { Icon } from "@/lib/icons";
import type { WikiCluster, WikiMoc } from "@/lib/types";

function MocRow({ m }: { m: WikiMoc }) {
  return (
    <Link href={`/wiki/${m.id}`} className="wlist-row clickable" data-testid="moc-row">
      <span className="wprop-kind-badge" style={{ color: "var(--amber)", background: "color-mix(in oklch,var(--amber) 14%,transparent)" }}>
        <Icon name="i-moc" /> MOC
      </span>
      <div className="wlr-body">
        <div className="wlr-t">{m.title ?? <span className="faint">#{m.id} — chưa có title</span>}</div>
        <div className="wlr-s mut">{m.outboundLinks} liên kết ra · cập nhật {m.updated}</div>
      </div>
      <span className={`wstatus ${m.status}`}>{m.status}</span>
    </Link>
  );
}

function ClusterCard({ c }: { c: WikiCluster }) {
  return (
    <div className="wcluster" data-testid="moc-cluster">
      <div className="wcluster-top">
        <b>{c.suggestedTitle ?? `Cụm ${c.size} note`}</b>
        <span className="wconf" data-testid="moc-cluster-meta">
          {c.size} note · mật độ {(c.density * 100).toFixed(0)}% · điểm {c.importance.toFixed(1)}
        </span>
      </div>
      <div className="wcluster-members">
        {c.members.map((mem) => (
          <Link key={mem.id} href={`/wiki/${mem.id}`} className="tagchip clickable" data-testid="moc-cluster-member">
            #{mem.id} {mem.title ? mem.title.slice(0, 18) : ""}
          </Link>
        ))}
      </div>
      {/* HONEST: drafting is LLM-side (no in-app AI). Hint, not a fake draft button. */}
      <div className="hint" data-testid="moc-cluster-hint" style={{ marginTop: 10, lineHeight: 1.5 }}>
        ◇ Những note này cụm lại — ứng viên Map of Content. Nhờ <b>Claude Code (MCP)</b> đọc cụm + nháp MOC
        (nối members + nêu throughline) → đề xuất vào hàng đợi <Link className="link" href="/wiki/proposals">duyệt</Link>. AI nháp, bạn duyệt.
      </div>
    </div>
  );
}

export default function WikiMocPage() {
  const { clusters, mocs, status, errMsg, clustersUnavailable, mocsUnavailable, reload } = useWikiMoc();

  if (status === "loading") {
    return <div className="hint" style={{ padding: "24px 4px" }} data-testid="moc-loading">Đang tải MOC + cụm…</div>;
  }
  if (status === "error") {
    return (
      <div className="hint" style={{ padding: "24px 4px", color: "var(--red)" }} data-testid="moc-screen-error">
        {errMsg || "Không tải được MOC."}
        <button type="button" className="btn ghost" style={{ marginLeft: 12 }} onClick={reload}>Thử lại</button>
      </div>
    );
  }

  return (
    <div data-testid="moc-screen">
      <div className="vtitle">
        <h1>MOC · Synthesize</h1>
        <span className="sub">{mocs.length} MOC · {clusters.length} cụm ứng viên</span>
        <span className="sp" style={{ flex: 1 }} />
        <Link href="/wiki/graph" className="btn" data-testid="moc-graph-link">
          <Icon name="i-graph" /> Graph
        </Link>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "start" }}>
        {/* existing MOC notes */}
        <div className="panel">
          <div className="phead">
            <span className="kicker">MOC notes · noteType=moc</span>
            <span className="hint" style={{ marginLeft: "auto" }}>{mocs.length}</span>
          </div>
          <div className="wlist" data-testid="moc-list">
            {mocsUnavailable ? (
              <div className="wlist-empty" data-testid="moc-list-unavailable" style={{ color: "var(--amber)" }}>
                ⚠ Tạm thời không tải được danh sách MOC. <button type="button" className="link" onClick={reload} style={{ background: "none", border: 0, cursor: "pointer" }}>Thử lại</button>
              </div>
            ) : mocs.length === 0 ? (
              <div className="wlist-empty" data-testid="moc-list-empty">
                Chưa có MOC nào. MOC ra đời khi bạn duyệt một <Link className="link" href="/wiki/proposals">đề xuất MOC</Link> (Claude
                Code nháp từ một cụm) — MOC = note workstation nối các note liên quan + nêu throughline.
              </div>
            ) : (
              mocs.map((m) => <MocRow key={m.id} m={m} />)
            )}
          </div>
        </div>

        {/* cluster candidates = MOC suggestions */}
        <div className="panel">
          <div className="phead">
            <span className="kicker">Cụm ứng viên · MOC suggestions</span>
            <span className="hint" style={{ marginLeft: "auto" }}>{clusters.length}</span>
          </div>
          <div style={{ padding: 7, display: "flex", flexDirection: "column", gap: 8 }} data-testid="moc-clusters">
            {clustersUnavailable ? (
              <div className="wcluster-empty" data-testid="moc-clusters-unavailable" style={{ color: "var(--amber)" }}>
                ⚠ Tạm thời không tải được cụm (clusters). <button type="button" className="link" onClick={reload} style={{ background: "none", border: 0, cursor: "pointer" }}>Thử lại</button>
              </div>
            ) : clusters.length === 0 ? (
              <div className="wcluster-empty" data-testid="moc-clusters-empty">
                Chưa có cụm. Cụm = nhóm ≥3 note nối chặt (mật độ link cao) — phát hiện bằng graph community detection
                (deterministic, không AI). Liên kết note nhiều hơn để các cụm xuất hiện.
              </div>
            ) : (
              clusters.map((c, i) => <ClusterCard key={i} c={c} />)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
