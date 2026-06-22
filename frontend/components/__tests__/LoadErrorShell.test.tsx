/* ============================================================
   LoadErrorShell — unit tests for the shared loading/error gate (#138-P1a).
   New coverage (the finance migration adds 0 behavior-test delta — finance's
   existing tests cover it; these test the EXTRACTED component directly).
   ============================================================ */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LoadErrorShell } from "@/components/LoadErrorShell";

describe("LoadErrorShell — the shared loading/error gate", () => {
  const body = <div data-testid="body">the real screen body</div>;

  it("status=loading → renders the loading label (with its testid), NOT the body", () => {
    render(
      <LoadErrorShell status="loading" loadingLabel="Đang tải…" errorLabel="x"
        loadingTestid="x-loading" errorTestid="x-error">{body}</LoadErrorShell>
    );
    expect(screen.getByTestId("x-loading")).toHaveTextContent("Đang tải…");
    expect(screen.queryByTestId("body")).toBeNull();
  });

  it("status=error → renders the error label + a reload button (when reload given), NOT the body", () => {
    const reload = vi.fn();
    render(
      <LoadErrorShell status="error" loadingLabel="x" errorLabel="Không tải được."
        loadingTestid="x-loading" errorTestid="x-error" reload={reload}>{body}</LoadErrorShell>
    );
    const err = screen.getByTestId("x-error");
    expect(err).toHaveTextContent("Không tải được.");
    expect(err.className).toContain("neg");
    expect(screen.queryByTestId("body")).toBeNull();
    // the reload button defaults to "Thử lại" and calls reload on click
    const btn = screen.getByRole("button", { name: "Thử lại" });
    fireEvent.click(btn);
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("status=error WITHOUT reload → no reload button", () => {
    render(
      <LoadErrorShell status="error" loadingLabel="x" errorLabel="oops"
        errorTestid="x-error">{body}</LoadErrorShell>
    );
    expect(screen.getByTestId("x-error")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("a custom reloadLabel overrides the default", () => {
    render(
      <LoadErrorShell status="error" loadingLabel="x" errorLabel="oops"
        errorTestid="x-error" reload={() => {}} reloadLabel="Tải lại">{body}</LoadErrorShell>
    );
    expect(screen.getByRole("button", { name: "Tải lại" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Thử lại" })).toBeNull();
  });

  it("status=ready (anything non-loading/error) → renders the body, no loading/error nodes", () => {
    render(
      <LoadErrorShell status="ready" loadingLabel="x" errorLabel="y"
        loadingTestid="x-loading" errorTestid="x-error">{body}</LoadErrorShell>
    );
    expect(screen.getByTestId("body")).toBeInTheDocument();
    expect(screen.queryByTestId("x-loading")).toBeNull();
    expect(screen.queryByTestId("x-error")).toBeNull();
  });

  it("section props → wraps the loading/error state in a <section class data-screen>", () => {
    const { container } = render(
      <LoadErrorShell status="loading" loadingLabel="Đang tải…" errorLabel="x"
        loadingTestid="x-loading" errorTestid="x-error"
        sectionClassName="view" dataScreen="S5">{body}</LoadErrorShell>
    );
    const section = container.querySelector("section.view");
    expect(section).toBeTruthy();
    expect(section?.getAttribute("data-screen")).toBe("S5");
    expect(section?.querySelector('[data-testid="x-loading"]')).toBeTruthy();
  });

  it("error label can be a NODE that interpolates values (byte-identical screen copy)", () => {
    render(
      <LoadErrorShell status="error" loadingLabel="x"
        errorLabel={<>Không tải được: {"Network error"}. Kiểm tra backend ({"http://be"}).</>}
        errorTestid="x-error" reload={() => {}}>{body}</LoadErrorShell>
    );
    const err = screen.getByTestId("x-error");
    expect(err.textContent).toContain("Không tải được: Network error. Kiểm tra backend (http://be).");
  });

  it("padding defaults to '24px 4px' (existing call-sites unchanged)", () => {
    render(
      <LoadErrorShell status="loading" loadingLabel="Đang tải…" errorLabel="x"
        loadingTestid="x-loading" errorTestid="x-error">{body}</LoadErrorShell>
    );
    expect((screen.getByTestId("x-loading") as HTMLElement).style.padding).toBe("24px 4px");
  });

  it("a custom padding prop overrides the default on both loading + error nodes", () => {
    const { rerender } = render(
      <LoadErrorShell status="loading" loadingLabel="Đang tải…" errorLabel="oops"
        loadingTestid="x-loading" errorTestid="x-error" padding="18px 16px">{body}</LoadErrorShell>
    );
    expect((screen.getByTestId("x-loading") as HTMLElement).style.padding).toBe("18px 16px");
    rerender(
      <LoadErrorShell status="error" loadingLabel="Đang tải…" errorLabel="oops"
        loadingTestid="x-loading" errorTestid="x-error" padding="18px 16px">{body}</LoadErrorShell>
    );
    expect((screen.getByTestId("x-error") as HTMLElement).style.padding).toBe("18px 16px");
  });
});
