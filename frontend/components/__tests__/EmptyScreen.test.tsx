import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyScreen } from "../EmptyScreen";

describe("EmptyScreen", () => {
  it("renders the screen name, id tag and icon", () => {
    render(<EmptyScreen name="Tài chính" screen="S5" icon="i-fin" />);
    expect(screen.getByRole("heading", { name: "Tài chính" })).toBeInTheDocument();
    expect(screen.getByText("S5")).toBeInTheDocument();
    const root = screen.getByTestId("empty-screen");
    expect(root.getAttribute("data-screen")).toBe("S5");
    expect(root.querySelector("svg")).toBeTruthy();
  });
});
