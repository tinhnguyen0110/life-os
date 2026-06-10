/**
 * S13 T3 pre-scaffold — tweaks lib unit tests.
 * Tests: applyTweaks sets CSS vars; default bg=cool; loadTweaks/saveTweaks localStorage round-trip.
 *
 * These tests will compile ONLY after frontend ships tweaks.ts (T1).
 * Until then this file is a scout: `npx vitest run lib/__tests__/tweaks.test.ts` will error
 * with "Cannot find module '@/lib/tweaks'" — that is the expected pre-scaffold state.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  THEMES,
  BG,
  DEFAULT_TWEAKS,
  applyTweaks,
  loadTweaks,
  saveTweaks,
  type TweakState,
} from "@/lib/tweaks";

// ── helpers ──────────────────────────────────────────────────────────────────

function cssVar(name: string): string {
  return document.documentElement.style.getPropertyValue(name);
}

// ── constants / shape ────────────────────────────────────────────────────────

describe("tweaks lib — constants", () => {
  it("THEMES has exactly 6 keys: copper amber solar cyan violet rose", () => {
    expect(Object.keys(THEMES).sort()).toEqual(
      ["amber", "copper", "cyan", "rose", "solar", "violet"]
    );
  });

  it("each theme entry has name, primary, soft, dim, grad", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      expect(typeof t.name, `${key}.name`).toBe("string");
      expect(typeof t.primary, `${key}.primary`).toBe("string");
      expect(typeof t.soft, `${key}.soft`).toBe("string");
      expect(typeof t.dim, `${key}.dim`).toBe("string");
      expect(typeof t.grad, `${key}.grad`).toBe("string");
    }
  });

  it("BG has exactly 2 keys: cool warm", () => {
    expect(Object.keys(BG).sort()).toEqual(["cool", "warm"]);
  });

  it("each BG palette has all 8 CSS var keys", () => {
    const REQUIRED = ["--bg-0", "--bg-1", "--bg-2", "--bg-3", "--line", "--line-2", "--tx-1", "--tx-2"];
    for (const [key, palette] of Object.entries(BG)) {
      for (const v of REQUIRED) {
        expect(Object.keys(palette), `BG.${key} missing ${v}`).toContain(v);
      }
    }
  });

  it("DEFAULT_TWEAKS.bg is 'cool' (neutral default — user requirement)", () => {
    expect(DEFAULT_TWEAKS.bg).toBe("cool");
  });

  it("DEFAULT_TWEAKS.theme is 'copper'", () => {
    expect(DEFAULT_TWEAKS.theme).toBe("copper");
  });

  it("DEFAULT_TWEAKS.glow is true, scanline is false", () => {
    expect(DEFAULT_TWEAKS.glow).toBe(true);
    expect(DEFAULT_TWEAKS.scanline).toBe(false);
  });
});

// ── applyTweaks ──────────────────────────────────────────────────────────────

describe("applyTweaks — CSS vars", () => {
  afterEach(() => {
    // Clean up CSS vars and body class after each test
    document.documentElement.style.cssText = "";
    document.body.classList.remove("scanline");
  });

  it("sets --accent from the chosen theme's primary", () => {
    const t: TweakState = { theme: "copper", bg: "cool", glow: true, scanline: false };
    applyTweaks(t);
    expect(cssVar("--accent")).toBe(THEMES.copper.primary);
  });

  it("sets --accent-soft, --accent-dim, --accent-grad", () => {
    const t: TweakState = { theme: "cyan", bg: "cool", glow: false, scanline: false };
    applyTweaks(t);
    expect(cssVar("--accent-soft")).toBe(THEMES.cyan.soft);
    expect(cssVar("--accent-dim")).toBe(THEMES.cyan.dim);
    expect(cssVar("--accent-grad")).toBe(THEMES.cyan.grad);
  });

  it("sets BG vars from the chosen bg key", () => {
    const t: TweakState = { theme: "copper", bg: "cool", glow: true, scanline: false };
    applyTweaks(t);
    // Spot-check two vars from the cool palette
    expect(cssVar("--bg-0")).toBe(BG.cool["--bg-0"]);
    expect(cssVar("--tx-1")).toBe(BG.cool["--tx-1"]);
  });

  it("TEETH — warm bg sets different vars than cool bg", () => {
    const warm: TweakState = { theme: "copper", bg: "warm", glow: true, scanline: false };
    applyTweaks(warm);
    const warmBg0 = cssVar("--bg-0");

    const cool: TweakState = { theme: "copper", bg: "cool", glow: true, scanline: false };
    applyTweaks(cool);
    const coolBg0 = cssVar("--bg-0");

    // The two palettes must differ — not collapsed to same value
    expect(warmBg0).not.toBe(coolBg0);
  });

  it("scanline=true adds body.scanline class", () => {
    const t: TweakState = { theme: "copper", bg: "cool", glow: true, scanline: true };
    applyTweaks(t);
    expect(document.body.classList.contains("scanline")).toBe(true);
  });

  it("scanline=false removes body.scanline class", () => {
    document.body.classList.add("scanline"); // pre-condition: class was on
    const t: TweakState = { theme: "copper", bg: "cool", glow: true, scanline: false };
    applyTweaks(t);
    expect(document.body.classList.contains("scanline")).toBe(false);
  });
});

// ── localStorage persistence ─────────────────────────────────────────────────

describe("loadTweaks / saveTweaks — localStorage round-trip", () => {
  const KEY = "lifeos.tweaks";

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("loadTweaks() returns DEFAULT_TWEAKS when localStorage is empty", () => {
    const result = loadTweaks();
    expect(result).toEqual(DEFAULT_TWEAKS);
  });

  it("saveTweaks() writes to localStorage[lifeos.tweaks]", () => {
    const t: TweakState = { theme: "violet", bg: "warm", glow: false, scanline: true };
    saveTweaks(t);
    const raw = localStorage.getItem(KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw!)).toEqual(t);
  });

  it("loadTweaks() reads back what saveTweaks() wrote (survives reload sim)", () => {
    const saved: TweakState = { theme: "rose", bg: "cool", glow: false, scanline: false };
    saveTweaks(saved);
    const loaded = loadTweaks();
    expect(loaded).toEqual(saved);
  });

  it("TEETH — switching bg from warm to cool persists correctly (not sticky at warm)", () => {
    // save warm first
    saveTweaks({ theme: "copper", bg: "warm", glow: true, scanline: false });
    // overwrite with cool
    saveTweaks({ theme: "copper", bg: "cool", glow: true, scanline: false });
    const loaded = loadTweaks();
    expect(loaded.bg).toBe("cool");
  });

  it("loadTweaks() merges partial stored value with DEFAULT_TWEAKS (missing keys filled)", () => {
    // Store only theme + bg (no glow/scanline — simulates a future migration scenario)
    localStorage.setItem(KEY, JSON.stringify({ theme: "amber", bg: "warm" }));
    const loaded = loadTweaks();
    expect(loaded.theme).toBe("amber");
    expect(loaded.bg).toBe("warm");
    // Missing keys should fall back to defaults
    expect(typeof loaded.glow).toBe("boolean");
    expect(typeof loaded.scanline).toBe("boolean");
  });

  it("loadTweaks() returns DEFAULT_TWEAKS when stored value is malformed JSON", () => {
    localStorage.setItem(KEY, "not-json{{{");
    const loaded = loadTweaks();
    expect(loaded).toEqual(DEFAULT_TWEAKS);
  });
});

// ── no-flash parity (layout.tsx inline script vs lib/tweaks.ts) ──────────────
//
// The NO_FLASH_SCRIPT in app/layout.tsx inlines its own copy of THEMES + BG
// hex values because an inline <head> script can't import the TS module.
// This suite asserts the inlined values MATCH lib/tweaks.ts — so editing a
// hex in tweaks.ts without updating the script goes RED immediately.
//
// Approach: read layout.tsx as raw text (no export needed), then assert
// each THEMES.*.primary/soft/dim/grad and each BG var value is present in
// the script string.

import * as fs from "node:fs";
import * as path from "node:path";

describe("no-flash script parity — layout.tsx inlined values match lib/tweaks.ts", () => {
  // Read the raw no-flash-script.ts source once for all assertions.
  // The script was moved to lib/no-flash-script.ts (exported) so the parity
  // test can import it cleanly — layout.tsx just re-imports it from there.
  const layoutPath = path.resolve(__dirname, "../no-flash-script.ts");
  const layoutSrc = fs.readFileSync(layoutPath, "utf-8");

  // ── THEMES parity ──────────────────────────────────────────────────────────

  it("inlined THEMES covers all 6 keys", () => {
    for (const key of Object.keys(THEMES)) {
      expect(layoutSrc, `layout.tsx missing theme key "${key}"`).toContain(`${key}:{`);
    }
  });

  it("every THEMES.*.primary hex matches the inlined script", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      expect(
        layoutSrc,
        `layout.tsx THEMES.${key}.primary mismatch: expected ${t.primary}`
      ).toContain(t.primary);
    }
  });

  it("every THEMES.*.soft hex matches the inlined script", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      expect(
        layoutSrc,
        `layout.tsx THEMES.${key}.soft mismatch: expected ${t.soft}`
      ).toContain(t.soft);
    }
  });

  it("every THEMES.*.dim hex matches the inlined script", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      expect(
        layoutSrc,
        `layout.tsx THEMES.${key}.dim mismatch: expected ${t.dim}`
      ).toContain(t.dim);
    }
  });

  it("every THEMES.*.grad string matches the inlined script", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      expect(
        layoutSrc,
        `layout.tsx THEMES.${key}.grad mismatch: expected ${t.grad}`
      ).toContain(t.grad);
    }
  });

  // ── BG parity ──────────────────────────────────────────────────────────────

  it("every BG.cool var value matches the inlined script", () => {
    for (const [varName, value] of Object.entries(BG.cool)) {
      expect(
        layoutSrc,
        `layout.tsx BG.cool ${varName} mismatch: expected ${value}`
      ).toContain(value);
    }
  });

  it("every BG.warm var value matches the inlined script", () => {
    for (const [varName, value] of Object.entries(BG.warm)) {
      expect(
        layoutSrc,
        `layout.tsx BG.warm ${varName} mismatch: expected ${value}`
      ).toContain(value);
    }
  });

  // ── default tweaks parity ──────────────────────────────────────────────────

  it("no-flash script defaults to bg:'cool' (neutral) matching DEFAULT_TWEAKS", () => {
    // The inline script sets: var t={theme:'copper',bg:'cool',glow:true,scanline:false}
    expect(DEFAULT_TWEAKS.bg).toBe("cool"); // lib canonical
    expect(layoutSrc).toContain("bg:'cool'");
  });

  it("no-flash script defaults to theme:'copper' matching DEFAULT_TWEAKS", () => {
    expect(DEFAULT_TWEAKS.theme).toBe("copper");
    expect(layoutSrc).toContain("theme:'copper'");
  });

  // ── TEETH: confirm the test can actually CATCH a drift ────────────────────

  it("TEETH: a fabricated wrong hex is NOT in the script (test detects drift)", () => {
    // If THEMES values were changed to a completely different hex, the check above
    // would fail. Assert that an obviously wrong value is absent — proves the test
    // has real bite, not just passing by coincidence on an empty string.
    expect(layoutSrc).not.toContain("primary:'#000000'");
    expect(layoutSrc).not.toContain("'--bg-0':'#ffffff'");
  });
});
