import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

/* Partial-mock the named api fns the W1 page (via useWikiOverview + searchWiki)
   actually calls — NOT lower-level apiGet (memory: vitest-mock-named-api). */
const getWikiOverview = vi.fn();
const searchWiki = vi.fn();
const bulkDeleteWikiNotes = vi.fn();
const getWikiTrash = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiOverview: (...a: unknown[]) => getWikiOverview(...a),
    searchWiki: (...a: unknown[]) => searchWiki(...a),
    bulkDeleteWikiNotes: (...a: unknown[]) => bulkDeleteWikiNotes(...a),
    getWikiTrash: (...a: unknown[]) => getWikiTrash(...a),
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a>,
}));
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

import WikiVaultPage from "../page";
import type { WikiOverview } from "@/lib/types";

function ok<T>(data: T, warning?: string) {
  return { success: true, data, ...(warning ? { warning } : {}) };
}

const FULL: WikiOverview = {
  stats: {
    totalNotes: 142,
    byStatus: { fleeting: 8, developing: 31, evergreen: 103 },
    totalLinks: 487,
    orphanCount: 6,
    ghostLinkCount: 3,
    pctWithLink: 94.2,
    asOf: "2026-06-14T10:00:00Z",
  },
  inbox: [
    { id: 47, title: null, status: "fleeting", rawContent: "raw dump về tích lũy tri thức", captured: "08:12", captureSource: "quick_add", linkCount: 0, aiSuggest: null },
  ],
  orphans: [
    { id: 12, title: "Spaced repetition is interest-driven", status: "evergreen", degree: 0, lastTouched: "2026-04-01" },
  ],
  recentActivity: [
    { ts: "2026-06-14T09:55:00Z", op: "edit", actor: "human", noteId: 88, noteTitle: "MOCs are workstations", detail: null },
    { ts: "2026-06-14T09:40:00Z", op: "create", actor: "agent", noteId: 47, noteTitle: "", detail: "agent created #47" },
  ],
  proposalCount: 0,
};

const EMPTY: WikiOverview = {
  stats: { totalNotes: 0, byStatus: { fleeting: 0, developing: 0, evergreen: 0 }, totalLinks: 0, orphanCount: 0, ghostLinkCount: 0, pctWithLink: null, asOf: "2026-06-14T10:00:00Z" },
  inbox: [],
  orphans: [],
  recentActivity: [],
  proposalCount: 0,
};

describe("W1 Vault Overview", () => {
  it("renders the 6 stat tiles + density % from live stats", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("wtile").length).toBe(6);
    // total notes tile shows the live number, not a placeholder
    const tiles = screen.getAllByTestId("wtile-v").map((e) => e.textContent);
    expect(tiles).toContain("142");
    expect(tiles).toContain("8"); // fleeting
    // density bar reflects pctWithLink
    expect(screen.getByTestId("vault-density-pct")).toHaveTextContent("94.2%");
  });

  it("WIKI-HOME-TRIM: NO 'Inbox cần refine' panel; orphan summary rows + op-log activity stay", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    // the inbox-refine panel is removed (AI-first → no manual triage on home)
    expect(screen.queryByTestId("vault-inbox-list")).toBeNull();
    expect(screen.queryByTestId("vault-inbox-count")).toBeNull();
    expect(screen.queryByTestId("vault-inbox-row")).toBeNull();
    expect(screen.queryByText("Inbox cần refine")).toBeNull();
    // orphan sweep + op-log stay
    expect(screen.getAllByTestId("vault-orphan-row").length).toBe(1);
    expect(screen.getByText("Spaced repetition is interest-driven")).toBeInTheDocument();
    expect(screen.getAllByTestId("vault-act-row").length).toBe(2);
  });

  it("WIKI-HOME-TRIM: KPI 'Fleeting' StatTile (byStatus.fleeting) still present (a DIFFERENT metric, not the inbox queue)", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    // the Fleeting KPI tile (status count = 8) survives — it's not the removed inbox-queue badge
    expect(screen.getByText("Fleeting")).toBeInTheDocument();
    const tiles = screen.getAllByTestId("wtile-v").map((e) => e.textContent);
    expect(tiles).toContain("8");
  });

  it("WIKI-HOME-TRIM #183: NO 'Proposal queue · chờ duyệt' panel (AI-first → AI writes directly, no review queue)", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    // the proposal-queue panel + the wrong "never auto-write" copy are removed
    expect(screen.queryByTestId("vault-proposal-count")).toBeNull();
    expect(screen.queryByTestId("vault-proposal-empty")).toBeNull();
    expect(screen.queryByText(/chờ duyệt/i)).toBeNull();
    expect(screen.queryByText(/không bao giờ tự ghi/i)).toBeNull();
    expect(screen.queryByText("Proposal queue")).toBeNull();
    // op-log stays (now full-width)
    expect(screen.getByTestId("vault-act-list")).toBeInTheDocument();
  });

  it("empty vault (0 notes) → 'vault rỗng' prompt, NOT fake tiles (pctWithLink null → no 0%)", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(EMPTY, "empty vault — no notes yet"));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-empty")).toBeInTheDocument());
    expect(screen.queryAllByTestId("wtile").length).toBe(0); // no stat tiles when empty
  });

  it("loading then error state surfaces", async () => {
    getWikiOverview.mockRejectedValueOnce(new Error("boom"));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-error")).toBeInTheDocument());
    expect(screen.getByTestId("vault-error")).toHaveTextContent("boom");
  });

  it("FTS search box → calls searchWiki and renders hits (Enter routes to note)", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([{ id: 88, title: "MOCs are workstations", status: "evergreen", snippet: "...work accretes..." }]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("vault-search-input"), { target: { value: "MOC" } });
    await waitFor(() => expect(searchWiki).toHaveBeenCalledWith("MOC"));
    const hit = await screen.findByTestId("vault-search-hit");
    expect(hit).toHaveTextContent("MOCs are workstations");
    fireEvent.keyDown(hit, { key: "Enter" });
    expect(mockPush).toHaveBeenCalledWith("/wiki/88");
  });

  it("search with no match → honest empty result (not a fabricated hit)", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("vault-search-input"), { target: { value: "zzz" } });
    await waitFor(() => expect(screen.getByTestId("vault-search-empty")).toBeInTheDocument());
    expect(screen.queryByTestId("vault-search-hit")).toBeNull();
  });
});

/* ---- #94 trash button + bulk soft-delete ---- */
const MULTI_ORPHAN: WikiOverview = {
  ...FULL,
  orphans: [
    { id: 12, title: "Orphan A", status: "evergreen", degree: 0, lastTouched: "2026-04-01" },
    { id: 13, title: "Orphan B", status: "fleeting", degree: 0, lastTouched: "2026-04-02" },
    { id: 14, title: "Orphan C", status: "developing", degree: 0, lastTouched: "2026-04-03" },
  ],
};

describe("W1 Vault — #94 trash + bulk soft-delete", () => {
  it("has a Trash button opening the trash modal", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    getWikiTrash.mockResolvedValue(ok({ trash: [], count: 0 }));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-trash-btn")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("vault-trash-btn"));
    await waitFor(() => expect(screen.getByTestId("wiki-trash")).toBeInTheDocument());
  });

  it("bulk-mode → checkboxes on orphans; select 2 → bulk-delete (IN-PAGE confirm) → POST {ids}", async () => {
    getWikiOverview.mockResolvedValue(ok(MULTI_ORPHAN)); // resolved (not Once) — survives reload-after-delete
    searchWiki.mockResolvedValue(ok([]));
    bulkDeleteWikiNotes.mockResolvedValue(ok({ results: [{ id: 12, ok: true, error: null }, { id: 13, ok: true, error: null }], deletedCount: 2 }));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-orphan-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("bulk-mode-btn"));
    // checkboxes appear (no navigation)
    await waitFor(() => expect(screen.getByTestId("bulk-check-12")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bulk-check-12"));
    fireEvent.click(screen.getByTestId("bulk-check-13"));
    expect(screen.getByTestId("bulk-count")).toHaveTextContent("2 đã chọn");

    // delete → IN-PAGE confirm (no window.confirm)
    const confirmSpy = vi.spyOn(window, "confirm");
    fireEvent.click(screen.getByTestId("bulk-delete-btn"));
    expect(screen.getByTestId("bulk-confirm-yes")).toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("bulk-confirm-yes"));
    await waitFor(() => expect(bulkDeleteWikiNotes).toHaveBeenCalledWith([12, 13]));
    // result surface
    await waitFor(() => expect(screen.getByTestId("bulk-result")).toHaveTextContent("2 đã chuyển"));
    confirmSpy.mockRestore();
  });

  it("bulk-delete fail-soft → shows the per-id errors (no crash)", async () => {
    getWikiOverview.mockResolvedValue(ok(MULTI_ORPHAN));
    searchWiki.mockResolvedValue(ok([]));
    bulkDeleteWikiNotes.mockResolvedValue(ok({
      results: [{ id: 12, ok: true, error: null }, { id: 13, ok: false, error: { code: "NOT_FOUND", message: "no note #13" } }],
      deletedCount: 1,
    }));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-orphan-list")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bulk-mode-btn"));
    await waitFor(() => expect(screen.getByTestId("bulk-check-12")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bulk-check-12"));
    fireEvent.click(screen.getByTestId("bulk-check-13"));
    fireEvent.click(screen.getByTestId("bulk-delete-btn"));
    fireEvent.click(screen.getByTestId("bulk-confirm-yes"));
    await waitFor(() => expect(screen.getByTestId("bulk-errors")).toHaveTextContent("no note #13"));
    expect(screen.getByTestId("bulk-result")).toHaveTextContent("1 đã chuyển");
  });

  it("bulk confirm can be cancelled (no POST)", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(MULTI_ORPHAN));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-orphan-list")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bulk-mode-btn"));
    await waitFor(() => expect(screen.getByTestId("bulk-check-12")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("bulk-check-12"));
    fireEvent.click(screen.getByTestId("bulk-delete-btn"));
    fireEvent.click(screen.getByTestId("bulk-confirm-no"));
    expect(screen.queryByTestId("bulk-confirm-yes")).toBeNull();
    expect(bulkDeleteWikiNotes).not.toHaveBeenCalled();
  });
});
