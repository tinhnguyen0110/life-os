import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

/* WIKI-TRIM — the Sync & Integrity (conflict-resolution) screen was removed (a
   multi-user problem that doesn't exist in a 1-user AI-first app; BE endpoints stay
   for MCP). This route file is now a REDIRECT-ONLY page → /wiki, so old bookmarks
   don't 404/error. Matches the inbox-redirect convention. */
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
}));

import WikiSyncRedirectPage from "../page";

afterEach(() => replace.mockReset());

describe("WIKI-TRIM /wiki/sync — redirect-only page", () => {
  it("redirects to /wiki on mount (router.replace), keeping old bookmarks alive", () => {
    render(<WikiSyncRedirectPage />);
    expect(replace).toHaveBeenCalledWith("/wiki");
    expect(screen.getByTestId("wiki-sync-redirect")).toHaveTextContent(/Đang chuyển tới Vault/);
  });

  it("never redirects to itself (no /wiki/sync loop)", () => {
    render(<WikiSyncRedirectPage />);
    expect(replace).not.toHaveBeenCalledWith("/wiki/sync");
  });
});
