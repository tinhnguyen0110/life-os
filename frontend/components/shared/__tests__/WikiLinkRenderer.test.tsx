import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { WikiLinkRenderer } from "../WikiLinkRenderer";

// next/link → plain <a href> (project convention, see Sidebar.test).
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("WikiLinkRenderer", () => {
  it("renders [[id|title]] as a resolved link to /wiki/id showing the title", () => {
    render(<WikiLinkRenderer content="see [[88|MOCs are workstations]] here" />);
    const link = screen.getByText("MOCs are workstations");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/wiki/88");
    expect(link).toHaveAttribute("data-wikilink", "88");
    expect(link.className).toContain("wlink");
    expect(link.className).not.toContain("ghost");
  });

  it("renders [[id]] as a resolved link to /wiki/id showing #id", () => {
    render(<WikiLinkRenderer content="as [[47]] shows" />);
    const link = screen.getByText("#47");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/wiki/47");
    expect(link).toHaveAttribute("data-wikilink", "47");
  });

  it("renders [[Title]] (no id) as a GHOST span — NOT a link, distinct styling", () => {
    render(<WikiLinkRenderer content="and [[Atomicity principle]] later" />);
    const ghost = screen.getByText("Atomicity principle");
    expect(ghost.tagName).toBe("SPAN"); // ghost is NOT a navigable link
    expect(ghost.className).toContain("wlink");
    expect(ghost.className).toContain("ghost");
    expect(ghost).toHaveAttribute("data-wikilink-ghost");
    expect(ghost).not.toHaveAttribute("href");
  });

  it("renders all three forms + **bold** together in one body", () => {
    render(
      <WikiLinkRenderer content="**Tri thức** links [[47|accretes]] to [[88]] and [[Ghost note]]." />,
    );
    expect(screen.getByText("Tri thức").tagName).toBe("B");
    expect(screen.getByText("accretes")).toHaveAttribute("href", "/wiki/47");
    expect(screen.getByText("#88")).toHaveAttribute("href", "/wiki/88");
    const ghost = screen.getByText("Ghost note");
    expect(ghost.tagName).toBe("SPAN");
    expect(ghost.className).toContain("ghost");
  });

  it("splits blank-line-separated blocks into paragraphs", () => {
    const { container } = render(<WikiLinkRenderer content={"First para.\n\nSecond para."} />);
    const paras = container.querySelectorAll("p");
    expect(paras.length).toBe(2);
    expect(paras[0]).toHaveTextContent("First para.");
    expect(paras[1]).toHaveTextContent("Second para.");
  });

  it("renders a markdown heading and an unordered list", () => {
    const { container } = render(
      <WikiLinkRenderer content={"## PKM\n\n- one\n- two"} />,
    );
    expect(container.querySelector("h3")).toHaveTextContent("PKM");
    const lis = container.querySelectorAll("ul.wmd-ul li");
    expect(lis.length).toBe(2);
    expect(lis[0]).toHaveTextContent("one");
  });

  it("shows an empty-state (not a crash) for blank content", () => {
    render(<WikiLinkRenderer content="" />);
    expect(screen.getByTestId("wiki-body-empty")).toBeInTheDocument();
  });

  it("does not turn a malformed [[ into a link (no false-positive)", () => {
    const { container } = render(<WikiLinkRenderer content="open bracket [[ not closed" />);
    expect(container.querySelectorAll("a").length).toBe(0);
    expect(container.querySelector('[data-testid="wiki-body"]')).toHaveTextContent(
      "open bracket [[ not closed",
    );
  });
});
