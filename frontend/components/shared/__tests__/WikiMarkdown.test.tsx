import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

import { WikiMarkdown } from "../WikiMarkdown";

describe("WikiMarkdown (WEXP read-render: react-markdown + remark-gfm, wikilinks preserved)", () => {
  it("renders markdown structure (heading + list + code)", () => {
    render(<WikiMarkdown content={"# Title\n\n- one\n- two\n\n```\ncode\n```"} />);
    expect(screen.getByRole("heading", { name: "Title" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").length).toBe(2);
    expect(screen.getByText("code")).toBeInTheDocument();
  });

  it("preserves [[id|title]] wikilink → clickable /wiki/[id]", () => {
    render(<WikiMarkdown content={"see [[47|MOCs]] here"} />);
    const link = screen.getByText("MOCs").closest("a")!;
    expect(link).toHaveAttribute("href", "/wiki/47");
    expect(link).toHaveAttribute("data-wikilink", "47");
  });

  it("preserves [[id]] bare-id link", () => {
    render(<WikiMarkdown content={"ref [[88]] inline"} />);
    expect(screen.getByText("#88").closest("a")).toHaveAttribute("href", "/wiki/88");
  });

  it("[[Title]] ghost → non-link span (no note yet)", () => {
    render(<WikiMarkdown content={"a [[Ghost Note]] ref"} />);
    const ghost = screen.getByText("Ghost Note");
    expect(ghost.closest("a")).toBeNull();
    expect(ghost).toHaveAttribute("data-wikilink-ghost");
  });

  it("wikilink inside a LIST ITEM still resolves (custom li renderer)", () => {
    render(<WikiMarkdown content={"- item with [[5|five]]"} />);
    const link = screen.getByText("five").closest("a")!;
    expect(link).toHaveAttribute("href", "/wiki/5");
    expect(link.closest("li")).toBeTruthy();
  });

  it("empty content → honest empty state (not a crash)", () => {
    render(<WikiMarkdown content="" testId="md" />);
    expect(screen.getByTestId("md-empty")).toBeInTheDocument();
  });

  it("GFM table renders", () => {
    render(<WikiMarkdown content={"| a | b |\n|---|---|\n| 1 | 2 |"} />);
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
