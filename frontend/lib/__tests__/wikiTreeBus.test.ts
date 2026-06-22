import { describe, it, expect, vi } from "vitest";
import { markWikiTreeStale, wikiTreeVersion, subscribeWikiTree } from "../wikiTreeBus";

/* #108 — the wiki-tree refresh bus. A tree-mutating write bumps the version + notifies
   subscribers so the Explorer (in another component) refetches its folder counts. */

describe("wikiTreeBus (#108)", () => {
  it("markWikiTreeStale bumps the version", () => {
    const before = wikiTreeVersion();
    markWikiTreeStale();
    expect(wikiTreeVersion()).toBe(before + 1);
  });

  it("notifies every subscriber on a bump", () => {
    const a = vi.fn(), b = vi.fn();
    const unsubA = subscribeWikiTree(a);
    const unsubB = subscribeWikiTree(b);
    markWikiTreeStale();
    expect(a).toHaveBeenCalledTimes(1);
    expect(b).toHaveBeenCalledTimes(1);
    unsubA(); unsubB();
  });

  it("unsubscribe stops further notifications", () => {
    const fn = vi.fn();
    const unsub = subscribeWikiTree(fn);
    markWikiTreeStale();
    expect(fn).toHaveBeenCalledTimes(1);
    unsub();
    markWikiTreeStale();
    expect(fn).toHaveBeenCalledTimes(1); // not called again
  });

  it("a throwing listener does NOT block the others (isolated)", () => {
    const bad = vi.fn(() => { throw new Error("boom"); });
    const good = vi.fn();
    const u1 = subscribeWikiTree(bad);
    const u2 = subscribeWikiTree(good);
    expect(() => markWikiTreeStale()).not.toThrow();
    expect(good).toHaveBeenCalledTimes(1);
    u1(); u2();
  });

  it("version is monotonic across bumps (a late subscriber can detect a missed bump)", () => {
    const v0 = wikiTreeVersion();
    markWikiTreeStale();
    markWikiTreeStale();
    expect(wikiTreeVersion()).toBe(v0 + 2);
  });
});
