import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

/* Partial-mock the named api fns the W1 page (via useWikiOverview + searchWiki)
   actually calls — NOT lower-level apiGet (memory: vitest-mock-named-api). */
const getWikiOverview = vi.fn();
const searchWiki = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getWikiOverview: (...a: unknown[]) => getWikiOverview(...a),
    searchWiki: (...a: unknown[]) => searchWiki(...a),
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

  it("renders inbox + orphan summary rows + op-log activity", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    expect(screen.getAllByTestId("vault-inbox-row").length).toBe(1);
    expect(screen.getAllByTestId("vault-orphan-row").length).toBe(1);
    expect(screen.getByText("Spaced repetition is interest-driven")).toBeInTheDocument();
    expect(screen.getAllByTestId("vault-act-row").length).toBe(2);
  });

  it("HONEST: proposalCount 0 → no fabricated queue, shows never-auto-write empty state", async () => {
    getWikiOverview.mockResolvedValueOnce(ok(FULL));
    searchWiki.mockResolvedValue(ok([]));
    render(<WikiVaultPage />);
    await waitFor(() => expect(screen.getByTestId("vault-screen")).toBeInTheDocument());
    expect(screen.getByTestId("vault-proposal-count")).toHaveTextContent("0");
    const empty = screen.getByTestId("vault-proposal-empty");
    expect(empty).toBeInTheDocument();
    expect(empty.textContent).toMatch(/không bao giờ tự ghi/i);
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
