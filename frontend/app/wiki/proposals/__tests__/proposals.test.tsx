import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";

const getWikiProposals = vi.fn();
const acceptWikiProposal = vi.fn();
const rejectWikiProposal = vi.fn();
const batchAcceptWikiProposals = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiProposals: (...a: unknown[]) => getWikiProposals(...a),
    acceptWikiProposal: (...a: unknown[]) => acceptWikiProposal(...a),
    rejectWikiProposal: (...a: unknown[]) => rejectWikiProposal(...a),
    batchAcceptWikiProposals: (...a: unknown[]) => batchAcceptWikiProposals(...a),
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

describe("P1 Proposal Queue", () => {
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

  it("batch-accept selected pending → calls accept-batch with the ids + shows success notice", async () => {
    getWikiProposals.mockResolvedValue(ok(PENDING));
    batchAcceptWikiProposals.mockResolvedValueOnce(ok({ results: [{ id: 1, ok: true }, { id: 2, ok: true }], accepted: 2, failed: 0 }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getAllByTestId("prop-card").length).toBe(2));
    const sels = screen.getAllByTestId("prop-select");
    fireEvent.click(sels[0]);
    fireEvent.click(sels[1]);
    fireEvent.click(screen.getByTestId("prop-batch-accept"));
    await waitFor(() => expect(batchAcceptWikiProposals).toHaveBeenCalledWith({ ids: [1, 2] }));
    expect(await screen.findByTestId("prop-batch-notice")).toHaveTextContent("2");
  });

  it("PARTIAL batch failure (200 + failed>0) → surfaced honestly, NOT swallowed", async () => {
    getWikiProposals.mockResolvedValue(ok(PENDING));
    // batch returns 200 but one id failed to apply — must NOT be treated as all-success.
    batchAcceptWikiProposals.mockResolvedValueOnce(ok({
      results: [{ id: 1, ok: true }, { id: 2, ok: false, error: "target note 5 not found" }],
      accepted: 1, failed: 1,
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getAllByTestId("prop-card").length).toBe(2));
    const sels = screen.getAllByTestId("prop-select");
    fireEvent.click(sels[0]);
    fireEvent.click(sels[1]);
    fireEvent.click(screen.getByTestId("prop-batch-accept"));
    const err = await screen.findByTestId("prop-batch-error");
    expect(err).toHaveTextContent("1 lỗi");
    expect(err).toHaveTextContent("#2");
    expect(err).toHaveTextContent("target note 5 not found");
  });

  it("honest empty: 0 pending → queue-clean message (not a fabricated card)", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({ proposals: [], counts: { pending: 0, accepted: 4, rejected: 1 } }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-empty")).toBeInTheDocument());
    expect(screen.getByTestId("prop-empty")).toHaveTextContent(/Claude Code/i);
    expect(screen.queryByTestId("prop-card")).toBeNull();
  });

  it("decided card (accepted) shows outcome + applied-note link, NO accept/reject buttons", async () => {
    getWikiProposals.mockResolvedValueOnce(ok({
      proposals: [prop({ id: 9, status: "accepted", decidedBy: "human", appliedNoteId: 42 })],
      counts: { pending: 0, accepted: 1, rejected: 0 },
    }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-card")).toBeInTheDocument());
    expect(screen.getByTestId("prop-decided-status")).toHaveTextContent("accepted");
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

  it("filter switch (pending→rejected) re-queries with the new status", async () => {
    getWikiProposals.mockResolvedValueOnce(ok(PENDING)).mockResolvedValueOnce(ok({ proposals: [], counts: { pending: 2, accepted: 4, rejected: 1 } }));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(screen.getByTestId("prop-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("prop-filter-rejected"));
    await waitFor(() => expect(getWikiProposals).toHaveBeenLastCalledWith("rejected"));
  });

  it("loads with status=pending by default", async () => {
    getWikiProposals.mockResolvedValueOnce(ok(PENDING));
    render(<WikiProposalsPage />);
    await waitFor(() => expect(getWikiProposals).toHaveBeenCalledWith("pending"));
  });
});
