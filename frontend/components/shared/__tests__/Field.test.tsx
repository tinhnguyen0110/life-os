import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Field, TextInput, NumberInput, Select, Toggle } from "../Field";

afterEach(() => { vi.clearAllMocks(); });

describe("Field — label + per-field error echo", () => {
  it("renders label + child; hint shows when no error", () => {
    render(<Field label="Tên" hint="ghi chú" testId="f"><input /></Field>);
    expect(screen.getByText("Tên")).toBeInTheDocument();
    expect(screen.getByText("ghi chú")).toBeInTheDocument();
  });

  it("error → red border class + inline message (hint suppressed)", () => {
    render(<Field label="Giờ" error="phải ≤ 23" hint="0-23" testId="f"><input /></Field>);
    expect(screen.getByTestId("f")).toHaveClass("has-err");
    expect(screen.getByTestId("f-error")).toHaveTextContent("phải ≤ 23");
    expect(screen.queryByText("0-23")).toBeNull(); // hint hidden when error present
  });
});

describe("TextInput — controlled", () => {
  it("calls onChange per keystroke (controlled — parent owns value)", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    // value is FIXED "" here (controlled, parent doesn't re-feed) → each keystroke
    // fires onChange with that single char. Proves the input is controlled, not internal-state.
    render(<TextInput value="" onChange={onChange} testId="t" />);
    await user.type(screen.getByTestId("t"), "hi");
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenNthCalledWith(1, "h");
    expect(onChange).toHaveBeenLastCalledWith("i");
  });

  it("reflects the value prop verbatim (controlled)", () => {
    render(<TextInput value="Tinh" onChange={() => {}} testId="t" />);
    expect((screen.getByTestId("t") as HTMLInputElement).value).toBe("Tinh");
  });

  it("respects maxLength", () => {
    render(<TextInput value="x" onChange={() => {}} maxLength={80} testId="t" />);
    expect(screen.getByTestId("t")).toHaveAttribute("maxLength", "80");
  });
});

describe("NumberInput — controlled, blank-safe", () => {
  it("emits a number for numeric input", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<NumberInput value={""} onChange={onChange} testId="n" />);
    await user.type(screen.getByTestId("n"), "9");
    expect(onChange).toHaveBeenLastCalledWith(9);
  });

  it("emits '' (not 0) when cleared — don't coerce blank to zero", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<NumberInput value={7} onChange={onChange} testId="n" />);
    await user.clear(screen.getByTestId("n"));
    expect(onChange).toHaveBeenLastCalledWith("");
  });
});

describe("Select — controlled", () => {
  it("calls onChange with selected value", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Select value="inapp" onChange={onChange} options={[{ value: "inapp", label: "In-app" }, { value: "none", label: "Tắt" }]} testId="s" />);
    await user.selectOptions(screen.getByTestId("s"), "none");
    expect(onChange).toHaveBeenCalledWith("none");
  });
});

describe("Toggle — accessible switch", () => {
  it("role=switch + aria-checked reflects state; click flips", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Toggle on={false} onChange={onChange} label="Master" testId="tg" />);
    const t = screen.getByTestId("tg");
    expect(t).toHaveAttribute("role", "switch");
    expect(t).toHaveAttribute("aria-checked", "false");
    await user.click(t);
    expect(onChange).toHaveBeenCalledWith(true); // flips to opposite
  });

  it("disabled → no flip", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<Toggle on={true} onChange={onChange} disabled testId="tg" />);
    await user.click(screen.getByTestId("tg"));
    expect(onChange).not.toHaveBeenCalled();
  });
});
