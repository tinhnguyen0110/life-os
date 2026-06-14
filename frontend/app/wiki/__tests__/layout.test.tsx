import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// WikiExplorer fetches the tree — stub it so the layout test is about the 2-pane shell.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getWikiTree: () => Promise.resolve({ success: true, data: { name: "", path: "", folders: [], notes: [] } }) };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/wiki" }));

import WikiLayout from "../layout";

describe("Wiki 2-pane layout (WEXP)", () => {
  it("renders explorer LEFT pane + content outlet", async () => {
    render(<WikiLayout><div data-testid="child">CONTENT</div></WikiLayout>);
    expect(screen.getByTestId("wiki-pane-left")).toBeInTheDocument();
    expect(screen.getByTestId("wiki-pane-content")).toHaveTextContent("CONTENT");
    await waitFor(() => expect(screen.getByTestId("wiki-explorer")).toBeInTheDocument());
  });

  it("collapse toggle hides the explorer pane", async () => {
    render(<WikiLayout><div>x</div></WikiLayout>);
    const pane = screen.getByTestId("wiki-pane-left");
    expect(pane).not.toHaveAttribute("hidden");
    fireEvent.click(screen.getByTestId("wiki-pane-toggle"));
    await waitFor(() => expect(screen.getByTestId("wiki-pane-left")).toHaveAttribute("hidden"));
    // 2-pane container reflects collapsed state
    expect(screen.getByTestId("wiki-2pane")).toHaveAttribute("data-collapsed", "true");
  });

  it("content (the wiki route) always renders even when collapsed", async () => {
    render(<WikiLayout><div data-testid="child">ROUTE</div></WikiLayout>);
    fireEvent.click(screen.getByTestId("wiki-pane-toggle"));
    expect(screen.getByTestId("child")).toHaveTextContent("ROUTE");
  });
});
