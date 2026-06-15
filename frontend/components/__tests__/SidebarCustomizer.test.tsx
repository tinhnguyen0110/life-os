import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarCustomizer } from "../SidebarCustomizer";
import { NAV } from "@/lib/nav";
import { loadPrefs, STORAGE_KEY } from "@/lib/sidebar-prefs";

// next/link not used here, but icons render fine in jsdom.
describe("SidebarCustomizer", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => { cleanup(); localStorage.clear(); });

  it("does not render when closed", () => {
    render(<SidebarCustomizer open={false} onClose={() => {}} />);
    expect(screen.queryByTestId("sbcust-panel")).toBeNull();
  });

  it("renders every nav item (including a row per route) when open", () => {
    render(<SidebarCustomizer open onClose={() => {}} />);
    for (const g of NAV) {
      for (const item of g.items) {
        expect(screen.getByTestId(`sbc-row-${item.route}`)).toBeTruthy();
      }
    }
  });

  it("Home '/' shows a locked 'cố định' marker, NOT a toggle", () => {
    render(<SidebarCustomizer open onClose={() => {}} />);
    expect(screen.getByTestId("sbc-pin-/")).toBeTruthy();
    expect(screen.queryByTestId("sbc-toggle-/")).toBeNull();
  });

  it("toggling a module off persists hidden to localStorage", async () => {
    const user = userEvent.setup();
    render(<SidebarCustomizer open onClose={() => {}} />);
    // /market is visible by default → its toggle is ON
    const toggle = screen.getByTestId("sbc-toggle-/market");
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    await user.click(toggle);
    // now hidden → persisted
    expect(loadPrefs().hidden).toContain("/market");
    // row reflects hidden state
    expect(screen.getByTestId("sbc-row-/market").getAttribute("data-hidden")).toBe("1");
  });

  it("toggle is keyboard-accessible (Enter hides)", async () => {
    const user = userEvent.setup();
    render(<SidebarCustomizer open onClose={() => {}} />);
    const toggle = screen.getByTestId("sbc-toggle-/notes");
    toggle.focus();
    await user.keyboard("{Enter}");
    expect(loadPrefs().hidden).toContain("/notes");
  });

  it("reorder down then re-enable: persists order, item moves within section", async () => {
    const user = userEvent.setup();
    render(<SidebarCustomizer open onClose={() => {}} />);
    // Find a section with >=2 items to reorder — Tài chính (finance/portfolio/exchange/journal/market)
    const finGroup = NAV.find((g) => g.sec === "Tài chính")!;
    const first = finGroup.items[0].route;  // /finance
    const second = finGroup.items[1].route; // /portfolio
    // move first down → it should now be after second in saved order
    await user.click(screen.getByTestId(`sbc-down-${first}`));
    const order = loadPrefs().order["Tài chính"];
    expect(order.indexOf(first)).toBeGreaterThan(order.indexOf(second));
  });

  it("up button is disabled for the first item in a section", () => {
    render(<SidebarCustomizer open onClose={() => {}} />);
    const finGroup = NAV.find((g) => g.sec === "Tài chính")!;
    const first = finGroup.items[0].route;
    expect((screen.getByTestId(`sbc-up-${first}`) as HTMLButtonElement).disabled).toBe(true);
  });

  it("down button is disabled for the last item in a section", () => {
    render(<SidebarCustomizer open onClose={() => {}} />);
    const finGroup = NAV.find((g) => g.sec === "Tài chính")!;
    const last = finGroup.items[finGroup.items.length - 1].route;
    expect((screen.getByTestId(`sbc-down-${last}`) as HTMLButtonElement).disabled).toBe(true);
  });

  it("Reset clears hidden + order from localStorage", async () => {
    const user = userEvent.setup();
    // pre-seed a customized state
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ hidden: ["/market"], order: { "Tài chính": ["/market"] } }));
    render(<SidebarCustomizer open onClose={() => {}} />);
    await user.click(screen.getByTestId("sbcust-reset"));
    expect(loadPrefs()).toEqual({ hidden: [], order: {} });
  });

  it("backdrop click closes (fires onClose)", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SidebarCustomizer open onClose={onClose} />);
    await user.click(screen.getByTestId("sbcust-backdrop"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Esc key closes (fires onClose)", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SidebarCustomizer open onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("close button fires onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<SidebarCustomizer open onClose={onClose} />);
    await user.click(screen.getByTestId("sbcust-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
