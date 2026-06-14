import { describe, it, expect } from "vitest";
import { NAV, CRUMB, ALL_ROUTES } from "../nav";

describe("nav config (D3 — 14 foundation screens + Wiki, 7 groups, no AI)", () => {
  it("has exactly 7 groups in SPEC §1 order (+ Tri thức for Wiki)", () => {
    expect(NAV.map((g) => g.sec)).toEqual([
      "Tổng quan",
      "Dự án",
      "Tài chính",
      "Hằng ngày",
      "Tri thức",
      "Hệ thống",
      "Cấu hình",
    ]);
  });

  it("covers all 14 foundation screens S1–S14 + OKX Exchange + Wiki across nav items", () => {
    const screens = NAV.flatMap((g) => g.items.map((i) => i.screen));
    const unique = new Set(screens);
    // 14 foundation entries (S1..S14 minus S3 detail, PLUS S-okx) + W3 Wiki Inbox.
    // (S3/S6 + /wiki/[id] detail views resolve under their parents.)
    expect(screens).toContain("S1");
    expect(screens).toContain("S14");
    expect(screens).toContain("S-okx");
    expect(screens).toContain("W3");
    expect(unique.size).toBe(15);
  });

  it("every nav route has a breadcrumb entry", () => {
    for (const route of ALL_ROUTES) {
      expect(CRUMB[route]).toBeTruthy();
    }
  });

  it("contains NO ai route (ARCH §11)", () => {
    expect(ALL_ROUTES).not.toContain("/ai");
    expect(CRUMB["/ai"]).toBeUndefined();
  });

  it("routes are unique", () => {
    expect(new Set(ALL_ROUTES).size).toBe(ALL_ROUTES.length);
  });

  // ---------------------------------------------------------------------------
  // Sprint 0A — label-uniqueness regression guard.
  // The Sidebar renders BOTH group headers (`sec`) and item labels as visible
  // text. If an item label equals a group header, RTL `getByText(label)` resolves
  // to 2 nodes and throws "multiple elements". This bit the Finance "Tổng quan"
  // item vs the "Tổng quan" section header. These guards keep that provably red.
  // ---------------------------------------------------------------------------
  it("no nav-item label collides with any group section header (getByText-safe)", () => {
    const secs = new Set(NAV.map((g) => g.sec));
    const collisions = NAV.flatMap((g) => g.items)
      .map((i) => i.label)
      .filter((label) => secs.has(label));
    expect(collisions).toEqual([]);
  });

  it("all nav-item labels are mutually unique (no two items share a label)", () => {
    const labels = NAV.flatMap((g) => g.items).map((i) => i.label);
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("Finance overview item is the unique 'Tổng quan tài chính' label, not the bare section header", () => {
    const finance = NAV.flatMap((g) => g.items).find((i) => i.route === "/finance");
    expect(finance?.label).toBe("Tổng quan tài chính");
    expect(finance?.label).not.toBe("Tổng quan");
  });
});
