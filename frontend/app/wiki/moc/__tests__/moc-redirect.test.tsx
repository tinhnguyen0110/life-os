import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

/* WIKI-TRIM — the MOC / Synthesize screen was removed (over-engineered for a 1-user
   AI-first app; MOC notes live in Vault/Graph, BE endpoints stay for MCP). This route
   file is now a REDIRECT-ONLY page → /wiki, so old bookmarks don't 404/error. Matches
   the inbox-redirect convention. */
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
}));

import WikiMocRedirectPage from "../page";

afterEach(() => replace.mockReset());

describe("WIKI-TRIM /wiki/moc — redirect-only page", () => {
  it("redirects to /wiki on mount (router.replace), keeping old bookmarks alive", () => {
    render(<WikiMocRedirectPage />);
    expect(replace).toHaveBeenCalledWith("/wiki");
    expect(screen.getByTestId("wiki-moc-redirect")).toHaveTextContent(/Đang chuyển tới Vault/);
  });

  it("never redirects to itself (no /wiki/moc loop)", () => {
    render(<WikiMocRedirectPage />);
    expect(replace).not.toHaveBeenCalledWith("/wiki/moc");
  });
});
