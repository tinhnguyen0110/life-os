/**
 * FE-1 extended — module-catalog lib unit tests.
 * Covers: buildCatalog derives from NAV (auto-discovery, new module folds in),
 * pinned modules, toggle/move/reset, isModuleEnabled default-ON, applyModulePrefs
 * (drop disabled groups + reorder), hiddenRoutesFromModules, normalize/load/save.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  STORAGE_KEY,
  PINNED_MODULES,
  DEFAULT_MODULE_PREFS,
  buildCatalog,
  normalizeModulePrefs,
  loadModulePrefs,
  saveModulePrefs,
  isModuleEnabled,
  hiddenRoutesFromModules,
  orderCatalog,
  toggleModule,
  moveModule,
  resetModulePrefs,
  applyModulePrefs,
  type ModulePrefs,
} from "@/lib/module-catalog";
import { NAV, type NavGroup } from "@/lib/nav";

// Synthetic NAV so assertions don't break when the real NAV evolves. Includes a
// pinned core ("Tổng quan") + two feature modules.
const TEST_NAV: NavGroup[] = [
  { sec: "Tổng quan", items: [{ route: "/", label: "Home", icon: "i-home", screen: "S1" }] },
  {
    sec: "Tài chính",
    items: [
      { route: "/finance", label: "Tài chính", icon: "i-fin", screen: "S5" },
      { route: "/market", label: "Thị trường", icon: "i-mkt", screen: "S8" },
    ],
  },
  { sec: "Tri thức", items: [{ route: "/wiki", label: "Wiki", icon: "i-home", screen: "W1" }] },
];

describe("module-catalog — buildCatalog (auto-discovery from NAV)", () => {
  it("one catalog entry per NAV group, in NAV order", () => {
    const cat = buildCatalog(TEST_NAV);
    expect(cat.map((m) => m.key)).toEqual(["Tổng quan", "Tài chính", "Tri thức"]);
  });
  it("entry carries label, icon (first item's), routes, count", () => {
    const fin = buildCatalog(TEST_NAV).find((m) => m.key === "Tài chính")!;
    expect(fin.label).toBe("Tài chính");
    expect(fin.icon).toBe("i-fin");
    expect(fin.routes).toEqual(["/finance", "/market"]);
    expect(fin.count).toBe(2);
  });
  it("AUTO-DISCOVERY: a new NAV group appears as a new catalog module (no edit needed)", () => {
    const withNew: NavGroup[] = [...TEST_NAV, { sec: "Sự nghiệp", items: [{ route: "/career", label: "Career", icon: "i-doc", screen: "C1" }] }];
    const cat = buildCatalog(withNew);
    expect(cat.map((m) => m.key)).toContain("Sự nghiệp");
    const career = cat.find((m) => m.key === "Sự nghiệp")!;
    expect(career.routes).toEqual(["/career"]);
    expect(career.pinned).toBe(false); // new feature modules default to togglable
  });
  it("AUTO-DISCOVERY: a new ITEM in an existing group folds into that module", () => {
    const expanded: NavGroup[] = [
      TEST_NAV[0],
      { sec: "Tài chính", items: [...TEST_NAV[1].items, { route: "/portfolio", label: "Danh mục", icon: "i-pie", screen: "S6" }] },
      TEST_NAV[2],
    ];
    const fin = buildCatalog(expanded).find((m) => m.key === "Tài chính")!;
    expect(fin.routes).toEqual(["/finance", "/market", "/portfolio"]);
    expect(fin.count).toBe(3);
  });
  it("marks pinned modules (Tổng quan / Cấu hình)", () => {
    const cat = buildCatalog(TEST_NAV);
    expect(cat.find((m) => m.key === "Tổng quan")!.pinned).toBe(true);
    expect(cat.find((m) => m.key === "Tài chính")!.pinned).toBe(false);
  });
  it("defaults to the real NAV when no source given (every real group present)", () => {
    expect(buildCatalog().map((m) => m.key)).toEqual(NAV.map((g) => g.sec));
  });
});

describe("module-catalog — isModuleEnabled (default ON)", () => {
  it("a module not in disabled is enabled (preserves current UX)", () => {
    expect(isModuleEnabled({ disabled: [], order: [] }, "Tài chính")).toBe(true);
  });
  it("a disabled module is not enabled", () => {
    expect(isModuleEnabled({ disabled: ["Tài chính"], order: [] }, "Tài chính")).toBe(false);
  });
  it("a pinned module is ALWAYS enabled even if listed in disabled", () => {
    expect(isModuleEnabled({ disabled: ["Tổng quan"], order: [] }, "Tổng quan")).toBe(true);
  });
});

describe("module-catalog — applyModulePrefs (filter + reorder groups)", () => {
  it("default → NAV unchanged", () => {
    const out = applyModulePrefs(DEFAULT_MODULE_PREFS, TEST_NAV);
    expect(out.map((g) => g.sec)).toEqual(["Tổng quan", "Tài chính", "Tri thức"]);
  });
  it("disabling a module drops its whole group from the nav", () => {
    const out = applyModulePrefs({ disabled: ["Tài chính"], order: [] }, TEST_NAV);
    expect(out.map((g) => g.sec)).toEqual(["Tổng quan", "Tri thức"]);
  });
  it("reorders modules per order", () => {
    const out = applyModulePrefs({ disabled: [], order: ["Tri thức", "Tổng quan", "Tài chính"] }, TEST_NAV);
    expect(out.map((g) => g.sec)).toEqual(["Tri thức", "Tổng quan", "Tài chính"]);
  });
  it("TEETH — divergent order is not a no-op", () => {
    const def = applyModulePrefs(DEFAULT_MODULE_PREFS, TEST_NAV).map((g) => g.sec);
    const moved = applyModulePrefs({ disabled: [], order: ["Tri thức", "Tài chính", "Tổng quan"] }, TEST_NAV).map((g) => g.sec);
    expect(moved).not.toEqual(def);
    expect(moved[0]).toBe("Tri thức");
  });
  it("a pinned module can NOT be dropped even if disabled lists it", () => {
    const out = applyModulePrefs({ disabled: ["Tổng quan"], order: [] }, TEST_NAV);
    expect(out.map((g) => g.sec)).toContain("Tổng quan");
  });
});

describe("module-catalog — hiddenRoutesFromModules", () => {
  it("returns all routes of disabled modules", () => {
    const hidden = hiddenRoutesFromModules({ disabled: ["Tài chính"], order: [] }, TEST_NAV);
    expect(hidden.has("/finance")).toBe(true);
    expect(hidden.has("/market")).toBe(true);
    expect(hidden.has("/wiki")).toBe(false);
  });
  it("empty when nothing disabled", () => {
    expect(hiddenRoutesFromModules({ disabled: [], order: [] }, TEST_NAV).size).toBe(0);
  });
});

describe("module-catalog — orderCatalog", () => {
  it("forward-compat: a module absent from order is appended", () => {
    const cat = buildCatalog(TEST_NAV);
    const out = orderCatalog(cat, ["Tài chính"]); // only 1 of 3
    expect(out.map((m) => m.key)).toEqual(["Tài chính", "Tổng quan", "Tri thức"]);
  });
  it("stale key in order is ignored", () => {
    const cat = buildCatalog(TEST_NAV);
    const out = orderCatalog(cat, ["Gone", "Tri thức", "Tổng quan", "Tài chính"]);
    expect(out.map((m) => m.key)).toEqual(["Tri thức", "Tổng quan", "Tài chính"]);
  });
});

describe("module-catalog — toggleModule / moveModule / reset", () => {
  it("toggle disables an enabled module", () => {
    expect(toggleModule({ disabled: [], order: [] }, "Tài chính").disabled).toContain("Tài chính");
  });
  it("toggle re-enables a disabled module", () => {
    expect(toggleModule({ disabled: ["Tài chính"], order: [] }, "Tài chính").disabled).not.toContain("Tài chính");
  });
  it("toggle is a no-op for a pinned module", () => {
    const prefs: ModulePrefs = { disabled: [], order: [] };
    expect(toggleModule(prefs, "Tổng quan")).toBe(prefs);
  });
  it("move down swaps with next (from default order)", () => {
    const r = moveModule({ disabled: [], order: [] }, "Tổng quan", "down", TEST_NAV);
    expect(r.order).toEqual(["Tài chính", "Tổng quan", "Tri thức"]);
  });
  it("move up swaps with prev", () => {
    const r = moveModule({ disabled: [], order: [] }, "Tri thức", "up", TEST_NAV);
    expect(r.order).toEqual(["Tổng quan", "Tri thức", "Tài chính"]);
  });
  it("no-op moving first up / last down", () => {
    const prefs: ModulePrefs = { disabled: [], order: [] };
    expect(moveModule(prefs, "Tổng quan", "up", TEST_NAV)).toBe(prefs);
    expect(moveModule(prefs, "Tri thức", "down", TEST_NAV)).toBe(prefs);
  });
  it("reset → default", () => {
    expect(resetModulePrefs()).toEqual({ disabled: [], order: [] });
  });
});

describe("module-catalog — normalize / load / save", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it("PINNED_MODULES includes the core sections", () => {
    expect(PINNED_MODULES).toContain("Tổng quan");
    expect(PINNED_MODULES).toContain("Cấu hình");
  });
  it("normalize strips pinned + non-strings from disabled and de-dupes", () => {
    const r = normalizeModulePrefs({ disabled: ["Tổng quan", "Tài chính", "Tài chính", 3], order: ["x", 9] });
    expect(r.disabled).toEqual(["Tài chính"]);
    expect(r.order).toEqual(["x"]);
  });
  it("non-object → default", () => {
    expect(normalizeModulePrefs(null)).toEqual({ disabled: [], order: [] });
  });
  it("load returns default when empty", () => {
    expect(loadModulePrefs()).toEqual(DEFAULT_MODULE_PREFS);
  });
  it("save → load round-trip (survives reload sim)", () => {
    const p: ModulePrefs = { disabled: ["Tài chính"], order: ["Tri thức", "Tổng quan"] };
    saveModulePrefs(p);
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(p);
    expect(loadModulePrefs()).toEqual(p);
  });
  it("load returns default on malformed JSON", () => {
    localStorage.setItem(STORAGE_KEY, "}{bad");
    expect(loadModulePrefs()).toEqual(DEFAULT_MODULE_PREFS);
  });
});
