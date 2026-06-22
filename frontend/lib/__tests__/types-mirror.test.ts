/**
 * types-mirror.test.ts — guard that lib/types.ts mirrors backend schema.py's
 * FROZEN ProjectStatus shape: nullable human/git fields, camelCase `testPass`,
 * `branch` present, ISO `last`/`lastAuto`. If a future edit drops a nullable or
 * reverts to snake_case, tsc fails here (compile-time) and the runtime asserts
 * document the contract.
 *
 * This is NOT a tautology: the object literals below would FAIL to type-check if
 * the interface narrowed (e.g. `last: string` instead of `string | null`), so
 * `npx tsc --noEmit` is the real gate. The runtime expects pin the shape.
 */
import { describe, it, expect } from "vitest";
import type {
  ProjectStatus,
  ProjectMetrics,
  ProjectsListData,
  ProjectRegisterInput,
  ProjectAbandonInput,
} from "../types";

describe("types.ts mirrors backend schema.py (frozen shape)", () => {
  it("ProjectMetrics: nullable lang/testPass/stars, camelCase testPass, branch present", () => {
    // All-null metrics (honest defaults from backend) must type-check.
    const honest: ProjectMetrics = {
      commits: 0,
      branch: "",
      lang: null,
      testPass: null,
      stars: null,
    };
    expect(honest.testPass).toBeNull();
    expect(honest.branch).toBe("");
    // populated variant
    const full: ProjectMetrics = {
      commits: 42,
      branch: "main",
      lang: "TypeScript",
      testPass: 100,
      stars: 7,
    };
    expect(full.lang).toBe("TypeScript");
  });

  it("ProjectStatus: nullable desc/progress/last/lastDays/next/lastAuto accept null", () => {
    const minimal: ProjectStatus = {
      id: "x",
      name: "X",
      desc: null,
      health: "act",
      progress: null,
      users: 0,
      last: null,
      lastDays: null,
      next: null,
      repo: "/tmp/x",
      metrics: { commits: 0, branch: "", lang: null, testPass: null, stars: null },
      routines: [],
      lastAuto: null,
      source: "auto",
      hidden: false,
    };
    expect(minimal.progress).toBeNull();
    expect(minimal.last).toBeNull();
    expect(minimal.lastAuto).toBeNull();

    // last is an ISO-8601 string when known (NOT human "2h trước").
    const known: ProjectStatus = { ...minimal, last: "2026-06-06T07:00:00Z", lastDays: 0 };
    expect(known.last).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it("ProjectsListData summary has all four health buckets + total", () => {
    const data: ProjectsListData = {
      projects: [],
      summary: { act: 0, slow: 0, stall: 0, dead: 0, total: 0 },
    };
    expect(Object.keys(data.summary).sort()).toEqual(
      ["act", "dead", "slow", "stall", "total"].sort(),
    );
  });

  it("register/abandon input types allow optional nullable fields", () => {
    const reg: ProjectRegisterInput = { name: "N", repo: "/r" };
    const regFull: ProjectRegisterInput = {
      name: "N",
      repo: "/r",
      goal: null,
      progress: null,
      next: null,
      users: null,
    };
    const ab: ProjectAbandonInput = { reason: "stalled" };
    expect(reg.name).toBe("N");
    expect(regFull.goal).toBeNull();
    expect(ab.reason).toBe("stalled");
  });
});
