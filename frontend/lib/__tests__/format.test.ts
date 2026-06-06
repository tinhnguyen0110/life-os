import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { relativeTime, idleDays, orDash } from "../format";

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
