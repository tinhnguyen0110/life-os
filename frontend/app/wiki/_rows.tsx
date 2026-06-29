"use client";
/* ============================================================
   Wiki vault · pure row renderers (extracted from page.tsx, #138-P2 — pure MOVE,
   no logic change). InboxRow + ActivityRow + the OP op-log label/color map. These
   close over NOTHING from page state (pure functions of their props), so they move
   cleanly. The orphan row + search rows stay in page.tsx (they close over bulk-mode
   state — non-mechanical to extract, left in place).
   ============================================================ */
import Link from "next/link";
import type { WikiInboxItem, WikiActivity, WikiOpKind } from "@/lib/types";

/** op-log label + color (mirrors mock OP map). */
export const OP: Record<WikiOpKind, { lbl: string; color: string }> = {
  create: { lbl: "create", color: "var(--green)" },
  edit: { lbl: "edit", color: "var(--blue)" },
  link: { lbl: "link", color: "var(--accent)" },
  link_candidate: { lbl: "candidate", color: "var(--amber)" },
  refine: { lbl: "refine", color: "var(--violet)" },
  merge: { lbl: "merge", color: "var(--violet)" },
  moc_proposal: { lbl: "MOC", color: "var(--amber)" },
  delete: { lbl: "delete", color: "var(--red)" },
};

export function InboxRow({ it }: { it: WikiInboxItem }) {
  // WIKI-AIFIRST: the /wiki/inbox triage screen is gone. A "cần refine" row now opens
  // the note DIRECTLY at /wiki/{id} (refine in place) instead of the removed queue.
  return (
    <Link href={`/wiki/${it.id}`} className="wlist-row clickable" data-testid="vault-inbox-row">
      <span className="runi run" style={{ width: 16, height: 16, fontSize: 9 }}>{it.linkCount}</span>
      <div className="wlr-body">
        <div className="wlr-t">{it.title ?? <span className="faint">chưa có title</span>}</div>
        <div className="wlr-s mut">{it.rawContent.slice(0, 70)}…</div>
      </div>
      <span className="faint" style={{ fontFamily: "var(--mono)", fontSize: 10, whiteSpace: "nowrap" }}>{it.captured}</span>
    </Link>
  );
}

export function ActivityRow({ a }: { a: WikiActivity }) {
  const op = OP[a.op] ?? { lbl: a.op, color: "var(--tx-1)" };
  return (
    <div className="wact-row" data-testid="vault-act-row">
      <span className="wact-ts num">{a.ts.slice(11, 19) || a.ts}</span>
      <span className="wact-op" style={{ color: op.color, background: `color-mix(in oklch,${op.color} 14%,transparent)` }}>{op.lbl}</span>
      <span className={`wact-actor ${a.actor}`}>{a.actor === "agent" ? "◇ AI" : "● bạn"}</span>
      <span className="wact-detail mut">
        {a.detail ?? `${a.noteTitle || `#${a.noteId}`}`}
      </span>
    </div>
  );
}
