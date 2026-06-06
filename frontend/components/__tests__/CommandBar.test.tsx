import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { parseCommand, CommandBar } from "../CommandBar";

const push = vi.fn();
vi.mock("@/lib/useNav", () => ({
  useSafeRouter: () => ({ push }),
  useSafePathname: () => "/",
}));

describe("parseCommand", () => {
  it("routes `open <project>` to /projects", () => {
    const r = parseCommand("open mcp-wrapper");
    expect(r.ok).toBe(true);
    expect(r.route).toBe("/projects");
  });

  it("routes `dca ...` to /journal", () => {
    expect(parseCommand("dca btc 2000").route).toBe("/journal");
  });

  it("routes `run <routine>` to /activity", () => {
    expect(parseCommand("run morning-brief").route).toBe("/activity");
  });

  it("routes `note ...` to /notes", () => {
    expect(parseCommand("note idea").route).toBe("/notes");
  });

  it("empty input → no message, not ok", () => {
    const r = parseCommand("   ");
    expect(r.ok).toBe(false);
    expect(r.message).toBe("");
  });

  it("unknown command → hint, no route", () => {
    const r = parseCommand("frobnicate");
    expect(r.ok).toBe(false);
    expect(r.route).toBeUndefined();
    expect(r.message).toMatch(/chưa rõ/);
  });

  it("`open` with no id is not actionable", () => {
    const r = parseCommand("open ");
    expect(r.route).toBeUndefined();
  });
});

describe("CommandBar component", () => {
  it("renders the `>` prefix and ⌘K hint", () => {
    render(<CommandBar />);
    expect(screen.getByText(">")).toBeInTheDocument();
    expect(screen.getByText("⌘K")).toBeInTheDocument();
    expect(screen.getByLabelText("Command bar")).toBeInTheDocument();
  });

  it("Enter on a known command navigates", async () => {
    push.mockClear();
    const user = userEvent.setup();
    render(<CommandBar />);
    const input = screen.getByLabelText("Command bar");
    await user.type(input, "dca btc 2000{Enter}");
    expect(push).toHaveBeenCalledWith("/journal");
  });

  it("Enter on unknown command shows hint, no navigation", async () => {
    push.mockClear();
    const user = userEvent.setup();
    render(<CommandBar />);
    const input = screen.getByLabelText("Command bar");
    await user.type(input, "xyz{Enter}");
    expect(screen.getByTestId("cmd-hint")).toHaveTextContent(/chưa rõ/);
    expect(push).not.toHaveBeenCalled();
  });
});
