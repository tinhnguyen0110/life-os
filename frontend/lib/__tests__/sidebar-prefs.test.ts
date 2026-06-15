/**
 * FE-1 — sidebar-prefs lib unit tests.
 * Covers: applyPrefs (filter hidden + reorder + drop empty sections + pinned-never-hidden),
 * toggleHidden, moveItem (incl. boundaries + first-move-from-default), reset,
 * normalize/load/save localStorage round-trip + forward-compat for new routes.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  DEFAULT_PREFS,
  PINNED_ROUTES,
  STORAGE_KEY,
  normalizePrefs,
  loadPrefs,
  savePrefs,
  applyPrefs,
  toggleHidden,
  moveItem,
  resetPrefs,
  type SidebarPrefs,
} from "@/lib/sidebar-prefs";
import { NAV, type NavGroup } from "@/lib/nav";

// A small synthetic NAV so tests don't break when the real NAV changes order.
const TEST_NAV: NavGroup[] = [
  { sec: "Tổng quan", items: [{ route: "/", label: "Home", icon: "i-home", screen: "S1" }] },
  {
    sec: "Tài chính",
    items: [
      { route: "/finance", label: "Tài chính", icon: "i-fin", screen: "S5" },
      { route: "/portfolio", label: "Danh mục", icon: "i-pie", screen: "S6" },
      { route: "/market", label: "Thị trường", icon: "i-mkt", screen: "S8" },
    ],
  },
];

describe("sidebar-prefs — constants", () => {
  it("DEFAULT_PREFS is empty (nothing hidden, no custom order)", () => {
    expect(DEFAULT_PREFS).toEqual({ hidden: [], order: {} });
  });
  it("Home '/' is pinned", () => {
    expect(PINNED_ROUTES).toContain("/");
  });
});

describe("normalizePrefs", () => {
  it("returns default for non-object", () => {
    expect(normalizePrefs(null)).toEqual({ hidden: [], order: {} });
    expect(normalizePrefs("x")).toEqual({ hidden: [], order: {} });
    expect(normalizePrefs(42)).toEqual({ hidden: [], order: {} });
  });
  it("filters non-string hidden entries and de-dupes", () => {
    const r = normalizePrefs({ hidden: ["/market", "/market", 5, null, "/notes"], order: {} });
    expect(r.hidden.sort()).toEqual(["/market", "/notes"]);
  });
  it("strips pinned routes from hidden (Home can never be hidden)", () => {
    const r = normalizePrefs({ hidden: ["/", "/market"] });
    expect(r.hidden).toEqual(["/market"]);
  });
  it("keeps only array order entries with string members", () => {
    const r = normalizePrefs({ order: { "Tài chính": ["/market", 3, "/finance"], bad: "x" } });
    expect(r.order).toEqual({ "Tài chính": ["/market", "/finance"] });
  });
});

describe("applyPrefs — filter + reorder", () => {
  it("default prefs → NAV unchanged (same groups, same items, same order)", () => {
    const out = applyPrefs(DEFAULT_PREFS, TEST_NAV);
    expect(out.map((g) => g.sec)).toEqual(["Tổng quan", "Tài chính"]);
    expect(out[1].items.map((i) => i.route)).toEqual(["/finance", "/portfolio", "/market"]);
  });

  it("hides a route", () => {
    const out = applyPrefs({ hidden: ["/portfolio"], order: {} }, TEST_NAV);
    expect(out[1].items.map((i) => i.route)).toEqual(["/finance", "/market"]);
  });

  it("drops a section when all its items are hidden", () => {
    const out = applyPrefs({ hidden: ["/finance", "/portfolio", "/market"], order: {} }, TEST_NAV);
    expect(out.map((g) => g.sec)).toEqual(["Tổng quan"]); // finance section gone
  });

  it("NEVER hides a pinned route even if present in hidden", () => {
    const out = applyPrefs({ hidden: ["/"], order: {} }, TEST_NAV);
    expect(out[0].items.map((i) => i.route)).toEqual(["/"]); // Home survives
  });

  it("reorders within a section per order[sec]", () => {
    const out = applyPrefs({ hidden: [], order: { "Tài chính": ["/market", "/finance", "/portfolio"] } }, TEST_NAV);
    expect(out[1].items.map((i) => i.route)).toEqual(["/market", "/finance", "/portfolio"]);
  });

  it("TEETH — divergent reorder is not a no-op (market moves to front)", () => {
    const def = applyPrefs(DEFAULT_PREFS, TEST_NAV)[1].items.map((i) => i.route);
    const moved = applyPrefs({ hidden: [], order: { "Tài chính": ["/market", "/finance", "/portfolio"] } }, TEST_NAV)[1].items.map((i) => i.route);
    expect(moved).not.toEqual(def);
    expect(moved[0]).toBe("/market");
  });

  it("forward-compat: a NAV route absent from order is appended (new module not dropped)", () => {
    // order lists only 2 of 3 — /portfolio (the new one) must still appear, at the end
    const out = applyPrefs({ hidden: [], order: { "Tài chính": ["/market", "/finance"] } }, TEST_NAV);
    expect(out[1].items.map((i) => i.route)).toEqual(["/market", "/finance", "/portfolio"]);
  });

  it("stale route in order (no longer in NAV) is ignored", () => {
    const out = applyPrefs({ hidden: [], order: { "Tài chính": ["/gone", "/market", "/finance", "/portfolio"] } }, TEST_NAV);
    expect(out[1].items.map((i) => i.route)).toEqual(["/market", "/finance", "/portfolio"]);
  });

  it("defaults source to the real NAV when omitted", () => {
    const out = applyPrefs(DEFAULT_PREFS);
    expect(out.map((g) => g.sec)).toEqual(NAV.map((g) => g.sec));
  });
});

describe("toggleHidden", () => {
  it("adds a route to hidden", () => {
    const r = toggleHidden({ hidden: [], order: {} }, "/market");
    expect(r.hidden).toContain("/market");
  });
  it("removes a route already hidden (toggle off)", () => {
    const r = toggleHidden({ hidden: ["/market"], order: {} }, "/market");
    expect(r.hidden).not.toContain("/market");
  });
  it("is a no-op for a pinned route", () => {
    const prefs: SidebarPrefs = { hidden: [], order: {} };
    const r = toggleHidden(prefs, "/");
    expect(r).toBe(prefs); // same ref → no change
  });
});

describe("moveItem", () => {
  it("moves a route down (swaps with next) — works from DEFAULT order", () => {
    const r = moveItem({ hidden: [], order: {} }, "Tài chính", "/finance", "down", TEST_NAV);
    expect(r.order["Tài chính"]).toEqual(["/portfolio", "/finance", "/market"]);
  });
  it("moves a route up (swaps with prev)", () => {
    const r = moveItem({ hidden: [], order: {} }, "Tài chính", "/market", "up", TEST_NAV);
    expect(r.order["Tài chính"]).toEqual(["/finance", "/market", "/portfolio"]);
  });
  it("no-op moving the first item up (boundary)", () => {
    const prefs: SidebarPrefs = { hidden: [], order: {} };
    const r = moveItem(prefs, "Tài chính", "/finance", "up", TEST_NAV);
    expect(r).toBe(prefs);
  });
  it("no-op moving the last item down (boundary)", () => {
    const prefs: SidebarPrefs = { hidden: [], order: {} };
    const r = moveItem(prefs, "Tài chính", "/market", "down", TEST_NAV);
    expect(r).toBe(prefs);
  });
  it("no-op for an unknown section", () => {
    const prefs: SidebarPrefs = { hidden: [], order: {} };
    expect(moveItem(prefs, "Nope", "/market", "up", TEST_NAV)).toBe(prefs);
  });
  it("no-op for an unknown route", () => {
    const prefs: SidebarPrefs = { hidden: [], order: {} };
    expect(moveItem(prefs, "Tài chính", "/ghost", "up", TEST_NAV)).toBe(prefs);
  });
  it("two moves compound (down then down again)", () => {
    let r = moveItem({ hidden: [], order: {} }, "Tài chính", "/finance", "down", TEST_NAV);
    r = moveItem(r, "Tài chính", "/finance", "down", TEST_NAV);
    expect(r.order["Tài chính"]).toEqual(["/portfolio", "/market", "/finance"]);
  });
});

describe("resetPrefs", () => {
  it("returns the empty default", () => {
    expect(resetPrefs()).toEqual({ hidden: [], order: {} });
  });
});

describe("loadPrefs / savePrefs — localStorage round-trip", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it("loadPrefs() returns DEFAULT_PREFS when empty", () => {
    expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  });
  it("savePrefs writes to localStorage[lifeos.sidebar]", () => {
    const p: SidebarPrefs = { hidden: ["/market"], order: { "Tài chính": ["/market", "/finance"] } };
    savePrefs(p);
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(p);
  });
  it("survives a reload sim (save → load round-trip)", () => {
    const p: SidebarPrefs = { hidden: ["/notes"], order: {} };
    savePrefs(p);
    expect(loadPrefs()).toEqual(p);
  });
  it("loadPrefs() returns default on malformed JSON", () => {
    localStorage.setItem(STORAGE_KEY, "{{not-json");
    expect(loadPrefs()).toEqual(DEFAULT_PREFS);
  });
  it("loadPrefs() normalizes a stored value (strips pinned + non-strings)", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ hidden: ["/", "/market", 9], order: { x: "bad" } }));
    const r = loadPrefs();
    expect(r.hidden).toEqual(["/market"]);
    expect(r.order).toEqual({});
  });
});
