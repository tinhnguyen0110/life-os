import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModulesPanel } from "../ModulesPanel";
import { NAV } from "@/lib/nav";
import { loadModulePrefs, STORAGE_KEY, PINNED_MODULES } from "@/lib/module-catalog";

describe("ModulesPanel (Settings → Modules registry)", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => { cleanup(); localStorage.clear(); });

  it("renders a row for every NAV group (catalog derived from NAV)", () => {
    render(<ModulesPanel />);
    for (const g of NAV) {
      expect(screen.getByTestId(`module-row-${g.sec}`)).toBeTruthy();
    }
  });

  it("pinned core modules show a 'lõi' marker, NOT a toggle", () => {
    render(<ModulesPanel />);
    for (const key of PINNED_MODULES) {
      if (NAV.some((g) => g.sec === key)) {
        expect(screen.getByTestId(`module-pin-${key}`)).toBeTruthy();
        expect(screen.queryByTestId(`module-toggle-${key}`)).toBeNull();
      }
    }
  });

  it("feature modules show an enabled toggle by default (default ON)", () => {
    render(<ModulesPanel />);
    const t = screen.getByTestId("module-toggle-Tài chính");
    expect(t.getAttribute("aria-checked")).toBe("true");
  });

  it("disabling a module persists to localStorage", async () => {
    const user = userEvent.setup();
    render(<ModulesPanel />);
    await user.click(screen.getByTestId("module-toggle-Tài chính"));
    expect(loadModulePrefs().disabled).toContain("Tài chính");
    expect(screen.getByTestId("module-row-Tài chính").getAttribute("data-enabled")).toBe("0");
  });

  it("toggle is keyboard accessible (Space disables)", async () => {
    const user = userEvent.setup();
    render(<ModulesPanel />);
    const t = screen.getByTestId("module-toggle-Tri thức");
    t.focus();
    await user.keyboard(" ");
    expect(loadModulePrefs().disabled).toContain("Tri thức");
  });

  it("reorder down persists the new module order", async () => {
    const user = userEvent.setup();
    render(<ModulesPanel />);
    // first feature group after the pinned 'Tổng quan'
    const second = NAV[1].sec;
    const third = NAV[2].sec;
    await user.click(screen.getByTestId(`module-down-${second}`));
    const order = loadModulePrefs().order;
    expect(order.indexOf(second)).toBeGreaterThan(order.indexOf(third));
  });

  it("up disabled for first, down disabled for last", () => {
    render(<ModulesPanel />);
    const first = NAV[0].sec;
    const last = NAV[NAV.length - 1].sec;
    expect((screen.getByTestId(`module-up-${first}`) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId(`module-down-${last}`) as HTMLButtonElement).disabled).toBe(true);
  });

  it("Reset clears disabled + order", async () => {
    const user = userEvent.setup();
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ disabled: ["Tài chính"], order: ["Tri thức"] }));
    render(<ModulesPanel />);
    await user.click(screen.getByTestId("modules-reset"));
    expect(loadModulePrefs()).toEqual({ disabled: [], order: [] });
  });

  it("header shows enabled/total count", () => {
    render(<ModulesPanel />);
    // all enabled by default → N/N
    expect(screen.getByText(new RegExp(`${NAV.length}/${NAV.length} bật`))).toBeTruthy();
  });
});
