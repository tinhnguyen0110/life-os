import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { relativeTime, idleDays, orDash, fmtUSD, fmtSign, fmtPct, deltaGlyph, slugifyVi } from "../format";

describe("relativeTime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-06T12:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("null/undefined → fallback dash", () => {
    expect(relativeTime(null)).toBe("—");
    expect(relativeTime(undefined)).toBe("—");
    expect(relativeTime(null, "n/a")).toBe("n/a");
  });

  it("invalid ISO → fallback", () => {
    expect(relativeTime("not-a-date")).toBe("—");
  });

  it("minutes / hours / days ago", () => {
    expect(relativeTime("2026-06-06T11:30:00Z")).toBe("30 phút trước");
    expect(relativeTime("2026-06-06T09:00:00Z")).toBe("3 giờ trước");
    expect(relativeTime("2026-06-03T12:00:00Z")).toBe("3 ngày trước");
  });

  it("future timestamp → 'vừa xong' (no negative)", () => {
    expect(relativeTime("2026-06-06T12:01:00Z")).toBe("vừa xong");
  });
});

describe("idleDays", () => {
  it("null → fallback", () => {
    expect(idleDays(null)).toBe("—");
    expect(idleDays(undefined)).toBe("—");
  });
  it("0 or negative → 'hôm nay'", () => {
    expect(idleDays(0)).toBe("hôm nay");
  });
  it("positive → 'N ngày'", () => {
    expect(idleDays(14)).toBe("14 ngày");
  });
});

describe("orDash", () => {
  it("null/empty → dash", () => {
    expect(orDash(null)).toBe("—");
    expect(orDash("")).toBe("—");
    expect(orDash(undefined)).toBe("—");
  });
  it("passes through a value", () => {
    expect(orDash("hello")).toBe("hello");
  });
  it("custom fallback", () => {
    expect(orDash(null, "chưa có")).toBe("chưa có");
  });
});

describe("fmtUSD", () => {
  it("plain thousands under 1M", () => {
    expect(fmtUSD(247850)).toBe("$247,850");
    expect(fmtUSD(0)).toBe("$0");
  });
  it("compact millions", () => {
    expect(fmtUSD(1_500_000)).toBe("$1.5M");
    expect(fmtUSD(2_480_000)).toBe("$2.48M");
  });
  it("negative", () => {
    expect(fmtUSD(-640)).toBe("-$640");
  });
  it("null/NaN → fallback", () => {
    expect(fmtUSD(null)).toBe("—");
    expect(fmtUSD(NaN)).toBe("—");
    expect(fmtUSD(undefined, "n/a")).toBe("n/a");
  });
});

describe("fmtSign", () => {
  it("positive gets +, negative gets true minus", () => {
    expect(fmtSign(3420)).toBe("+$3,420");
    expect(fmtSign(-640)).toBe("−$640");
  });
  it("millions compact with sign", () => {
    expect(fmtSign(11_200_000)).toBe("+$11.2M");
  });
  it("null/NaN → fallback", () => {
    expect(fmtSign(null)).toBe("—");
    expect(fmtSign(NaN)).toBe("—");
  });
});

describe("fmtPct", () => {
  it("signed percent to 1 decimal", () => {
    expect(fmtPct(1.4)).toBe("+1.4%");
    expect(fmtPct(-0.6)).toBe("−0.6%");
    expect(fmtPct(0)).toBe("+0.0%");
  });
  it("null/NaN → fallback", () => {
    expect(fmtPct(null)).toBe("—");
    expect(fmtPct(undefined, "—")).toBe("—");
  });
});

// ---------------------------------------------------------------------------
// #81 — deltaGlyph: the SINGLE 3-way honest delta rule shared by every delta
// widget (Home/Finance net-worth, EquityCurve, MarketChart). These are the
// DISTINGUISHING cases a 2-way `up ? pos : neg` gets WRONG — they are the teeth
// that go RED if any widget (or this helper) regresses to 2-way.
// ---------------------------------------------------------------------------
describe("deltaGlyph (3-way honest delta — #81)", () => {
  it("a real LOSS (< 0) → ▼ / neg (red-down)", () => {
    expect(deltaGlyph(-12.5)).toEqual({ arrow: "▼", cls: "neg" });
    expect(deltaGlyph(-0.01)).toEqual({ arrow: "▼", cls: "neg" });
  });

  it("a real GAIN (> 0) → ▲ / pos (green-up)", () => {
    expect(deltaGlyph(8.3)).toEqual({ arrow: "▲", cls: "pos" });
    expect(deltaGlyph(0.01)).toEqual({ arrow: "▲", cls: "pos" });
  });

  // THE teeth #1 — flat must NOT be a green gain.
  it("FLAT (=== 0) → ▬ / faint — NOT a green ▲ pos (the false-gain bug)", () => {
    const g = deltaGlyph(0);
    expect(g).toEqual({ arrow: "▬", cls: "faint" });
    expect(g.cls).not.toBe("pos"); // explicit: a flat 0.00% is never green-up
    expect(g.arrow).not.toBe("▲");
  });

  // THE teeth #2 — no data must NOT fabricate a direction.
  it("null / undefined / NaN → ▬ / faint — NOT a fabricated arrow/color", () => {
    for (const v of [null, undefined, NaN]) {
      const g = deltaGlyph(v as number | null | undefined);
      expect(g).toEqual({ arrow: "▬", cls: "faint" });
      expect(["pos", "neg"]).not.toContain(g.cls); // never green/red on no-data
    }
  });

  it("the neutral tone is NEVER pos/neg (so it can't render green/red)", () => {
    expect(["pos", "neg"]).not.toContain(deltaGlyph(0).cls);
    expect(["pos", "neg"]).not.toContain(deltaGlyph(null).cls);
  });
});

// ---------------------------------------------------------------------------
// #110 — slugifyVi: name → kebab id, matching the BE slug (so the user never types
// an id). Must reproduce the seed ids exactly (Uống nước → uong-nuoc).
// ---------------------------------------------------------------------------
describe("slugifyVi (#110 auto-slug)", () => {
  it("matches the BE seed slugs (Vietnamese diacritics stripped)", () => {
    expect(slugifyVi("Uống nước")).toBe("uong-nuoc");
    expect(slugifyVi("Tập thể dục")).toBe("tap-the-duc");
    expect(slugifyVi("Đọc sách")).toBe("doc-sach");
    expect(slugifyVi("Thiền")).toBe("thien");
    expect(slugifyVi("Viết nhật ký")).toBe("viet-nhat-ky");
  });
  it("đ/Đ → d, lowercases, collapses + trims hyphens", () => {
    expect(slugifyVi("Đi bộ")).toBe("di-bo");
    expect(slugifyVi("  Hello   World  ")).toBe("hello-world");
    expect(slugifyVi("A!!!B")).toBe("a-b");
  });
  it("empty / diacritic-only / punctuation-only → '' (caller surfaces 'cần id')", () => {
    expect(slugifyVi("")).toBe("");
    expect(slugifyVi("   ")).toBe("");
    expect(slugifyVi("!!!")).toBe("");
  });
  it("digits survive", () => {
    expect(slugifyVi("Bài 5")).toBe("bai-5");
  });
});
