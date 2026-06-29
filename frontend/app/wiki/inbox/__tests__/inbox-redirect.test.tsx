import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";

/* WIKI-AIFIRST — the standalone /wiki/inbox triage screen was removed. This route
   file is now a REDIRECT-ONLY page that sends old bookmarks/deep-links to /wiki
   (instead of falling into /wiki/[id] and showing a confusing "invalid id" error).
   Matches the /graveyard + /dev-activity redirect convention. */
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
}));

import WikiInboxRedirectPage from "../page";

afterEach(() => replace.mockReset());

describe("WIKI-AIFIRST /wiki/inbox — redirect-only page", () => {
  it("redirects to /wiki on mount (router.replace), keeping old bookmarks alive", () => {
    render(<WikiInboxRedirectPage />);
    expect(replace).toHaveBeenCalledWith("/wiki");
    // honest interim copy (not a blank screen) while the redirect lands
    expect(screen.getByTestId("wiki-inbox-redirect")).toHaveTextContent(/Đang chuyển tới Vault/);
  });

  it("never redirects to itself (no /wiki/inbox loop)", () => {
    render(<WikiInboxRedirectPage />);
    expect(replace).not.toHaveBeenCalledWith("/wiki/inbox");
  });
});
