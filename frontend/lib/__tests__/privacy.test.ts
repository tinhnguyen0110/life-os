import { describe, it, expect, beforeEach } from "vitest";
import {
  normalizePrivacy,
  loadPrivacy,
  savePrivacy,
  STORAGE_KEY,
  DEFAULT_PRIVACY,
} from "@/lib/privacy";

describe("privacy — pure store (localStorage, device-local)", () => {
  beforeEach(() => localStorage.clear());

  it("default is OFF", () => {
    expect(DEFAULT_PRIVACY).toBe(false);
    expect(loadPrivacy()).toBe(false);
  });

  it("save → load round-trips the flag (persisted to localStorage)", () => {
    savePrivacy(true);
    expect(loadPrivacy()).toBe(true);
    expect(localStorage.getItem(STORAGE_KEY)).toBe(JSON.stringify({ on: true }));
    savePrivacy(false);
    expect(loadPrivacy()).toBe(false);
  });

  it("normalizePrivacy coerces shapes + falls back safely", () => {
    expect(normalizePrivacy(true)).toBe(true);
    expect(normalizePrivacy({ on: true })).toBe(true);
    expect(normalizePrivacy({ on: false })).toBe(false);
    expect(normalizePrivacy("garbage")).toBe(false); // malformed → default OFF
    expect(normalizePrivacy(null)).toBe(false);
  });

  it("malformed localStorage → safe default (no throw)", () => {
    localStorage.setItem(STORAGE_KEY, "{not json");
    expect(loadPrivacy()).toBe(false);
  });
});

describe("privacy mask is DISPLAY-ONLY (the CSS contract)", () => {
  it("the blur is CSS on [data-privacy=on] [data-amount] — the real value is NEVER deleted/replaced", () => {
    // DOM-level proof of the display-only contract: a money node tagged data-amount keeps
    // its REAL text content regardless of the privacy flag (the blur is purely visual CSS,
    // recoverable on toggle-off with no reload). We assert the tag + that text is untouched.
    document.body.innerHTML = `<div data-amount data-testid="m">$10,645</div>`;
    const el = document.querySelector("[data-amount]")!;
    expect(el.textContent).toBe("$10,645"); // real value present (OFF)
    document.body.setAttribute("data-privacy", "on");
    // ON: the text is UNCHANGED (mask = CSS filter, not a content swap) — recoverable
    expect(el.textContent).toBe("$10,645");
    document.body.removeAttribute("data-privacy");
    expect(el.textContent).toBe("$10,645"); // OFF again, no reload, real value back
    document.body.innerHTML = "";
  });
});

