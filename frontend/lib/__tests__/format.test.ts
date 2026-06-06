import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { relativeTime, idleDays, orDash, fmtUSD, fmtSign, fmtPct } from "../format";

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
