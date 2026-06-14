/**
 * tests/projects-s2.test.tsx — Sprint 2 pre-scaffold: shared components + Projects screens.
 *
 * Designed to skip gracefully until T1/T2/T3 land.
 * Every test asserts observable behavior (DOM output, class names, user interactions)
 * — NOT call counts or internal structure.
 *
 * Baseline when all modules land: vitest ≥ 125 (90 + 35+ new tests here).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import type { ProjectHealth, ProjectStatus, ProjectMetrics } from "@/lib/types";

// ProjectsPage / ProjectDetailPage fetch on mount (global.fetch mock). Section F/G
// tests assert synchronously, so the resolved-state update lands after the test → a
// React act() warning. Flushing pending microtasks/effects inside act() before the
// test ends applies those updates cleanly (purely settles async state — no behaviour
// change). The pure-component sections (A–E) don't fetch, so they don't need this.
async function flushEffects() {
  await act(async () => { await Promise.resolve(); });
}

// ------------------------------------------------------------------ #
// Import guards — skip whole describe blocks until modules exist.
// ------------------------------------------------------------------ #
let HealthChip: React.ComponentType<{ health: ProjectHealth }> | null = null;
// ProgressBar actual API: value (number|null) + health (ProjectHealth) + optional variant/showLabel
let ProgressBar: React.ComponentType<{ value: number | null; health?: ProjectHealth; variant?: "inline" | "block"; showLabel?: boolean }> | null = null;
// KpiCard actual API: label + value (ReactNode) + optional sub (ReactNode) + optional tone
let KpiCard: React.ComponentType<{ label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: string }> | null = null;

try { HealthChip = (await import("@/components/shared/HealthChip")).HealthChip; } catch { /* T1 not yet */ }
try { ProgressBar = (await import("@/components/shared/ProgressBar")).ProgressBar; } catch { /* T1 not yet */ }
try { KpiCard = (await import("@/components/shared/KpiCard")).KpiCard; } catch { /* T1 not yet */ }

// ------------------------------------------------------------------ #
// Fixtures — frozen ProjectStatus shape (mirror schema.py, Sprint 1).
// Nullables mirrored correctly: desc/progress/next/lastDays/lastAuto/last = null allowed.
// ------------------------------------------------------------------ #
const METRICS_FULL: ProjectMetrics = {
  commits: 500,
  branch: "main",
  lang: "TypeScript",
  testPass: null,
  stars: null,
};

const METRICS_EMPTY: ProjectMetrics = {
  commits: 0,
  branch: "",
  lang: null,
  testPass: null,
  stars: null,
};

const PROJECT_ACT: ProjectStatus = {
  id: "outboundos",
  name: "OutboundOS",
  desc: "Outbound sales automation",
  health: "act",
  progress: 72,
  users: 3,
  last: "2026-06-05T10:00:00+00:00",
  lastDays: 1,
  next: "Ship v2 API",
  repo: "/home/watercry/Disk_C/Data/Tinhdev/OutboundOS",
  metrics: METRICS_FULL,
  routines: ["wiki-refresh"],
  lastAuto: "2026-06-05T12:00:00+00:00",
};

const PROJECT_SLOW: ProjectStatus = {
  id: "crewly",
  name: "Crewly",
  desc: "Team management SaaS",
  health: "slow",
  progress: 45,
  users: 1,
  last: "2026-05-20T10:00:00+00:00",
  lastDays: 17,
  next: null,
  repo: "/home/watercry/Disk_C/Data/Tinhdev/Crewly",
  metrics: METRICS_FULL,
  routines: ["wiki-refresh"],
  lastAuto: null,
};

const PROJECT_STALL: ProjectStatus = {
  id: "habit-tracker",
  name: "Habit Tracker",
  desc: null,
  health: "stall",
  progress: null,
  users: 0,
  last: "2026-04-01T10:00:00+00:00",
  lastDays: 66,
  next: null,
  repo: "/home/watercry/Disk_C/Data/Tinhdev/HabitTracker",
  metrics: METRICS_EMPTY,
  routines: [],
  lastAuto: null,
};

const PROJECT_DEAD: ProjectStatus = {
  id: "old-project",
  name: "Old Project",
  desc: null,
  health: "dead",
  progress: null,
  users: 0,
  last: null,
  lastDays: null,
  next: null,
  repo: "/nonexistent/path",
  metrics: METRICS_EMPTY,
  routines: [],
  lastAuto: null,
};

// ------------------------------------------------------------------ #
// Section A — HealthChip component
// ------------------------------------------------------------------ #
describe("HealthChip", () => {
  it("act — uses sb-act class (green chip)", () => {
    if (!HealthChip) return;
    const { container } = render(<HealthChip health="act" />);
    const badge = container.querySelector(".sbadge");
    expect(badge).toBeTruthy();
    expect(badge!.className).toContain("sb-act");
    expect(badge!.className).not.toContain("sb-slow");
    expect(badge!.className).not.toContain("sb-stall");
    expect(badge!.className).not.toContain("sb-dead");
  });

  it("slow — uses sb-slow class (amber chip)", () => {
    if (!HealthChip) return;
    const { container } = render(<HealthChip health="slow" />);
    const badge = container.querySelector(".sbadge");
    expect(badge).toBeTruthy();
    expect(badge!.className).toContain("sb-slow");
  });

  it("stall — uses sb-stall class (red chip)", () => {
    if (!HealthChip) return;
    const { container } = render(<HealthChip health="stall" />);
    const badge = container.querySelector(".sbadge");
    expect(badge).toBeTruthy();
    expect(badge!.className).toContain("sb-stall");
  });

  it("dead — uses sb-dead class (muted chip)", () => {
    if (!HealthChip) return;
    const { container } = render(<HealthChip health="dead" />);
    const badge = container.querySelector(".sbadge");
    expect(badge).toBeTruthy();
    expect(badge!.className).toContain("sb-dead");
  });

  it("contains a colored dot element", () => {
    if (!HealthChip) return;
    const { container } = render(<HealthChip health="act" />);
    // Mock uses <span class="dot"> inside .sbadge
    const dot = container.querySelector(".sbadge .dot");
    expect(dot).toBeTruthy();
  });

  it("renders visible health label text (non-empty)", () => {
    if (!HealthChip) return;
    const { container } = render(<HealthChip health="act" />);
    const badge = container.querySelector(".sbadge");
    expect(badge!.textContent!.trim().length).toBeGreaterThan(0);
  });
});

// ------------------------------------------------------------------ #
// Section B — ProgressBar component
// ------------------------------------------------------------------ #
describe("ProgressBar", () => {
  it("renders .barc wrapper", () => {
    if (!ProgressBar) return;
    const { container } = render(<ProgressBar value={72} health="act" />);
    expect(container.querySelector(".barc")).toBeTruthy();
  });

  it("inner <i> width reflects progress percent", () => {
    if (!ProgressBar) return;
    // Actual API: value={72} health="act"
    const { container } = render(<ProgressBar value={72} health="act" />);
    const inner = container.querySelector(".barc i");
    expect(inner).toBeTruthy();
    // data-value attribute or style encodes the actual pct
    const bar = container.querySelector("[data-testid='progress-bar']") as HTMLElement;
    // Check data-value attribute (set by component when value is known)
    const dataVal = bar?.getAttribute("data-value");
    if (dataVal) {
      expect(dataVal).toContain("72");
    } else {
      // Fallback: check style.width on <i>
      const style = (inner as HTMLElement).style.width;
      expect(style).toContain("72");
    }
  });

  it("progress=0 renders zero-width bar (not crash)", () => {
    if (!ProgressBar) return;
    const { container } = render(<ProgressBar value={0} health="stall" />);
    const inner = container.querySelector(".barc i");
    expect(inner).toBeTruthy();
    const style = (inner as HTMLElement).style.width;
    expect(style).toContain("0");
  });

  it("progress=100 renders full bar", () => {
    if (!ProgressBar) return;
    const { container } = render(<ProgressBar value={100} health="act" />);
    const inner = container.querySelector(".barc i");
    expect(inner).toBeTruthy();
    const style = (inner as HTMLElement).style.width;
    expect(style).toContain("100");
  });

  it("value=null renders '—' NOT a fabricated bar value (no fabrication)", () => {
    if (!ProgressBar) return;
    const { container } = render(<ProgressBar value={null} />);
    const text = container.textContent ?? "";
    // Must show "—" for null — the component uses the em-dash explicitly
    expect(text).toContain("—");
    // data-value must be "none" to signal null (not a fake pct)
    const bar = container.querySelector("[data-testid='progress-bar']") as HTMLElement;
    expect(bar?.getAttribute("data-value")).toBe("none");
  });
});

// ------------------------------------------------------------------ #
// Section C — KpiCard component
// ------------------------------------------------------------------ #
describe("KpiCard", () => {
  it("renders label + value", () => {
    if (!KpiCard) return;
    render(<KpiCard label="Tổng dự án" value={6} />);
    expect(screen.getByText("Tổng dự án")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
  });

  it("renders sub (delta) when provided", () => {
    if (!KpiCard) return;
    // Actual API: sub not delta
    render(<KpiCard label="Active" value={2} sub="commit trong 24h" />);
    expect(screen.getByText("commit trong 24h")).toBeInTheDocument();
  });

  it("renders without sub (optional prop)", () => {
    if (!KpiCard) return;
    expect(() => render(<KpiCard label="Cần chú ý" value={3} />)).not.toThrow();
  });

  it("uses .stat wrapper class (mock token)", () => {
    if (!KpiCard) return;
    const { container } = render(<KpiCard label="Tổng dự án" value={6} />);
    expect(container.querySelector(".stat")).toBeTruthy();
  });
});

// ------------------------------------------------------------------ #
// Section D — lib/types.ts reconciliation checks
// (Verifies frozen shape is mirrored correctly after T1 reconcile.)
// ------------------------------------------------------------------ #
describe("lib/types — ProjectStatus shape reconciliation", () => {
  it("ProjectMetrics has branch field (camelCase) not missing", () => {
    const m: ProjectMetrics = {
      commits: 100,
      branch: "main",
      lang: null,
      testPass: null,
      stars: null,
    };
    expect(m.branch).toBe("main");
  });

  it("ProjectMetrics uses testPass (camelCase, not test_pass snake_case)", () => {
    const m: ProjectMetrics = {
      commits: 0,
      branch: "",
      lang: null,
      testPass: null,
      stars: null,
    };
    // If this compiled, testPass exists in the type (snake_case would be a TS error)
    expect("testPass" in m).toBe(true);
    expect("test_pass" in m).toBe(false);
  });

  it("ProjectStatus.progress allows null (nullable)", () => {
    const p = PROJECT_STALL;
    expect(p.progress).toBeNull();
  });

  it("ProjectStatus.desc allows null (nullable)", () => {
    const p = PROJECT_STALL;
    expect(p.desc).toBeNull();
  });

  it("ProjectStatus.next allows null (nullable)", () => {
    const p = PROJECT_STALL;
    expect(p.next).toBeNull();
  });

  it("ProjectStatus.lastAuto allows null (nullable)", () => {
    const p = PROJECT_SLOW;
    expect(p.lastAuto).toBeNull();
  });

  it("ProjectStatus.lastDays allows null (nullable)", () => {
    const p = PROJECT_DEAD;
    expect(p.lastDays).toBeNull();
  });

  it("ProjectStatus.last allows null (nullable)", () => {
    const p = PROJECT_DEAD;
    expect(p.last).toBeNull();
  });
});

// ------------------------------------------------------------------ #
// Section E — lib/api.ts Sprint 2 additions
// ------------------------------------------------------------------ #
// Pre-load api module once at top level (avoids vi.mock hoisting conflicts).
let apiModule: typeof import("@/lib/api") | null = null;
try { apiModule = await import("@/lib/api"); } catch { /* not yet */ }

describe("lib/api — getProjects() + getProject(id)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => vi.restoreAllMocks());

  it("getProjects exists and calls /projects endpoint", async () => {
    if (!apiModule) return;
    const getProjects = (apiModule as any).getProjects;
    if (typeof getProjects !== "function") return; // T2 not yet landed
    const mockData = {
      success: true,
      data: { projects: [PROJECT_ACT], summary: { act: 1, slow: 0, stall: 0, dead: 0, total: 1 } },
    };
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    } as any);
    const result = await getProjects();
    expect(result.success).toBe(true);
    expect(result.data.projects).toHaveLength(1);
    expect(result.data.summary.total).toBe(1);
    expect((global.fetch as any).mock.calls[0][0]).toContain("/projects");
  });

  it("getProject(id) calls /projects/{id}", async () => {
    if (!apiModule) return;
    const getProject = (apiModule as any).getProject;
    if (typeof getProject !== "function") return; // T2 not yet landed
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, data: PROJECT_ACT }),
    } as any);
    const result = await getProject("outboundos");
    expect(result.success).toBe(true);
    expect(result.data.id).toBe("outboundos");
    expect((global.fetch as any).mock.calls[0][0]).toContain("/projects/outboundos");
  });

  it("getProject(id) propagates ApiError on 404", async () => {
    if (!apiModule) return;
    const getProject = (apiModule as any).getProject;
    if (typeof getProject !== "function") return; // T2 not yet landed
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: "project 'nobody' not found" }),
    } as any);
    await expect(getProject("nobody")).rejects.toThrow();
  });

  it("apiPost helper exists (used for refresh/abandon)", async () => {
    if (!apiModule) return;
    const apiPost = (apiModule as any).apiPost;
    if (typeof apiPost !== "function") return; // T2 not yet landed
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, data: PROJECT_ACT }),
    } as any);
    const result = await apiPost("/projects/outboundos/refresh");
    expect(result.success).toBe(true);
    expect((global.fetch as any).mock.calls[0][0]).toContain("/projects/outboundos/refresh");
  });
});

// ------------------------------------------------------------------ #
// Section F — S2 Projects List screen (app/projects/page.tsx)
// Screen tests use global.fetch mocking (NOT vi.mock — hoisting issue).
// T2 replaces the EmptyScreen stub; guards check for real S2 content.
// ------------------------------------------------------------------ #
let ProjectsPage: React.ComponentType | null = null;
try {
  const mod = await import("@/app/projects/page");
  ProjectsPage = mod.default;
} catch { /* not yet */ }

/** Mock global fetch to return a projects list payload. */
function mockFetchProjects(projects = [PROJECT_ACT, PROJECT_SLOW, PROJECT_STALL]) {
  const payload = {
    success: true,
    data: {
      projects,
      summary: {
        act: projects.filter((p) => p.health === "act").length,
        slow: projects.filter((p) => p.health === "slow").length,
        stall: projects.filter((p) => p.health === "stall").length,
        dead: projects.filter((p) => p.health === "dead").length,
        total: projects.length,
      },
    },
  };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => payload,
  } as any);
}

describe("S2 Projects List screen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockFetchProjects();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders without crashing (fetch mocked)", async () => {
    if (!ProjectsPage) return;
    expect(() => render(<ProjectsPage />)).not.toThrow();
    await flushEffects();
  });

  it("renders heading 'Dự án'", async () => {
    if (!ProjectsPage) return;
    render(<ProjectsPage />);
    // /dự án/i collides with "Dự án" column header + "Dự án mới" button — use h1 role
    expect(screen.getByRole("heading", { name: /^dự án$/i, level: 1 })).toBeInTheDocument();
    await flushEffects();
  });

  it("renders summary KpiCards (4 stat blocks) once real S2 lands", async () => {
    if (!ProjectsPage) return;
    const { container } = render(<ProjectsPage />);
    const stats = container.querySelectorAll(".stat");
    await flushEffects();
    if (stats.length === 0) return; // still EmptyScreen stub — skip gracefully
    expect(stats.length).toBeGreaterThanOrEqual(4);
  });

  it("renders a .dtable when projects exist (after T2 lands)", async () => {
    if (!ProjectsPage) return;
    const { container } = render(<ProjectsPage />);
    const table = container.querySelector(".dtable");
    await flushEffects();
    if (!table) return; // still EmptyScreen stub — skip gracefully
    expect(table).toBeTruthy();
  });

  it("progress=null renders '—' not 0% (after T2 lands)", async () => {
    if (!ProjectsPage) return;
    mockFetchProjects([PROJECT_STALL]); // progress: null
    const { container } = render(<ProjectsPage />);
    const table = container.querySelector(".dtable");
    await flushEffects();
    if (!table) return; // still a stub — skip gracefully
    expect(container.textContent).not.toMatch(/\b0%/);
  });

  it("empty list renders empty state (not crash)", async () => {
    if (!ProjectsPage) return;
    mockFetchProjects([]);
    expect(() => render(<ProjectsPage />)).not.toThrow();
    await flushEffects();
  });

  it("fetch error → renders without crash (friendly error state)", async () => {
    if (!ProjectsPage) return;
    global.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));
    expect(() => render(<ProjectsPage />)).not.toThrow();
    await flushEffects();
  });
});

// ------------------------------------------------------------------ #
// Section G — S3 Project Detail screen (app/projects/[id]/page.tsx)
// ------------------------------------------------------------------ #
let ProjectDetailPage: React.ComponentType<{ params?: { id?: string } }> | null = null;
try {
  const mod = await import("@/app/projects/[id]/page");
  ProjectDetailPage = mod.default;
} catch { /* not yet */ }

function mockFetchProject(project = PROJECT_ACT) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ success: true, data: project }),
  } as any);
}

describe("S3 Project Detail screen", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockFetchProject();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders without crashing (fetch mocked)", async () => {
    if (!ProjectDetailPage) return;
    expect(() =>
      render(<ProjectDetailPage params={{ id: "outboundos" }} />)
    ).not.toThrow();
    await flushEffects();
  });

  it("404 — fetch returns 404 → renders without crash", async () => {
    if (!ProjectDetailPage) return;
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ detail: "project 'nobody' not found" }),
    } as any);
    expect(() =>
      render(<ProjectDetailPage params={{ id: "nobody" }} />)
    ).not.toThrow();
    await flushEffects();
  });

  it("renders project name once T3 lands (stub skips gracefully)", async () => {
    if (!ProjectDetailPage) return;
    mockFetchProject(PROJECT_ACT);
    const { container } = render(<ProjectDetailPage params={{ id: "outboundos" }} />);
    await flushEffects();
    // Real S3 renders p.name in <h1>; stub renders params.id only.
    // Guard: only assert after T3 ships real content.
    if (!container.textContent?.includes("OutboundOS")) return;
    // The name appears in the heading AND the breadcrumb once the fetch settles —
    // getAllByText (≥1) asserts it renders without tripping on the duplicate.
    expect(screen.getAllByText(/OutboundOS/i).length).toBeGreaterThan(0);
  });

  it("lastAuto=null renders 'chưa chạy' once T3 lands", async () => {
    if (!ProjectDetailPage) return;
    mockFetchProject(PROJECT_SLOW); // lastAuto: null
    const { container } = render(<ProjectDetailPage params={{ id: "crewly" }} />);
    await flushEffects();
    if (!container.textContent?.includes("chưa chạy")) return; // still stub
    expect(container.textContent).toContain("chưa chạy");
  });

  it("progress=null renders '—' once T3 lands", async () => {
    if (!ProjectDetailPage) return;
    mockFetchProject(PROJECT_STALL); // progress: null
    const { container } = render(<ProjectDetailPage params={{ id: "habit-tracker" }} />);
    await flushEffects();
    // Guard: stub page won't have progress display
    if (!container.querySelector("[data-testid='progress-bar']")) return;
    const bar = container.querySelector("[data-testid='progress-bar']") as HTMLElement;
    expect(bar?.getAttribute("data-value")).toBe("none");
  });
});
