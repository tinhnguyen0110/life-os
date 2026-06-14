import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, within, fireEvent } from "@testing-library/react";

const getWikiConflicts = vi.fn();
const resolveWikiConflict = vi.fn();
const verifyWikiCitations = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiConflicts: (...a: unknown[]) => getWikiConflicts(...a),
    resolveWikiConflict: (...a: unknown[]) => resolveWikiConflict(...a),
    verifyWikiCitations: (...a: unknown[]) => verifyWikiCitations(...a),
  };
});
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mockPush }) }));

import WikiSyncPage from "../page";
import { ApiError } from "@/lib/api";
import type { WikiConflictList, WikiCitationVerifyResult } from "@/lib/types";

function ok<T>(data: T) { return { success: true, data }; }

const CONFLICTS: WikiConflictList = {
  conflicts: [
    {
      id: 1, noteId: 7, blockIndex: 2, status: "open", detected: "10:00", resolved: null,
      versions: [
        { device: "laptop", content: "version from laptop", ts: "09:59" },
        { device: "phone", content: "version from phone", ts: "10:00" },
      ],
    },
  ],
};

describe("A1c Sync & Integrity — conflicts", () => {
  it("renders open conflicts with every version (0 data loss)", async () => {
    getWikiConflicts.mockResolvedValueOnce(ok(CONFLICTS));
    verifyWikiCitations.mockResolvedValue(ok({ results: [], summary: { verified: 0, rejected: 0, ungrounded: 0, weaklyGrounded: 0, total: 0 } }));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("conflicts-section")).toBeInTheDocument());
    expect(screen.getByTestId("conflict-card")).toBeInTheDocument();
    expect(screen.getAllByTestId("conflict-version").length).toBe(2);
    expect(screen.getByText("version from laptop")).toBeInTheDocument();
    expect(screen.getByText("version from phone")).toBeInTheDocument();
  });

  it("picking a version → resolveWikiConflict(id, noteId, chosen content) + refetch", async () => {
    getWikiConflicts.mockResolvedValueOnce(ok(CONFLICTS)).mockResolvedValueOnce(ok({ conflicts: [] }));
    resolveWikiConflict.mockResolvedValueOnce(ok({}));
    verifyWikiCitations.mockResolvedValue(ok({ results: [], summary: { verified: 0, rejected: 0, ungrounded: 0, weaklyGrounded: 0, total: 0 } }));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("conflict-card")).toBeInTheDocument());
    const picks = screen.getAllByTestId("conflict-pick");
    fireEvent.click(picks[1]); // pick the phone version
    await waitFor(() => expect(resolveWikiConflict).toHaveBeenCalledWith(1, { noteId: 7, content: "version from phone" }));
    await waitFor(() => expect(getWikiConflicts).toHaveBeenCalledTimes(2));
  });

  it("FAIL-CLOSED: resolve 404 (already decided) → error on card, list NOT mutated", async () => {
    getWikiConflicts.mockResolvedValue(ok(CONFLICTS));
    resolveWikiConflict.mockRejectedValueOnce(new ApiError(404, "conflict already resolved"));
    verifyWikiCitations.mockResolvedValue(ok({ results: [], summary: { verified: 0, rejected: 0, ungrounded: 0, weaklyGrounded: 0, total: 0 } }));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("conflict-card")).toBeInTheDocument());
    fireEvent.click(screen.getAllByTestId("conflict-pick")[0]);
    const err = await within(screen.getByTestId("conflict-card")).findByTestId("conflict-error");
    expect(err).toHaveTextContent("already resolved");
    expect(screen.getByTestId("conflict-card")).toBeInTheDocument(); // still present
  });

  it("honest empty: no conflicts → testid-scoped empty (LWW auto-converges)", async () => {
    getWikiConflicts.mockResolvedValueOnce(ok({ conflicts: [] }));
    verifyWikiCitations.mockResolvedValue(ok({ results: [], summary: { verified: 0, rejected: 0, ungrounded: 0, weaklyGrounded: 0, total: 0 } }));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("conflicts-empty")).toBeInTheDocument());
    expect(screen.queryByTestId("conflict-card")).toBeNull();
  });
});

const VERIFY: WikiCitationVerifyResult = {
  results: [
    { claim: "spaced repetition works", noteId: 5, status: "verified", reason: "span_found", resolvedNoteId: 5 },
    { claim: "unicorns exist", noteId: 5, status: "rejected", reason: "span_not_in_note", resolvedNoteId: null },
    { claim: "no cite", noteId: null, status: "ungrounded", reason: "no_citation", resolvedNoteId: null },
  ],
  summary: { verified: 1, rejected: 1, ungrounded: 1, weaklyGrounded: 0, total: 3 },
};

describe("A1c Sync & Integrity — citation verify (no chatbox, SPEC L257)", () => {
  it("verify → renders per-claim status + summary", async () => {
    getWikiConflicts.mockResolvedValue(ok({ conflicts: [] }));
    verifyWikiCitations.mockResolvedValueOnce(ok(VERIFY));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("citations-section")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("cite-input"), { target: { value: '{"claims":[{"claim":"x","noteId":5}]}' } });
    fireEvent.click(screen.getByTestId("cite-verify"));
    await waitFor(() => expect(screen.getByTestId("cite-summary")).toBeInTheDocument());
    expect(screen.getAllByTestId("cite-row").length).toBe(3);
    expect(screen.getByTestId("cite-summary")).toHaveTextContent("1"); // verified count
  });

  it("verified citation is click→jump to /wiki/[note]; rejected/ungrounded are NOT clickable", async () => {
    getWikiConflicts.mockResolvedValue(ok({ conflicts: [] }));
    verifyWikiCitations.mockResolvedValueOnce(ok(VERIFY));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("citations-section")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("cite-input"), { target: { value: "x | 5 |" } });
    fireEvent.click(screen.getByTestId("cite-verify"));
    await waitFor(() => expect(screen.getAllByTestId("cite-row").length).toBe(3));
    const rows = screen.getAllByTestId("cite-row");
    const verifiedRow = rows.find((r) => r.getAttribute("data-status") === "verified")!;
    fireEvent.click(verifiedRow);
    expect(mockPush).toHaveBeenCalledWith("/wiki/5");
    mockPush.mockClear();
    // rejected row click does nothing
    const rejectedRow = rows.find((r) => r.getAttribute("data-status") === "rejected")!;
    fireEvent.click(rejectedRow);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("parses line-format (claim | noteId | span) too", async () => {
    getWikiConflicts.mockResolvedValue(ok({ conflicts: [] }));
    verifyWikiCitations.mockResolvedValueOnce(ok(VERIFY));
    render(<WikiSyncPage />);
    await waitFor(() => expect(screen.getByTestId("citations-section")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("cite-input"), { target: { value: "spaced repetition works | 5 | spaced" } });
    fireEvent.click(screen.getByTestId("cite-verify"));
    await waitFor(() => expect(verifyWikiCitations).toHaveBeenCalled());
    const arg = verifyWikiCitations.mock.calls[0][0];
    expect(arg.claims[0]).toEqual({ claim: "spaced repetition works", noteId: 5, span: "spaced" });
  });
});
