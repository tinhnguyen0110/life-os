"use client";
/* ============================================================
   P1 — Nhật ký AI / AI Audit-Log · /wiki/proposals.

   WIKI-AIFIRST (user CHỐT "bỏ chế độ duyệt, AI-first ghi thẳng"): backend is
   AUTONOMOUS (wikiAgentAutonomous default ON) — AI writes land DIRECTLY in the
   Vault and keep an `accepted` proposal record with decidedBy="agent:auto".
   So this screen is no longer a duyệt/gate — it's an AUDIT-LOG of what the AI
   wrote. Default filter = `accepted` (the working set the human audits).

   - A pending row is now a rare legacy case; accept/reject stay available per-row
     but are NOT the headline (no prominent batch-duyệt CTA).
   - REVERSE per accepted row:
       · note_create / moc  → "Lùi (xoá note)" = SOFT-delete appliedNoteId
         (recoverable). The only clean one-step undo today.
       · note_edit / link_* / merge → NO version-undo exists → deep-link
         "→ mở note để refine" + an honest hint (manual revert).
   FAIL-CLOSED: a reverse/decide that 4xx's surfaces ON the row; the list is NOT
   optimistically mutated.

   States: loading · error · empty (0 in this filter — honest) · ready.
   ============================================================ */
import { useCallback, useState } from "react";
import Link from "next/link";
import { useWikiProposals } from "@/lib/useWiki";
import type { ProposalFilter } from "@/lib/useWiki";
import { Icon, type IconKey } from "@/lib/icons";
import { WikiMarkdown } from "@/components/shared";
import { ApiError, deleteWikiNote } from "@/lib/api";
import type { WikiProposal, WikiProposalKind } from "@/lib/types";

/** kinds whose accepted write is one-step reversible via SOFT-deleting the
 *  applied note (recoverable). Other kinds (edit/link/merge) have no version-undo. */
const REVERSIBLE_KINDS: ReadonlySet<string> = new Set(["note_create", "moc"]);

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

// WIKI-NO-APPROVAL #183: the "chờ duyệt" (pending) filter is GONE — AI-first means no manual
// approval gate, so this is a pure AUDIT log. A rare legacy pending row still shows under "tất cả".
const FILTERS: { value: ProposalFilter; label: string }[] = [
  { value: "accepted", label: "AI đã ghi" },
  { value: "rejected", label: "đã reject" },
  { value: "all", label: "tất cả" },
];

/** A LONG `content` field needs the collapse/markdown treatment: >120 chars OR
 *  contains a newline. A short 1-line content renders inline (no toggle). */
function isLongContent(v: unknown): v is string {
  return typeof v === "string" && (v.length > 120 || v.includes("\n"));
}

/** WIKI-AIFIRST T4 — a note_create/moc payload's long `content` rendered collapsed
 *  by default (3-line raw clamp + "xem thêm"), expandable to full WikiMarkdown.
 *  Per-card local state. `resolve` is OMITTED (the audit payload has no resolved
 *  outbound edges → `[[Title]]` stays a ghost honestly; `[[id]]` still resolves). */
function ContentBlock({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="wprop-content-block" data-testid="prop-content-block">
      {expanded ? (
        <div className="wprop-content-md" data-testid="prop-content-expanded">
          <WikiMarkdown content={content} testId="prop-content-md" />
        </div>
      ) : (
        <div className="wprop-preview" data-testid="prop-content-preview">{content}</div>
      )}
      <button
        type="button"
        className="wprop-toggle"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        data-testid="prop-content-toggle"
      >
        {expanded ? "▾ thu gọn" : "▸ xem thêm"}
      </button>
    </div>
  );
}

/** Render the kind-specific payload generically (no kind invented — we display
 *  whatever fields the frozen payload dict carries). A LONG `content` field is
 *  pulled out into a collapsible markdown block; the rest stay inline as-is. */
function PayloadBody({ p }: { p: WikiProposal }) {
  const pl = p.payload ?? {};
  const longContent = isLongContent(pl.content) ? (pl.content as string) : null;
  // inline fields = everything EXCEPT the long content we render separately below.
  const inlineEntries = Object.entries(pl).filter(([k]) => !(longContent != null && k === "content"));
  return (
    <>
      <div className="wprop-link" data-testid="prop-body">
        <span className="wtrust cand" style={{ flexShrink: 0 }}>{p.kind}</span>
        {p.targetId != null && (
          <Link className="wlink" href={`/wiki/${p.targetId}`} data-testid="prop-target">#{p.targetId}</Link>
        )}
        {inlineEntries.length > 0 && (
          <span className="wprop-content mut" style={{ flex: 1 }} data-testid="prop-payload">
            {inlineEntries.map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`).join(" · ")}
          </span>
        )}
      </div>
      {longContent != null && <ContentBlock content={longContent} />}
    </>
  );
}

function ProposalCard({
  p,
  onAccept,
  onReject,
  onReversed,
  busy,
}: {
  p: WikiProposal;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
  /** called after a successful reverse (soft-delete) so the list refetches. */
  onReversed: () => void;
  busy: boolean;
}) {
  const km = kindMeta(p.kind);
  const [err, setErr] = useState("");
  const [reverseBusy, setReverseBusy] = useState(false);
  // after a successful reverse we keep the row but show the "đã lùi" state until the
  // list refetch lands (the soft-deleted note's proposal stays accepted; its applied
  // note is now in trash). Holds the trashed note id for the "khôi phục" deep-link.
  const [reversedNoteId, setReversedNoteId] = useState<number | null>(null);
  const isPending = p.status === "pending";
  const isAccepted = p.status === "accepted";
  // W4d: auto-applied write (autonomy ON) → decidedBy "agent:auto".
  const isAuto = p.decidedBy === "agent:auto";
  // A note_create/moc accepted write with a live applied note → one-step reversible.
  const canReverse = isAccepted && REVERSIBLE_KINDS.has(p.kind) && p.appliedNoteId != null;

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
  const doReverse = async () => {
    if (p.appliedNoteId == null) return;
    setErr("");
    setReverseBusy(true);
    try {
      // SOFT-delete the applied note (recoverable). FAIL-CLOSED: a 4xx surfaces on the
      // row; we do NOT optimistically mark reversed unless the delete actually succeeded.
      await deleteWikiNote(p.appliedNoteId);
      setReversedNoteId(p.appliedNoteId);
      onReversed(); // refetch the list (the note is now in trash)
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setReverseBusy(false);
    }
  };

  return (
    <div className={`wprop-card ${busy ? "deciding" : ""}`} data-testid="prop-card" data-prop-id={p.id} data-status={p.status}>
      <div className="wprop-head">
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
            {p.status === "accepted" ? "✓ AI đã ghi" : "✕ rejected"}
          </span>
          {/* W4d: an AUTO-write (decidedBy "agent:auto") gets a distinct amber badge so a
              human auditing the accepted filter can tell autonomous writes from their own. */}
          {isAuto ? (
            <span className="wtrust cand" data-testid="prop-auto-badge" title="ghi tự động bởi agent (autonomous ON)">◇ agent:auto</span>
          ) : (
            p.decidedBy && <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10.5 }}>bởi {p.decidedBy}</span>
          )}
          <span className="sp" style={{ flex: 1 }} />

          {/* applied-note deep-link (always, when there's an applied note) */}
          {p.appliedNoteId != null && (
            <Link className="link" href={`/wiki/${p.appliedNoteId}`} data-testid="prop-applied-link">→ note #{p.appliedNoteId}</Link>
          )}

          {/* REVERSE — note_create/moc: one-step SOFT-delete (recoverable). */}
          {reversedNoteId != null ? (
            <span className="hint" data-testid="prop-reversed">
              đã lùi · note #{reversedNoteId} vào thùng rác ·{" "}
              <Link className="link" href={`/wiki?trashed=${reversedNoteId}`} data-testid="prop-reversed-restore">khôi phục</Link>
            </span>
          ) : canReverse ? (
            <button
              type="button"
              className="btn sm"
              style={{ color: "var(--red)" }}
              onClick={doReverse}
              disabled={reverseBusy || busy}
              data-testid="prop-reverse"
              title="xoá note đã ghi (soft-delete, khôi phục được trong thùng rác)"
            >
              <Icon name="i-x" /> {reverseBusy ? "Đang lùi…" : "Lùi (xoá note)"}
            </button>
          ) : isAccepted && p.appliedNoteId != null ? (
            /* edit/link/merge: NO version-undo → manual-refine deep-link + honest hint. */
            <span className="hint" data-testid="prop-reverse-manual">
              <Link className="link" href={`/wiki/${p.appliedNoteId}`}>→ mở note #{p.appliedNoteId} để refine</Link>
              <span className="faint"> (sửa nội dung là cách lùi — chưa có version-undo)</span>
            </span>
          ) : null}
        </div>
      )}

      {err && <div className="wprop-err" data-testid="prop-error">⚠ {err}</div>}
    </div>
  );
}

export default function WikiProposalsPage() {
  // WIKI-AIFIRST: default to `accepted` — the working set the human audits (autonomous
  // ON means ~all writes are accepted-by-agent:auto). Pending is now a rare legacy case.
  // WIKI-NO-APPROVAL #183: pure audit log — no batch-accept gate. Per-row accept/reject stay
  // (fail-closed) for a rare legacy pending row, but there's no headline batch CTA + no selection.
  const { proposals, counts, filter, setFilter, status, errMsg, reload, accept, reject } = useWikiProposals("accepted");

  const [busyId, setBusyId] = useState<number | null>(null);

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
        <h1>Nhật ký AI</h1>
        <span className="sub" data-testid="prop-subcount">{counts.accepted ?? 0} lần AI ghi · audit</span>
        <span className="sp" style={{ flex: 1 }} />
        <div className="seg" role="group" aria-label="filter">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={filter === f.value ? "on" : ""}
              onClick={() => setFilter(f.value)}
              data-testid={`prop-filter-${f.value}`}
            >
              {f.label}
              {f.value !== "all" && counts[f.value] != null ? ` ${counts[f.value]}` : ""}
            </button>
          ))}
        </div>
      </div>

      {/* AI-first audit banner — autonomous ON: writes auto-apply, this is the log. */}
      <div className="panel wprop-banner" data-testid="prop-banner">
        <span className="dot acc pulse" />
        <div style={{ flex: 1, fontSize: 12.5, lineHeight: 1.5 }}>
          <b style={{ fontFamily: "var(--mono)" }}>AI ghi thẳng vào Vault (autonomous ON).</b>{" "}
          <span className="mut">
            Đây là nhật ký mọi lần AI ghi — xem lại + lùi nếu cần. note_create/MOC lùi được (xoá note, khôi phục trong
            thùng rác); edit/link/merge lùi thủ công (mở note để refine — chưa có version-undo).
          </span>
        </div>
        <span className="tagchip" data-testid="prop-count-total">{total} tổng</span>
      </div>

      {/* WIKI-NO-APPROVAL #183: the batch-duyệt bar was removed — this is an audit log, not an
          approval queue. No batch-accept CTA, no selection. */}

      {/* list / honest empty — per-filter so the accepted (default) empty reads as an
          AUDIT-LOG empty, NOT a queue empty (team-lead Chrome-gate: empty-state honest). */}
      {proposals.length === 0 ? (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="prop-empty">
          {filter === "accepted"
            ? "📭 Chưa có ghi nhớ AI nào — khi Claude Code (MCP) ghi vào Vault, mỗi lần ghi sẽ hiện ở đây."
            : filter === "all"
              ? "📭 Chưa có ghi nhớ AI nào."
              : `Không có proposal nào ở trạng thái “${filter}”.`}
        </div>
      ) : (
        <div className="wprop-list" style={{ marginTop: 12 }} data-testid="prop-list">
          {proposals.map((p) => (
            <ProposalCard
              key={p.id}
              p={p}
              onAccept={onAccept}
              onReject={onReject}
              onReversed={reload}
              busy={busyId === p.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
