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
import { searchWiki, ApiError } from "@/lib/api";
import { Icon } from "@/lib/icons";
import { WikiImport } from "@/components/WikiImport";
import { WikiTrash } from "@/components/WikiTrash";
import { StatTile } from "./_StatTile";
import { InboxRow, ActivityRow } from "./_rows";
import type {
  WikiOrphan,
  WikiSearchHit,
} from "@/lib/types";

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

  /* ---- #94 trash modal + "moved to trash" toast (from ?trashed=<id>) ---- */
  const [showTrash, setShowTrash] = useState(false);
  const trashedDirty = useRef(false);
  const closeTrash = useCallback(() => {
    setShowTrash(false);
    if (trashedDirty.current) { trashedDirty.current = false; reload(); }
  }, [reload]);
  // the note-detail soft-delete navigates to /wiki?trashed=<id> → show a recover toast.
  const trashedId = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("trashed") : null;
  const [toastDismissed, setToastDismissed] = useState(false);

  /* ---- #94 bulk-select (orphan list) → bulk soft-delete ---- */
  const [bulkMode, setBulkMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkConfirm, setBulkConfirm] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkResult, setBulkResult] = useState<{ deletedCount: number; errors: { id: number; msg: string }[] } | null>(null);
  const toggleSelect = useCallback((id: number) => {
    setSelectedIds((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }, []);
  const exitBulk = useCallback(() => { setBulkMode(false); setSelectedIds(new Set()); setBulkConfirm(false); setBulkResult(null); }, []);
  async function onBulkDelete() {
    if (selectedIds.size === 0) return;
    setBulkBusy(true); setBulkResult(null);
    try {
      const { bulkDeleteWikiNotes } = await import("@/lib/api");
      const res = await bulkDeleteWikiNotes([...selectedIds]);
      const errors = res.data.results.filter((r) => !r.ok).map((r) => ({ id: r.id, msg: r.error?.message ?? "lỗi" }));
      setBulkResult({ deletedCount: res.data.deletedCount, errors });
      setBulkConfirm(false);
      setSelectedIds(new Set());
      reload(); // refresh the tree (the soft-deleted notes leave the orphan list)
    } catch (e) {
      setBulkResult({ deletedCount: 0, errors: [{ id: -1, msg: e instanceof ApiError ? e.message : (e as Error).message }] });
    } finally {
      setBulkBusy(false);
    }
  }

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

  // #94 — trash modal (same hoist rationale as the import modal: survive a reload).
  const trashModal = showTrash ? (
    <WikiTrash onClose={closeTrash} onRestored={() => { trashedDirty.current = true; }} />
  ) : null;

  // #94 — "moved to trash · restore" toast after a soft-delete (the undo affordance).
  const trashedToast = trashedId && !toastDismissed ? (
    <div className="panel" style={{ padding: "10px 14px", borderColor: "var(--accent)", display: "flex", alignItems: "center", gap: 10 }} data-testid="trashed-toast">
      <span className="hint">🗑 Đã chuyển note vào thùng rác.</span>
      <button type="button" className="btn sm acc" onClick={() => { setShowTrash(true); setToastDismissed(true); }} data-testid="toast-open-trash">↩ Khôi phục</button>
      <button type="button" className="btn sm ghost" onClick={() => setToastDismissed(true)} data-testid="toast-dismiss">Bỏ qua</button>
    </div>
  ) : null;

  const overlays = <>{importModal}{trashModal}</>;

  if (status === "loading") {
    return (
      <>
        {overlays}
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="vault-loading">Đang tải vault…</div>
      </>
    );
  }
  if (status === "error") {
    return (
      <>
        {overlays}
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
        {overlays}
        <div className="vtitle">
          <h1>Vault · Tri thức</h1>
          <span className="sub">0 notes · vault còn trống</span>
          <span className="sp" style={{ flex: 1 }} />
          {/* #93 — import is a key way to BOOTSTRAP an empty vault (the "chưa upload được" pain). */}
          <button type="button" className="btn accent" onClick={() => setShowImport(true)} data-testid="vault-import-btn">
            <Icon name="i-plus" /> Import .md
          </button>
          {/* #94 — trash access even when the vault is empty (e.g. soft-deleted the last note). */}
          <button type="button" className="btn" onClick={() => setShowTrash(true)} data-testid="vault-trash-btn">
            🗑 Thùng rác
          </button>
          <Link href="/wiki/inbox" className="btn" data-testid="vault-inbox-link">
            <Icon name="i-note" /> Inbox
          </Link>
        </div>
        {trashedToast}
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

  const orphanRow = (o: WikiOrphan) =>
    bulkMode ? (
      // #94 bulk-mode: a checkbox row (no navigation) to multi-select for soft-delete.
      <label key={o.id} className="wlist-row" style={{ cursor: "pointer" }} data-testid={`vault-orphan-row-bulk-${o.id}`}>
        <input
          type="checkbox"
          checked={selectedIds.has(o.id)}
          onChange={() => toggleSelect(o.id)}
          data-testid={`bulk-check-${o.id}`}
          style={{ marginRight: 6 }}
        />
        <span className="worphan-deg">{o.degree}</span>
        <div className="wlr-body"><div className="wlr-t">{o.title ?? <span className="faint">#{o.id}</span>}</div></div>
        <span className={`wstatus ${o.status}`}>{o.status}</span>
        <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{o.lastTouched}</span>
      </label>
    ) : (
      <Link key={o.id} href={`/wiki/${o.id}`} className="wlist-row clickable" data-testid="vault-orphan-row">
        <span className="worphan-deg">{o.degree}</span>
        <div className="wlr-body">
          <div className="wlr-t">{o.title ?? <span className="faint">#{o.id}</span>}</div>
        </div>
        <span className={`wstatus ${o.status}`}>{o.status}</span>
        <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10 }}>{o.lastTouched}</span>
      </Link>
    );

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
        <button type="button" className="btn" onClick={() => setShowTrash(true)} data-testid="vault-trash-btn">
          🗑 Thùng rác
        </button>
        <Link href="/wiki/inbox" className="btn accent" data-testid="vault-newnote-link">
          <Icon name="i-plus" /> Inbox
        </Link>
      </div>

      {overlays}
      {trashedToast}

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
              : inbox.slice(0, 4).map((it) => <InboxRow key={it.id} it={it} />)}
          </div>
        </div>
        <div className="panel">
          <div className="phead">
            <span className="kicker">Orphan sweep</span>
            <span className="wstatus" style={{ color: "var(--red)", background: "var(--red-dim)" }}>{orphans.length} cô lập</span>
            {/* #94 bulk-select toggle */}
            {orphans.length > 0 && (
              bulkMode ? (
                <button type="button" className="btn sm ghost" style={{ marginLeft: "auto" }} onClick={exitBulk} data-testid="bulk-exit">Xong</button>
              ) : (
                <button type="button" className="btn sm" style={{ marginLeft: "auto" }} onClick={() => setBulkMode(true)} data-testid="bulk-mode-btn">Chọn nhiều</button>
              )
            )}
          </div>

          {/* #94 bulk action bar — soft-delete the selected, IN-PAGE confirm (no JS dialog) */}
          {bulkMode && (
            <div className="wbulk-bar" data-testid="bulk-bar">
              <span className="hint" data-testid="bulk-count">{selectedIds.size} đã chọn</span>
              {bulkConfirm ? (
                <>
                  <span className="hint neg">Chuyển {selectedIds.size} note vào thùng rác?</span>
                  <button type="button" className="btn sm neg" disabled={bulkBusy} onClick={onBulkDelete} data-testid="bulk-confirm-yes">
                    {bulkBusy ? "Đang xoá…" : "Xác nhận"}
                  </button>
                  <button type="button" className="btn sm" onClick={() => setBulkConfirm(false)} data-testid="bulk-confirm-no">Huỷ</button>
                </>
              ) : (
                <button
                  type="button"
                  className="btn sm"
                  style={{ color: "var(--red)" }}
                  disabled={selectedIds.size === 0}
                  onClick={() => { setBulkResult(null); setBulkConfirm(true); }}
                  data-testid="bulk-delete-btn"
                >
                  🗑 Xoá đã chọn
                </button>
              )}
            </div>
          )}
          {/* fail-soft bulk result */}
          {bulkResult && (
            <div className="hint" style={{ padding: "6px 10px" }} data-testid="bulk-result">
              <span className="pos">{bulkResult.deletedCount} đã chuyển vào thùng rác</span>
              {bulkResult.errors.length > 0 && (
                <span className="neg" data-testid="bulk-errors"> · {bulkResult.errors.length} lỗi: {bulkResult.errors.map((e) => e.msg).join("; ")}</span>
              )}
            </div>
          )}

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
              : activity.map((a, i) => <ActivityRow key={`${a.ts}-${a.noteId}-${i}`} a={a} />)}
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
