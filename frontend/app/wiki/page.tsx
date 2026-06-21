"use client";
/* ============================================================
   W1 — Wiki Home / Vault Overview · /wiki. Ported from mock screens-wiki.js
   SCREENS.wiki + wiki.css (W1 block). The vault entrance: "how's my knowledge
   vault + what do I need to triage today".

   Live from GET /wiki/overview (stats + inbox/orphan summaries + op-log +
   proposalCount) and GET /wiki/search?q= (FTS5 quick search box).

   HONEST-MIRROR (M1, no embedded AI):
   - proposalCount is ALWAYS 0 (AI proposals are M4) → render the honest empty
     "no proposals" state, never a fabricated queue.
   - pctWithLink is null on an empty vault → show "—", not "0%".
   - inbox/orphans are SUMMARIES (slice 4) — full triage lives on W3, full graph on W4.
   States: loading · error · empty-vault (0 notes) · ready.
   ============================================================ */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useWikiOverview } from "@/lib/useWiki";
import { searchWiki } from "@/lib/api";
import { Icon } from "@/lib/icons";
import { WikiImport } from "@/components/WikiImport";
import type {
  WikiInboxItem,
  WikiOrphan,
  WikiActivity,
  WikiOpKind,
  WikiSearchHit,
} from "@/lib/types";

/** op-log label + color (mirrors mock OP map). */
const OP: Record<WikiOpKind, { lbl: string; color: string }> = {
  create: { lbl: "create", color: "var(--green)" },
  edit: { lbl: "edit", color: "var(--blue)" },
  link: { lbl: "link", color: "var(--accent)" },
  link_candidate: { lbl: "candidate", color: "var(--amber)" },
  refine: { lbl: "refine", color: "var(--violet)" },
  merge: { lbl: "merge", color: "var(--violet)" },
  moc_proposal: { lbl: "MOC", color: "var(--amber)" },
  delete: { lbl: "delete", color: "var(--red)" },
};

function StatTile({ label, value, sub, cls }: { label: string; value: string | number; sub: string; cls?: string }) {
  return (
    <div className="wtile" data-testid="wtile">
      <span className="wtile-l">{label}</span>
      <span className={`wtile-v ${cls ?? ""}`} data-testid="wtile-v">{value}</span>
      <span className="wtile-s">{sub}</span>
    </div>
  );
}

export default function WikiVaultPage() {
  const { overview, status, errMsg, warning, reload } = useWikiOverview();
  const router = useRouter();

  /* ---- #93 import modal ----
     onImported fires on a successful import but we do NOT reload the overview WHILE the
     modal is open: reload() flips the page to status="loading", which re-renders the
     tree and would remount the modal (destroying the results the user needs to read).
     Instead we mark "vault is stale" and reload ONCE, on modal close — so results stay
     stable in the modal AND the tree refreshes when the user is done. */
  const [showImport, setShowImport] = useState(false);
  const importedDirty = useRef(false);
  const closeImport = useCallback(() => {
    setShowImport(false);
    if (importedDirty.current) { importedDirty.current = false; reload(); }
  }, [reload]);

  /* ---- FTS quick search (debounced) ---- */
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<WikiSearchHit[]>([]);
  const [searched, setSearched] = useState(false);
  const debRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = useCallback(async (term: string) => {
    const t = term.trim();
    if (!t) {
      setHits([]);
      setSearched(false);
      return;
    }
    try {
      const res = await searchWiki(t);
      setHits(Array.isArray(res?.data) ? res.data : []);
      setSearched(true);
    } catch {
      setHits([]);
      setSearched(true);
    }
  }, []);

  useEffect(() => {
    if (debRef.current) clearTimeout(debRef.current);
    debRef.current = setTimeout(() => runSearch(q), 250);
    return () => {
      if (debRef.current) clearTimeout(debRef.current);
    };
  }, [q, runSearch]);

  // #93 — the import modal renders OUTSIDE the status-gated branches so a post-import
  // reload() (which flips status→loading) does NOT unmount it mid-flow + destroy the
  // results the user needs to read. It's a fixed overlay, so it sits above any state.
  const importModal = showImport ? (
    <WikiImport onClose={closeImport} onImported={() => { importedDirty.current = true; }} />
  ) : null;

  if (status === "loading") {
    return (
      <>
        {importModal}
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="vault-loading">Đang tải vault…</div>
      </>
    );
  }
  if (status === "error") {
    return (
      <>
        {importModal}
        <div className="hint" style={{ padding: "24px 4px", color: "var(--red)" }} data-testid="vault-error">
          {errMsg || "Không tải được vault."}
          <button type="button" className="btn ghost" style={{ marginLeft: 12 }} onClick={reload}>Thử lại</button>
        </div>
      </>
    );
  }

  const s = overview?.stats;
  const totalNotes = s?.totalNotes ?? 0;

  // empty-vault state (cold-start): 0 notes → honest "vault rỗng" prompt, not fake tiles.
  if (!overview || totalNotes === 0) {
    return (
      <div data-testid="vault-screen">
        {importModal}
        <div className="vtitle">
          <h1>Vault · Tri thức</h1>
          <span className="sub">0 notes · vault còn trống</span>
          <span className="sp" style={{ flex: 1 }} />
          {/* #93 — import is a key way to BOOTSTRAP an empty vault (the "chưa upload được" pain). */}
          <button type="button" className="btn accent" onClick={() => setShowImport(true)} data-testid="vault-import-btn">
            <Icon name="i-plus" /> Import .md
          </button>
          <Link href="/wiki/inbox" className="btn" data-testid="vault-inbox-link">
            <Icon name="i-note" /> Inbox
          </Link>
        </div>
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="vault-empty">
          🌱 Vault rỗng — chưa có note nào. {warning ? <span className="mut">({warning})</span> : null} Bắt đầu bằng cách
          <b> Import .md</b> (nhập file có sẵn) hoặc capture một fleeting note (command bar <code>note …</code>) rồi triage ở Inbox.
        </div>
      </div>
    );
  }

  const pct = s && s.pctWithLink != null ? s.pctWithLink : null;
  const pctLabel = pct != null ? `${pct.toFixed(1)}%` : "—";
  const inbox = overview.inbox ?? [];
  const orphans = overview.orphans ?? [];
  const activity = overview.recentActivity ?? [];

  const inboxRow = (it: WikiInboxItem) => (
    <Link key={it.id} href="/wiki/inbox" className="wlist-row clickable" data-testid="vault-inbox-row">
      <span className="runi run" style={{ width: 16, height: 16, fontSize: 9 }}>{it.linkCount}</span>
      <div className="wlr-body">
        <div className="wlr-t">{it.title ?? <span className="faint">chưa có title</span>}</div>
        <div className="wlr-s mut">{it.rawContent.slice(0, 70)}…</div>
      </div>
      <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10, whiteSpace: "nowrap" }}>{it.captured}</span>
    </Link>
  );

  const orphanRow = (o: WikiOrphan) => (
    <Link key={o.id} href={`/wiki/${o.id}`} className="wlist-row clickable" data-testid="vault-orphan-row">
      <span className="worphan-deg">{o.degree}</span>
      <div className="wlr-body">
        <div className="wlr-t">{o.title ?? <span className="faint">#{o.id}</span>}</div>
      </div>
      <span className={`wstatus ${o.status}`}>{o.status}</span>
      <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{o.lastTouched}</span>
    </Link>
  );

  const actRow = (a: WikiActivity, i: number) => {
    const op = OP[a.op] ?? { lbl: a.op, color: "var(--tx-1)" };
    return (
      <div className="wact-row" key={`${a.ts}-${a.noteId}-${i}`} data-testid="vault-act-row">
        <span className="wact-ts num">{a.ts.slice(11, 19) || a.ts}</span>
        <span className="wact-op" style={{ color: op.color, background: `color-mix(in oklch,${op.color} 14%,transparent)` }}>{op.lbl}</span>
        <span className={`wact-actor ${a.actor}`}>{a.actor === "agent" ? "◇ AI" : "● bạn"}</span>
        <span className="wact-detail mut">
          {a.detail ?? `${a.noteTitle || `#${a.noteId}`}`}
        </span>
      </div>
    );
  };

  return (
    <div data-testid="vault-screen">
      <div className="vtitle">
        <h1>Vault · Tri thức</h1>
        <span className="sub">{totalNotes} notes · {s?.totalLinks ?? 0} links · cập nhật {s?.asOf}</span>
        <span className="sp" style={{ flex: 1 }} />
        <Link href="/wiki/graph" className="btn" data-testid="vault-graph-link">
          <Icon name="i-graph" /> Graph
        </Link>
        <button type="button" className="btn" onClick={() => setShowImport(true)} data-testid="vault-import-btn">
          <Icon name="i-plus" /> Import .md
        </button>
        <Link href="/wiki/inbox" className="btn accent" data-testid="vault-newnote-link">
          <Icon name="i-plus" /> Inbox
        </Link>
      </div>

      {importModal}

      {/* FTS search */}
      <div className="wsearch">
        <span className="pr"><Icon name="i-search" /></span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={`Tìm full-text trong ${totalNotes} notes… (FTS5 · gõ title hoặc nội dung)`}
          data-testid="vault-search-input"
          aria-label="Tìm trong vault"
        />
        <kbd>⌘F</kbd>
      </div>
      {q.trim() && (
        <div className="wsearch-res" data-testid="vault-search-results">
          {hits.length === 0 ? (
            <div className="wsearch-empty" data-testid="vault-search-empty">
              {searched ? `Không có kết quả cho “${q.trim()}”.` : "Đang tìm…"}
            </div>
          ) : (
            hits.map((h) => (
              <div
                key={h.id}
                className="wsearch-row"
                data-testid="vault-search-hit"
                onClick={() => router.push(`/wiki/${h.id}`)}
                onKeyDown={(e) => { if (e.key === "Enter") router.push(`/wiki/${h.id}`); }}
                role="button"
                tabIndex={0}
              >
                <span className={`wstatus ${h.status}`}>{h.status}</span>
                <div className="wlr-body">
                  <div className="wlr-t">{h.title ?? <span className="faint">#{h.id}</span>}</div>
                  <div className="wlr-s mut">{h.snippet}</div>
                </div>
                <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>#{h.id}</span>
              </div>
            ))
          )}
        </div>
      )}

      {/* stat tiles */}
      <div className="wtiles" style={{ marginTop: 12 }}>
        <StatTile label="Tổng notes" value={totalNotes} sub={`${s?.byStatus.evergreen ?? 0} evergreen`} cls="acc" />
        <StatTile label="Fleeting" value={s?.byStatus.fleeting ?? 0} sub="chờ refine" cls="amber" />
        <StatTile label="Developing" value={s?.byStatus.developing ?? 0} sub="đang chín" cls="blue" />
        <StatTile label="Tổng links" value={s?.totalLinks ?? 0} sub={`mật độ ${pctLabel}`} cls="pos" />
        <StatTile label="Orphan" value={s?.orphanCount ?? 0} sub="degree = 0" cls={(s?.orphanCount ?? 0) > 3 ? "neg" : "mut"} />
        <StatTile label="Ghost links" value={s?.ghostLinkCount ?? 0} sub="note chưa tạo" cls="amber" />
      </div>

      {/* density bar */}
      <div className="panel" style={{ padding: "13px 16px", marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 9 }}>
          <span className="kicker">Mật độ liên kết — chỉ số chất lượng vault</span>
          <span className="sp" style={{ flex: 1 }} />
          <span className="num pos" style={{ fontSize: 13, fontWeight: 700 }} data-testid="vault-density-pct">{pctLabel}</span>
          <span className="faint" style={{ fontSize: 11 }}>notes có ≥1 link</span>
        </div>
        <div className="bar" style={{ height: 8 }}>
          <i style={{ width: `${pct ?? 0}%`, background: "var(--green)", boxShadow: "0 0 8px -2px var(--green)" }} />
        </div>
        <div className="hint" style={{ marginTop: 8 }}>
          {s?.orphanCount ?? 0} orphan + {s?.ghostLinkCount ?? 0} ghost links cần xử lý — vault khỏe khi mật độ &gt; 90%.
        </div>
      </div>

      {/* inbox + orphan columns */}
      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "start", marginTop: 12 }}>
        <div className="panel">
          <div className="phead">
            <span className="kicker">Inbox cần refine</span>
            <span className="wstatus" style={{ color: "var(--amber)", background: "var(--amber-dim)" }}>{inbox.length} fleeting</span>
            <Link className="link" href="/wiki/inbox" style={{ marginLeft: "auto" }}>triage →</Link>
          </div>
          <div className="wlist" data-testid="vault-inbox-list">
            {inbox.length === 0
              ? <div className="wlist-empty" data-testid="vault-inbox-empty">Không có note fleeting — inbox sạch.</div>
              : inbox.slice(0, 4).map(inboxRow)}
          </div>
        </div>
        <div className="panel">
          <div className="phead">
            <span className="kicker">Orphan sweep</span>
            <span className="wstatus" style={{ color: "var(--red)", background: "var(--red-dim)" }}>{orphans.length} cô lập</span>
            <Link className="link" href="/wiki/graph" style={{ marginLeft: "auto" }}>xem graph →</Link>
          </div>
          <div className="wlist" data-testid="vault-orphan-list">
            {orphans.length === 0
              ? <div className="wlist-empty" data-testid="vault-orphan-empty">Không có orphan — mọi note đều có liên kết.</div>
              : orphans.slice(0, 4).map(orphanRow)}
          </div>
        </div>
      </div>

      {/* op-log + proposal mini */}
      <div className="grid" style={{ gridTemplateColumns: "1.5fr 1fr", alignItems: "start", marginTop: 12 }}>
        <div className="panel">
          <div className="phead">
            <span className="kicker">Hoạt động gần đây · op-log</span>
            <span className="hint" style={{ marginLeft: "auto" }}>single-writer</span>
          </div>
          <div className="wact-list" data-testid="vault-act-list">
            {activity.length === 0
              ? <div className="wlist-empty" data-testid="vault-act-empty">Chưa có hoạt động.</div>
              : activity.map(actRow)}
          </div>
        </div>
        <div className="panel wproposal-mini">
          <div className="phead">
            <span className="kicker">Proposal queue</span>
            <span className="wstatus" style={{ color: "var(--accent)", background: "var(--accent-dim)" }} data-testid="vault-proposal-count">
              {overview.proposalCount} chờ duyệt
            </span>
          </div>
          {/* M1: proposalCount is ALWAYS 0 (no embedded AI). Honest empty state — NOT a fabricated queue. */}
          <div className="wprop-empty" data-testid="vault-proposal-empty">
            Chưa có đề xuất AI. Link / MOC / merge candidate sẽ đến qua Claude Code (MCP) ở giai đoạn sau — mỗi cái chờ
            bạn duyệt, <b>không bao giờ tự ghi</b> vào note evergreen.
          </div>
        </div>
      </div>
    </div>
  );
}
