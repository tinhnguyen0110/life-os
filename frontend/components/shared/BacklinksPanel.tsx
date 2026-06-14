"use client";
/* ============================================================
   BacklinksPanel — a note's connections (W2). Ported from mock screens-wiki.js
   outRow/linkedRow/unlinkedRow + wiki.css (.woutlink/.wbl-row/.wbl-sec-lbl).
   Two panels in the mock (Outbound + Backlinks); this component renders BOTH
   sections from one WikiBacklinks payload so W2 composes it once.

   - outbound: resolved → clickable <Link>; ghost → dashed row + "+ tạo note".
   - linked mentions: clickable <Link> + snippet (snippet may carry <b> highlight
     HTML from the backend — rendered via dangerouslySetInnerHTML, server-owned).
   - unlinked mentions: title + snippet + "link nó" action.
   Action callbacks are optional (W2 wires create/link later; M1 may pass none →
   the buttons are inert-but-present, honest-mirror).
   ============================================================ */
import Link from "next/link";
import { Icon } from "@/lib/icons";
import type { WikiBacklinks, WikiOutboundLink } from "@/lib/types";

interface BacklinksPanelProps {
  backlinks: WikiBacklinks;
  /** ghost outbound → "+ tạo note" (create a note with this title). Optional. */
  onCreateGhost?: (title: string) => void;
  /** unlinked mention → "link nó" (link this note). Optional. */
  onLinkUnlinked?: (id: number) => void;
}

function OutboundRow({ o, onCreateGhost }: { o: WikiOutboundLink; onCreateGhost?: (t: string) => void }) {
  if (o.isResolved) {
    return (
      <Link href={`/wiki/${o.id}`} className="woutlink clickable" data-testid="outbound-resolved">
        <Icon name="i-link" />
        <span>{o.title}</span>
        <span className="faint">#{o.id}</span>
      </Link>
    );
  }
  return (
    <div className="woutlink ghost" data-testid="outbound-ghost">
      <Icon name="i-link" />
      <span>{o.ghost}</span>
      <button
        type="button"
        className="btn sm ghost"
        style={{ marginLeft: "auto", padding: "2px 8px" }}
        onClick={() => onCreateGhost?.(o.ghost)}
        data-testid="ghost-create"
      >
        + tạo note
      </button>
    </div>
  );
}

export function BacklinksPanel({ backlinks, onCreateGhost, onLinkUnlinked }: BacklinksPanelProps) {
  const { linked, unlinked, outbound } = backlinks;
  return (
    <>
      {/* Outbound */}
      <div className="panel" data-testid="outbound-panel">
        <div className="phead">
          <span className="kicker">Outbound links</span>
          <span className="hint" style={{ marginLeft: "auto" }}>
            {outbound.length} liên kết ra
          </span>
        </div>
        <div className="woutlist">
          {outbound.length === 0 ? (
            <div className="wbl-empty" data-testid="outbound-empty">
              chưa có liên kết ra
            </div>
          ) : (
            outbound.map((o, i) => <OutboundRow key={i} o={o} onCreateGhost={onCreateGhost} />)
          )}
        </div>
      </div>

      {/* Backlinks (linked + unlinked) */}
      <div className="panel" data-testid="backlinks-panel">
        <div className="phead">
          <span className="kicker">Backlinks</span>
          <span className="hint" style={{ marginLeft: "auto" }}>
            {linked.length} linked · {unlinked.length} unlinked
          </span>
        </div>

        <div className="wbl-sec-lbl">Linked mentions</div>
        <div className="wbl-list">
          {linked.length === 0 ? (
            <div className="wbl-empty" data-testid="linked-empty">
              chưa có
            </div>
          ) : (
            linked.map((b) => (
              <Link key={b.id} href={`/wiki/${b.id}`} className="wbl-row clickable" data-testid="linked-row">
                <div className="wbl-head">
                  <b>{b.title}</b>
                  <span className="faint">
                    #{b.id} {b.anchor ?? ""}
                  </span>
                </div>
                <div className="wbl-snip mut" dangerouslySetInnerHTML={{ __html: b.snippet }} />
              </Link>
            ))
          )}
        </div>

        <div className="wbl-sec-lbl">
          Unlinked mentions <span className="faint">— nhắc tên nhưng chưa link</span>
        </div>
        <div className="wbl-list">
          {unlinked.length === 0 ? (
            <div className="wbl-empty" data-testid="unlinked-empty">
              không có
            </div>
          ) : (
            unlinked.map((b) => (
              <div key={b.id} className="wbl-row unlinked" data-testid="unlinked-row">
                <div className="wbl-head">
                  <b>{b.title}</b>
                  <span className="faint">#{b.id}</span>
                  <button
                    type="button"
                    className="btn sm"
                    style={{ marginLeft: "auto", padding: "2px 9px" }}
                    onClick={() => onLinkUnlinked?.(b.id)}
                    data-testid="unlinked-link-btn"
                  >
                    <Icon name="i-link" /> link nó
                  </button>
                </div>
                <div className="wbl-snip mut" dangerouslySetInnerHTML={{ __html: b.snippet }} />
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
