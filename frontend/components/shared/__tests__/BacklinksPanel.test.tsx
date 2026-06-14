import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BacklinksPanel } from "../BacklinksPanel";
import type { WikiBacklinks } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const FULL: WikiBacklinks = {
  linked: [{ id: 88, title: "MOCs are workstations", snippet: "…as <b>[[47]]</b> shows…", anchor: "^b3" }],
  unlinked: [{ id: 102, title: "Evergreen notes compound", snippet: "…knowledge work accretes…" }],
  outbound: [
    { id: 88, title: "MOCs are workstations", isResolved: true },
    { ghost: "Atomicity principle", isResolved: false },
  ],
};

describe("BacklinksPanel", () => {
  it("renders a linked mention as a clickable link with snippet + anchor", () => {
    render(<BacklinksPanel backlinks={FULL} />);
    const row = screen.getByTestId("linked-row");
    expect(row).toHaveAttribute("href", "/wiki/88");
    expect(row).toHaveTextContent("MOCs are workstations");
    expect(row).toHaveTextContent("#88");
    expect(row).toHaveTextContent("^b3");
    // snippet <b> highlight rendered as HTML
    expect(row.querySelector("b")).toBeInTheDocument();
  });

  it("renders an unlinked mention with a 'link nó' action", async () => {
    const onLink = vi.fn();
    render(<BacklinksPanel backlinks={FULL} onLinkUnlinked={onLink} />);
    const row = screen.getByTestId("unlinked-row");
    expect(row).toHaveTextContent("Evergreen notes compound");
    await userEvent.click(screen.getByTestId("unlinked-link-btn"));
    expect(onLink).toHaveBeenCalledWith(102);
  });

  it("renders a resolved outbound link as a navigable link", () => {
    render(<BacklinksPanel backlinks={FULL} />);
    const resolved = screen.getByTestId("outbound-resolved");
    expect(resolved).toHaveAttribute("href", "/wiki/88");
    expect(resolved).toHaveTextContent("#88");
  });

  it("renders a ghost outbound with '+ tạo note' (distinct from resolved)", async () => {
    const onCreate = vi.fn();
    render(<BacklinksPanel backlinks={FULL} onCreateGhost={onCreate} />);
    const ghost = screen.getByTestId("outbound-ghost");
    expect(ghost).toHaveTextContent("Atomicity principle");
    expect(ghost.className).toContain("ghost");
    await userEvent.click(screen.getByTestId("ghost-create"));
    expect(onCreate).toHaveBeenCalledWith("Atomicity principle");
  });

  it("shows empty-states for a note with no connections (no crash)", () => {
    render(<BacklinksPanel backlinks={{ linked: [], unlinked: [], outbound: [] }} />);
    expect(screen.getByTestId("outbound-empty")).toBeInTheDocument();
    expect(screen.getByTestId("linked-empty")).toBeInTheDocument();
    expect(screen.getByTestId("unlinked-empty")).toBeInTheDocument();
  });
});
