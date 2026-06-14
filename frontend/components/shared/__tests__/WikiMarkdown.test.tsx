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

  // --- Bug #2 regression: title-based [[Title]] of an EXISTING note must resolve to
  //     a clickable link (it used to ALWAYS render a dead ghost — the renderer had no
  //     title→id map). The note page passes `resolve` built from resolved outbound edges.
  it("[[Title]] of an existing note (in resolve map) → clickable link to its id", () => {
    const resolve = new Map<string, number>([["linking notes", 2]]);
    render(<WikiMarkdown content={"see [[Linking Notes]] here"} resolve={resolve} />);
    const link = screen.getByText("Linking Notes").closest("a")!;
    expect(link).toHaveAttribute("href", "/wiki/2");
    expect(link).toHaveAttribute("data-wikilink", "2");
    // it is NOT a ghost
    expect(screen.getByText("Linking Notes")).not.toHaveAttribute("data-wikilink-ghost");
  });

  it("[[Title]] resolution is case-insensitive", () => {
    const resolve = new Map<string, number>([["atomic notes", 1]]);
    render(<WikiMarkdown content={"ref [[ATOMIC notes]] inline"} resolve={resolve} />);
    expect(screen.getByText("ATOMIC notes").closest("a")).toHaveAttribute("href", "/wiki/1");
  });

  it("DISTINGUISHING: with a resolve map, an UNresolved title stays a ghost (not a false link)", () => {
    // Only "linking notes" is resolvable; "Nonexistent Topic" must remain a ghost —
    // proves resolution is real, not a blanket "everything becomes a link".
    const resolve = new Map<string, number>([["linking notes", 2]]);
    render(<WikiMarkdown content={"[[Linking Notes]] and [[Nonexistent Topic]]"} resolve={resolve} />);
    expect(screen.getByText("Linking Notes").closest("a")).toHaveAttribute("href", "/wiki/2");
    const ghost = screen.getByText("Nonexistent Topic");
    expect(ghost.closest("a")).toBeNull();
    expect(ghost).toHaveAttribute("data-wikilink-ghost");
  });

  it("no resolve map → [[Title]] stays a ghost (back-compat default)", () => {
    render(<WikiMarkdown content={"a [[Some Note]] ref"} />);
    expect(screen.getByText("Some Note").closest("a")).toBeNull();
    expect(screen.getByText("Some Note")).toHaveAttribute("data-wikilink-ghost");
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
