"use client";
/* ============================================================
   P1 — Proposal Queue · /wiki/proposals. Ported from mock screens-wiki.js
   SCREENS.proposals + wiki.css (P1 block), built to the FROZEN W4a contract
   (NOT the mock's aspirational kinds): GET /wiki/proposals?status= →
   {proposals[], counts}, POST .../{id}/accept|reject {decidedBy?}, POST
   .../accept-batch {ids,decidedBy?}.

   TRUST BOUNDARY (the whole point of this screen): every AI-proposed mutation
   lands here as `pending` first — a human accepts/rejects. AI NEVER edits an
   evergreen note's body in place. Accept → apply via changes-queue/op-log → the
   note becomes verified. Reject is remembered.

   FAIL-CLOSED: an accept that can't apply (target note missing, malformed payload)
   returns 4xx {detail} → surfaced ON the card; the queue is NOT optimistically
   mutated, so a failed apply leaves the proposal in place to retry/reject.

   States: loading · error · empty (0 in this filter — honest) · ready.
   ============================================================ */
import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useWikiProposals } from "@/lib/useWiki";
import type { ProposalFilter } from "@/lib/useWiki";
import { Icon, type IconKey } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { WikiProposal, WikiProposalKind } from "@/lib/types";

/** per-kind display: label + accent color + icon. Covers ALL 6 frozen kinds
 *  (note_create/note_edit/link_add/link_remove/merge/moc). agent_note from the
 *  mock isn't a frozen kind; a future kind falls back to a neutral chip. */
const KIND_META: Record<WikiProposalKind, { lbl: string; color: string; ic: IconKey }> = {
  note_create: { lbl: "note create", color: "var(--green)", ic: "i-plus" },
  note_edit: { lbl: "note edit", color: "var(--blue)", ic: "i-doc" },
  link_add: { lbl: "link add", color: "var(--accent)", ic: "i-link" },
  link_remove: { lbl: "link remove", color: "var(--amber)", ic: "i-link" },
  merge: { lbl: "merge", color: "var(--violet)", ic: "i-merge" },
  moc: { lbl: "MOC", color: "var(--amber)", ic: "i-moc" },
};
function kindMeta(k: string) {
  return KIND_META[k as WikiProposalKind] ?? { lbl: k, color: "var(--tx-1)", ic: "i-doc" as IconKey };
}

const FILTERS: { value: ProposalFilter; label: string }[] = [
  { value: "pending", label: "chờ duyệt" },
  { value: "accepted", label: "đã accept" },
  { value: "rejected", label: "đã reject" },
  { value: "all", label: "tất cả" },
];

/** Render the kind-specific payload generically (no kind invented — we display
 *  whatever fields the frozen payload dict carries). */
function PayloadBody({ p }: { p: WikiProposal }) {
  const pl = p.payload ?? {};
  const entries = Object.entries(pl);
  return (
    <div className="wprop-link" data-testid="prop-body">
      <span className="wtrust cand" style={{ flexShrink: 0 }}>{p.kind}</span>
      {p.targetId != null && (
        <Link className="wlink" href={`/wiki/${p.targetId}`} data-testid="prop-target">#{p.targetId}</Link>
      )}
      {entries.length > 0 && (
        <span className="wprop-content mut" style={{ flex: 1 }} data-testid="prop-payload">
          {entries.map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}
        </span>
      )}
    </div>
  );
}

function ProposalCard({
  p,
  selected,
  onToggleSelect,
  onAccept,
  onReject,
  busy,
}: {
  p: WikiProposal;
  selected: boolean;
  onToggleSelect: (id: number) => void;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
  busy: boolean;
}) {
  const km = kindMeta(p.kind);
  const [err, setErr] = useState("");
  const isPending = p.status === "pending";

  const doAccept = async () => {
    setErr("");
    try {
      await onAccept(p.id);
    } catch (e) {
      // FAIL-CLOSED: surface the 4xx detail right here; card stays.
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
    }
  };
  const doReject = async () => {
    setErr("");
    try {
      await onReject(p.id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
    }
  };

  return (
    <div className={`wprop-card ${busy ? "deciding" : ""}`} data-testid="prop-card" data-prop-id={p.id} data-status={p.status}>
      <div className="wprop-head">
        {isPending && (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggleSelect(p.id)}
            aria-label={`Chọn proposal #${p.id}`}
            data-testid="prop-select"
          />
        )}
        <span className="wprop-kind-badge" style={{ color: km.color, background: `color-mix(in oklch,${km.color} 14%,transparent)` }}>
          <Icon name={km.ic} /> {km.lbl}
        </span>
        <span className="wprop-actor" data-testid="prop-actor">{p.actor.replace("agent:", "◇ ")}</span>
        <span className="sp" style={{ flex: 1 }} />
        <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>
          {p.created}{p.correlationId ? ` · ${p.correlationId}` : ""}
        </span>
      </div>

      <PayloadBody p={p} />

      {p.rationale ? (
        <div className="wprop-why" data-testid="prop-rationale"><span className="acc">why:</span> {p.rationale}</div>
      ) : (
        <div className="wprop-why mut" data-testid="prop-rationale-empty"><span className="acc">why:</span> <span className="faint">(không có giải thích)</span></div>
      )}

      {/* decided cards show the outcome + applied note deep-link; pending show actions */}
      {isPending ? (
        <div className="wprop-acts">
          <button type="button" className="btn sm accent" onClick={doAccept} disabled={busy} data-testid="prop-accept">
            <Icon name="i-check" /> Accept
          </button>
          <button type="button" className="btn sm" onClick={doReject} disabled={busy} data-testid="prop-reject">
            <Icon name="i-x" /> Reject
          </button>
          <span className="sp" style={{ flex: 1 }} />
          <span className="hint">accept → apply qua op-log → verified</span>
        </div>
      ) : (
        <div className="wprop-acts" data-testid="prop-decided">
          <span className={`wstatus ${p.status === "accepted" ? "evergreen" : "fleeting"}`} data-testid="prop-decided-status">
            {p.status === "accepted" ? "✓ accepted" : "✕ rejected"}
          </span>
          {p.decidedBy && <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>bởi {p.decidedBy}</span>}
          <span className="sp" style={{ flex: 1 }} />
          {p.appliedNoteId != null && (
            <Link className="link" href={`/wiki/${p.appliedNoteId}`} data-testid="prop-applied-link">→ note #{p.appliedNoteId}</Link>
          )}
        </div>
      )}

      {err && <div className="wprop-err" data-testid="prop-error">⚠ {err}</div>}
    </div>
  );
}

export default function WikiProposalsPage() {
  const { proposals, counts, filter, setFilter, status, errMsg, reload, accept, reject, batchAccept } = useWikiProposals("pending");
  const router = useRouter();

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busyId, setBusyId] = useState<number | null>(null);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchErr, setBatchErr] = useState("");
  const [batchNotice, setBatchNotice] = useState("");

  const toggleSelect = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  // selection only meaningful for pending cards in view; prune on filter change.
  const pendingIds = useMemo(() => proposals.filter((p) => p.status === "pending").map((p) => p.id), [proposals]);
  const selectedInView = useMemo(() => [...selected].filter((id) => pendingIds.includes(id)), [selected, pendingIds]);

  const onAccept = useCallback(async (id: number) => {
    setBusyId(id);
    try {
      await accept(id); // throws → ProposalCard surfaces it (fail-closed)
    } finally {
      setBusyId(null);
    }
  }, [accept]);

  const onReject = useCallback(async (id: number) => {
    setBusyId(id);
    try {
      await reject(id);
    } finally {
      setBusyId(null);
    }
  }, [reject]);

  async function onBatchAccept() {
    if (!selectedInView.length) return;
    setBatchErr("");
    setBatchNotice("");
    setBatchBusy(true);
    try {
      const res = await batchAccept(selectedInView);
      setSelected(new Set());
      // A batch can PARTIALLY succeed (200 + failed>0). Surface the outcome honestly:
      // failures are NOT a thrown error, so without this they'd silently vanish.
      if (res) {
        if (res.failed > 0) {
          const failedIds = res.results.filter((r) => !r.ok).map((r) => `#${r.id} (${r.error ?? "lỗi"})`).join(", ");
          setBatchErr(`Accept ${res.accepted}/${res.accepted + res.failed} — ${res.failed} lỗi: ${failedIds}`);
        } else {
          setBatchNotice(`✓ Đã accept ${res.accepted} proposal.`);
        }
      }
    } catch (e) {
      setBatchErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBatchBusy(false);
    }
  }

  if (status === "loading") {
    return <div className="hint" style={{ padding: "24px 4px" }} data-testid="prop-loading">Đang tải proposal queue…</div>;
  }
  if (status === "error") {
    return (
      <div className="hint" style={{ padding: "24px 4px", color: "var(--red)" }} data-testid="prop-screen-error">
        {errMsg || "Không tải được proposal queue."}
        <button type="button" className="btn ghost" style={{ marginLeft: 12 }} onClick={reload}>Thử lại</button>
      </div>
    );
  }

  const total = (counts.pending ?? 0) + (counts.accepted ?? 0) + (counts.rejected ?? 0);

  return (
    <div data-testid="prop-screen">
      <div className="vtitle">
        <h1>Proposal Queue</h1>
        <span className="sub">{counts.pending ?? 0} mutation AI chờ duyệt · trust boundary</span>
        <span className="sp" style={{ flex: 1 }} />
        <div className="seg" role="group" aria-label="filter">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={filter === f.value ? "on" : ""}
              onClick={() => { setFilter(f.value); setSelected(new Set()); }}
              data-testid={`prop-filter-${f.value}`}
            >
              {f.label}
              {f.value !== "all" && counts[f.value] != null ? ` ${counts[f.value]}` : ""}
            </button>
          ))}
        </div>
      </div>

      {/* trust-boundary banner */}
      <div className="panel wprop-banner">
        <span className="dot acc pulse" />
        <div style={{ flex: 1, fontSize: 12.5, lineHeight: 1.5 }}>
          <b style={{ fontFamily: "var(--mono)" }}>AI write-back luôn vào đây trước.</b>{" "}
          <span className="mut">
            Không bao giờ sửa thân note evergreen tại chỗ. Accept → apply qua changes-queue. Reject → nhớ, không gợi lại.
          </span>
        </div>
        <span className="tagchip" data-testid="prop-count-total">{total} tổng</span>
      </div>

      {/* batch action bar (pending filter, ≥1 selected) */}
      {filter === "pending" && pendingIds.length > 0 && (
        <div className="panel wprop-banner" data-testid="prop-batch-bar" style={{ marginTop: 12 }}>
          <span className="mut" style={{ fontSize: 12 }}>{selectedInView.length} đã chọn</span>
          <span className="sp" style={{ flex: 1 }} />
          {batchNotice && <span className="hint" style={{ color: "var(--green)" }} data-testid="prop-batch-notice">{batchNotice}</span>}
          {batchErr && <span className="wprop-err" style={{ margin: 0 }} data-testid="prop-batch-error">⚠ {batchErr}</span>}
          <button
            type="button"
            className="btn sm accent"
            onClick={onBatchAccept}
            disabled={batchBusy || selectedInView.length === 0}
            data-testid="prop-batch-accept"
          >
            <Icon name="i-check" /> {batchBusy ? "Đang accept…" : `Accept ${selectedInView.length} đã chọn`}
          </button>
        </div>
      )}

      {/* list / honest empty */}
      {proposals.length === 0 ? (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="prop-empty">
          {filter === "pending"
            ? "✅ Không có proposal nào chờ duyệt — queue sạch. AI candidate (link/MOC/merge/edit) sẽ xuất hiện ở đây khi Claude Code (MCP) đề xuất."
            : `Không có proposal nào ở trạng thái “${filter}”.`}
        </div>
      ) : (
        <div className="wprop-list" style={{ marginTop: 12 }} data-testid="prop-list">
          {proposals.map((p) => (
            <ProposalCard
              key={p.id}
              p={p}
              selected={selected.has(p.id)}
              onToggleSelect={toggleSelect}
              onAccept={onAccept}
              onReject={onReject}
              busy={busyId === p.id || batchBusy}
            />
          ))}
        </div>
      )}
    </div>
  );
}
