import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";

const getWikiProposals = vi.fn();
const acceptWikiProposal = vi.fn();
const rejectWikiProposal = vi.fn();
const batchAcceptWikiProposals = vi.fn();
const deleteWikiNote = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiProposals: (...a: unknown[]) => getWikiProposals(...a),
    acceptWikiProposal: (...a: unknown[]) => acceptWikiProposal(...a),
    rejectWikiProposal: (...a: unknown[]) => rejectWikiProposal(...a),
    batchAcceptWikiProposals: (...a: unknown[]) => batchAcceptWikiProposals(...a),
    deleteWikiNote: (...a: unknown[]) => deleteWikiNote(...a),
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a>,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

import WikiProposalsPage from "../page";
import { ApiError } from "@/lib/api";
import type { WikiProposal, WikiProposalList } from "@/lib/types";

function ok<T>(data: T) {
  return { success: true, data };
}
function prop(over: Partial<WikiProposal>): WikiProposal {
  return {
    id: 1, kind: "note_edit", targetId: 5, payload: { title: "x" }, rationale: "because",
    actor: "agent:claude", status: "pending", correlationId: "mcp-abc", created: "10:00",
    decided: null, decidedBy: null, appliedNoteId: null, ...over,
  };
}
const PENDING: WikiProposalList = {
  proposals: [
    prop({ id: 1, kind: "link_add", targetId: null, payload: { target: 7 }, rationale: "B relates A" }),
    prop({ id: 2, kind: "note_edit", targetId: 5, payload: { title: "newt" }, rationale: "" }),
  ],
  counts: { pending: 2, accepted: 4, rejected: 1 },
};

describe("P1 Nhật ký AI (AI audit-log, WIKI-AIFIRST)", () => {
  it("renders pending proposals with kind badge + rationale + actor", async () => {
    getWikiProposals.mockResolvedValueOnce(ok(PENDING));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("prop-card").length).toBe(2);
    expect(screen.getByText("link add")).toBeInTheDocument();
    expect(screen.getByText("note edit")).toBeInTheDocument();
    // actor agent: prefix rendered as ◇
    expect(screen.getAllByTestId("prop-actor")[0]).toHaveTextContent("◇ claude");
    // empty rationale → honest "(không có giải thích)", not blank
    expect(screen.getByTestId("prop-rationale-empty")).toBeInTheDocument();
  });

  it("accept ONE → calls acceptWikiProposal + refetches", async () => {
    getWikiProposals.mockResolvedValueOnce(ok(PENDING)).mockResolvedValueOnce(ok({ proposals: [PENDING.proposals[1]], counts: { pending: 1, accepted: 5, rejected: 1 } }));
    acceptWikiProposal.mockResolvedValueOnce(ok(prop({ id: 1, status: "accepted", appliedNoteId: 7 })));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getAllByTestId("prop-card").length).toBe(2));
    const card1 = screen.getAllByTestId("prop-card").find((c) => c.getAttribute("data-prop-id") === "1")!;
    fireEvent.click(within(card1).getByTestId("prop-accept"));
    await waitFor(() => expect(acceptWikiProposal).toHaveBeenCalledWith(1, undefined));
    await waitFor(() => expect(getWikiProposals).toHaveBeenCalledTimes(2));
  });

  it("FAIL-CLOSED: accept 4xx → error surfaced ON the card, queue not mutated", async () => {
    getWikiProposals.mockResolvedValue(ok(PENDING));
    acceptWikiProposal.mockRejectedValueOnce(new ApiError(400, "target note 5 not found"));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getAllByTestId("prop-card").length).toBe(2));
    const card1 = screen.getAllByTestId("prop-card").find((c) => c.getAttribute("data-prop-id") === "1")!;
    fireEvent.click(within(card1).getByTestId("prop-accept"));
    const err = await within(card1).findByTestId("prop-error");
    expect(err).toHaveTextContent("target note 5 not found");
    // card still present (not optimistically removed)
    expect(screen.getAllByTestId("prop-card").length).toBe(2);
  });

  it("reject ONE → calls rejectWikiProposal", async () => {
    getWikiProposals.mockResolvedValue(ok(PENDING));
    rejectWikiProposal.mockResolvedValueOnce(ok(prop({ id: 1, status: "rejected" })));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getAllByTestId("prop-card").length).toBe(2));
    const card1 = screen.getAllByTestId("prop-card").find((c) => c.getAttribute("data-prop-id") === "1")!;
    fireEvent.click(within(card1).getByTestId("prop-reject"));
    await waitFor(() => expect(rejectWikiProposal).toHaveBeenCalledWith(1, undefined));
  });

  // WIKI-NO-APPROVAL #183: AI-first = no manual approval gate → the page is a PURE AUDIT log.
  // The "chờ duyệt" filter, the batch-duyệt bar, and the per-card select checkbox are GONE.
  it("🔴 #183 audit-only: NO 'chờ duyệt' filter, NO batch-accept bar, NO per-card select checkbox", async () => {
    getWikiProposals.mockResolvedValue(ok(PENDING)); // even with pending rows present
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-screen")).toBeInTheDocument());
    // the pending filter button is removed; accepted/rejected/all remain
    expect(screen.queryByTestId("prop-filter-pending")).toBeNull();
    expect(screen.getByTestId("prop-filter-accepted")).toBeInTheDocument();
    expect(screen.getByTestId("prop-filter-rejected")).toBeInTheDocument();
    expect(screen.getByTestId("prop-filter-all")).toBeInTheDocument();
    // no batch machinery anywhere
    expect(screen.queryByTestId("prop-batch-bar")).toBeNull();
    expect(screen.queryByTestId("prop-batch-accept")).toBeNull();
    expect(screen.queryByTestId("prop-select")).toBeNull();
    expect(batchAcceptWikiProposals).not.toHaveBeenCalled();
  });

  it("🔴 #183: a legacy PENDING row (under default/all) keeps its per-row accept/reject (no batch gate)", async () => {
    // a stray pending row still renders with its own accept/reject (fail-closed, per-row) —
    // the audit log can still resolve an edge case, just without the headline batch CTA.
    getWikiProposals.mockResolvedValue(ok(PENDING));
    acceptWikiProposal.mockResolvedValueOnce(ok(prop({ id: 1, status: "accepted", appliedNoteId: 7 })));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getAllByTestId("prop-card").length).toBe(2));
    const card1 = screen.getAllByTestId("prop-card").find((c) => c.getAttribute("data-prop-id") === "1")!;
    // per-row actions present (NOT a checkbox)
    expect(within(card1).getByTestId("prop-accept")).toBeInTheDocument();
    expect(within(card1).getByTestId("prop-reject")).toBeInTheDocument();
    expect(within(card1).queryByTestId("prop-select")).toBeNull();
    fireEvent.click(within(card1).getByTestId("prop-accept"));
    await waitFor(() => expect(acceptWikiProposal).toHaveBeenCalledWith(1, undefined));
  });

  it("honest empty: 0 AI writes (accepted default) → audit-log empty message (not a fabricated card, not a queue-empty)", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({ proposals: [], counts: { pending: 0, accepted: 0, rejected: 1 } }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-empty")).toBeInTheDocument());
    const empty = screen.getByTestId("prop-empty");
    // audit-log framing, NOT "chờ duyệt / queue" framing.
    expect(empty).toHaveTextContent(/Chưa có ghi nhớ AI nào/i);
    expect(empty).toHaveTextContent(/Claude Code/i);
    expect(empty).not.toHaveTextContent(/chờ duyệt/i);
    expect(screen.queryByTestId("prop-card")).toBeNull();
  });

  it("decided card (accepted) shows 'AI đã ghi' + applied-note link, NO accept/reject buttons", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 9, status: "accepted", decidedBy: "human", appliedNoteId: 42 })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    expect(screen.getByTestId("prop-decided-status")).toHaveTextContent("AI đã ghi");
    expect(screen.getByTestId("prop-applied-link")).toHaveAttribute("href", "/wiki/42");
    expect(screen.queryByTestId("prop-accept")).toBeNull();
    expect(screen.queryByTestId("prop-reject")).toBeNull();
  });

  it("W4d: auto-accepted proposal (decidedBy agent:auto) shows the distinct ◇ agent:auto badge", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 30, kind: "note_create", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 7, payload: { title: "auto note" } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    const badge = screen.getByTestId("prop-auto-badge");
    expect(badge).toHaveTextContent("agent:auto");
    // applied-note link still present; human-decided "bởi" label is NOT shown for an auto-write
    expect(screen.getByTestId("prop-applied-link")).toHaveAttribute("href", "/wiki/7");
    expect(screen.queryByText(/bởi human/i)).toBeNull();
  });

  it("W4d: human-accepted proposal shows 'bởi human', NOT the auto badge", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 31, status: "accepted", decidedBy: "human", appliedNoteId: 8 })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    expect(screen.queryByTestId("prop-auto-badge")).toBeNull();
    expect(screen.getByText(/bởi human/i)).toBeInTheDocument();
  });

  it("filter switch (→ rejected) re-queries with the new status", async () => {
    getWikiProposals.mockResolvedValueOnce(ok(PENDING)).mockResolvedValueOnce(ok({ proposals: [], counts: { pending: 2, accepted: 4, rejected: 1 } }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("prop-filter-rejected"));
    await waitFor(() => expect(getWikiProposals).toHaveBeenLastCalledWith("rejected"));
  });

  it("WIKI-AIFIRST: loads with status=accepted by default (audit-log working set)", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({ proposals: [], counts: { pending: 0, accepted: 4, rejected: 1 } }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(getWikiProposals).toHaveBeenCalledWith("accepted"));
  });

  it("reframed: title 'Nhật ký AI' + sub 'N lần AI ghi' + AI-first banner (not duyệt-gate)", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({ proposals: [], counts: { pending: 0, accepted: 4, rejected: 1 } }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-screen")).toBeInTheDocument());
    expect(screen.getByText("Nhật ký AI")).toBeInTheDocument();
    expect(screen.getByTestId("prop-subcount")).toHaveTextContent("4 lần AI ghi");
    expect(screen.getByTestId("prop-banner")).toHaveTextContent(/ghi thẳng vào Vault/i);
  });

  it("REVERSE note_create: accepted note_create row → 'Lùi' soft-deletes the applied note + shows khôi phục", async () => {
    // The PROPOSAL record stays `accepted` after a reverse (only the applied NOTE is
    // soft-deleted) → the post-reverse refetch returns the SAME proposal; the card
    // persists and shows the "đã lùi" state (held in the card's local reversed state).
    getWikiProposals.mockResolvedValue(ok({
      proposals: [prop({ id: 40, kind: "note_create", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 55, payload: { title: "auto" } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    deleteWikiNote.mockResolvedValueOnce(ok({ deleted: true, deletedAt: "now" }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("prop-reverse"));
    await waitFor(() => expect(deleteWikiNote).toHaveBeenCalledWith(55));
    const reversed = await screen.findByTestId("prop-reversed");
    expect(reversed).toHaveTextContent(/đã lùi/i);
    expect(screen.getByTestId("prop-reversed-restore")).toHaveAttribute("href", "/wiki?trashed=55");
  });

  it("REVERSE fail-closed: delete 4xx → error on the row, NOT marked reversed", async () => {
    getWikiProposals.mockResolvedValue(ok({
      proposals: [prop({ id: 41, kind: "note_create", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 56, payload: { title: "x" } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    deleteWikiNote.mockRejectedValueOnce(new ApiError(404, "note 56 not found"));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("prop-reverse"));
    const err = await screen.findByTestId("prop-error");
    expect(err).toHaveTextContent("note 56 not found");
    expect(screen.queryByTestId("prop-reversed")).toBeNull();
  });

  it("REVERSE manual (note_edit): NO reverse button — honest manual-refine deep-link + hint instead", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 42, kind: "note_edit", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 60, payload: { title: "edited" } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    expect(screen.queryByTestId("prop-reverse")).toBeNull();
    const manual = screen.getByTestId("prop-reverse-manual");
    expect(manual).toHaveTextContent(/mở note #60 để refine/i);
    expect(manual).toHaveTextContent(/chưa có version-undo/i);
  });

  // ── T4: collapse / expand / markdown for a LONG note_create `content` payload ──
  const LONG_MD = "# Blog roadmap\n\nMột đoạn dài về tracing.\n\n## Chuỗi bài\n- Bài 1: validate\n- Bài 2: tracing\n\nCòn nhiều dòng nữa để vượt ngưỡng 120 ký tự và có newline.";

  it("T4: long note_create content is COLLAPSED by default — preview clamp + 'xem thêm' toggle, full markdown NOT rendered yet", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 50, kind: "note_create", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 70, payload: { title: "Blog roadmap", content: LONG_MD } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    // collapsed: a raw-text preview + a toggle; the markdown body is NOT mounted yet.
    expect(screen.getByTestId("prop-content-preview")).toBeInTheDocument();
    expect(screen.getByTestId("prop-content-toggle")).toHaveTextContent(/xem thêm/i);
    expect(screen.getByTestId("prop-content-toggle")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByTestId("prop-content-expanded")).toBeNull();
    // the long content does NOT leak into the inline payload dump (it's pulled out).
    expect(screen.queryByTestId("prop-payload")).not.toHaveTextContent(/Chuỗi bài/);
  });

  it("T4: click 'xem thêm' → EXPANDS to WikiMarkdown (heading + list elements render), toggle flips to 'thu gọn'", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 51, kind: "note_create", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 71, payload: { title: "Blog roadmap", content: LONG_MD } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("prop-content-toggle"));
    // expanded: the markdown body mounts + emits real heading/list elements.
    const md = await screen.findByTestId("prop-content-md");
    expect(md.querySelector("h2, h3")).toBeTruthy();          // # / ## → heading
    expect(md.querySelectorAll("li").length).toBeGreaterThan(0); // - items → list
    expect(screen.getByTestId("prop-content-toggle")).toHaveTextContent(/thu gọn/i);
    expect(screen.getByTestId("prop-content-toggle")).toHaveAttribute("aria-expanded", "true");
    // preview is gone once expanded
    expect(screen.queryByTestId("prop-content-preview")).toBeNull();
  });

  it("T4: SHORT content → NO collapse toggle, rendered inline in the generic payload (1-liner doesn't need a toggle)", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 52, kind: "note_create", status: "accepted", decidedBy: "agent:auto", appliedNoteId: 72, payload: { title: "t", content: "hi" } })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    expect(screen.queryByTestId("prop-content-toggle")).toBeNull();
    expect(screen.queryByTestId("prop-content-block")).toBeNull();
    // short content stays inline in the generic dict render
    expect(screen.getByTestId("prop-payload")).toHaveTextContent(/content: hi/);
  });
});
