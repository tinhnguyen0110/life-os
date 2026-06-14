"use client";
/* ============================================================
   Wiki badges — ported from mock screens-wiki.js statusPill/trustBadge/typeBadge
   (L9-19) + wiki.css (.wstatus/.wtrust/.wtype). STATUS_META colors live in CSS
   classes (.wstatus.fleeting etc.) so the component stays presentational.

   - StatusPill: fleeting / developing / evergreen (soft, editable-in-place upstream).
   - TrustTierBadge: verified (human) vs candidate (agent). NO AI sparkle icon
     (ARCH §11 — i-ai omitted); candidate uses a neutral "◇" marker + i-check for
     verified, matching the no-embedded-AI stance.
   - TypeBadge: concept ◆ / literature ▢.
   ============================================================ */
import { Icon } from "@/lib/icons";
import type { WikiStatus, WikiNoteType, WikiTrustTier } from "@/lib/types";

const STATUS_LABEL: Record<WikiStatus, string> = {
  fleeting: "fleeting",
  developing: "developing",
  evergreen: "evergreen",
};

export function StatusPill({ status, testId }: { status: WikiStatus; testId?: string }) {
  return (
    <span className={`wstatus ${status}`} data-testid={testId} data-status={status}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function TrustTierBadge({ tier, testId }: { tier: WikiTrustTier; testId?: string }) {
  if (tier === "candidate") {
    return (
      <span className="wtrust cand" data-testid={testId} data-tier="candidate" title="Do agent đề xuất — chưa ratify">
        ◇ candidate
      </span>
    );
  }
  return (
    <span className="wtrust ver" data-testid={testId} data-tier="verified" title="Người xác nhận">
      <Icon name="i-check" /> verified
    </span>
  );
}

export function TypeBadge({ type, testId }: { type: WikiNoteType; testId?: string }) {
  const label = type === "concept" ? "◆ concept" : type === "literature" ? "▢ literature" : `⬡ ${type}`;
  return (
    <span className="wtype" data-testid={testId} data-type={type}>
      {label}
    </span>
  );
}

/** The candidate-warning banner shown on a note whose trustTier=candidate (W2). */
export function CandidateWarning({ testId }: { testId?: string }) {
  return (
    <div className="wcand-warn" data-testid={testId} role="note">
      ◇ Note này do agent viết — đang ở trạng thái <b>candidate</b>. Ratify ở Proposal queue để thành verified.
    </div>
  );
}
