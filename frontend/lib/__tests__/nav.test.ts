import { describe, it, expect } from "vitest";
import { NAV, CRUMB, ALL_ROUTES } from "../nav";

describe("nav config (D3 — 14 foundation screens + Wiki + Career, 8 groups, no AI)", () => {
  it("has exactly 9 groups in SPEC §1 order (+ Tin tức for News, + Tri thức for Wiki, + Sự nghiệp for Career)", () => {
    expect(NAV.map((g) => g.sec)).toEqual([
      "Tổng quan",
      "Dự án",
      "Tài chính",
      "Tin tức",
      "Hằng ngày",
      "Tri thức",
      "Sự nghiệp",
      "Hệ thống",
      "Cấu hình",
    ]);
  });

  it("covers all 14 foundation screens S1–S14 + OKX Exchange + Wiki (W1/W3/W4/P1/W5/A1c) + Career across nav items", () => {
    const screens = NAV.flatMap((g) => g.items.map((i) => i.screen));
    const unique = new Set(screens);
    // 14 foundation entries (S1..S14 minus S3 detail, PLUS S-okx) + Wiki nav group:
    // W1 Vault Home · W3 Inbox · W4 Graph. (S3/S6 + /wiki/[id] detail views + P1
    // Proposals (M4) resolve/land elsewhere — not linked here, no dead links.)
    // + CAR — the Career cockpit (CV · Blog · Demo) under "Sự nghiệp" (CAR-1).
    expect(screens).toContain("S1");
    expect(screens).toContain("S14");
    expect(screens).toContain("S-okx");
    expect(screens).toContain("W1");
    expect(screens).toContain("W3");
    expect(screens).toContain("W4");
    expect(screens).toContain("P1");
    expect(screens).toContain("W5");
    expect(screens).toContain("A1c");
    expect(screens).toContain("DJ");
    expect(screens).toContain("CAR");
    expect(screens).toContain("FE-5-macro");
    expect(screens).toContain("FE-5-news");
    expect(screens).toContain("DEC"); // Decision Cockpit (FINANCE-UI)
    expect(screens).toContain("REM"); // Reminders (#31 GAP-4) under "Hằng ngày"
    expect(screens).toContain("TRACE"); // Daily Tracing (#65-P3 G-HABIT) under "Hằng ngày"
    expect(screens).toContain("DEVACT"); // Dev Activity (#63 git contributions) under "Dự án" (user CHỐT nav-IA option A) — DISTINCT from S14 /activity feed
    expect(screens).toContain("REPOMEM"); // Repo Memory (#64-P3 code_insight + repo_memory) under "Dự án" — DISTINCT browse screen
    expect(unique.size).toBe(29);
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
