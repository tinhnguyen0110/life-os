import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, within, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "../Sidebar";

let mockPath = "/";
vi.mock("@/lib/useNav", () => ({
  useSafePathname: () => mockPath,
  useSafeRouter: () => ({ push: vi.fn() }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a>,
}));

// badge fetches + settings (pins) — all NAMED fns the hooks call.
const getRoutines = vi.fn();
const getProjects = vi.fn();
const getMarket = vi.fn();
const getClaudeUsage = vi.fn();
const getSettings = vi.fn();
const patchSettings = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getRoutines: () => getRoutines(),
    getProjects: () => getProjects(),
    getMarket: () => getMarket(),
    getClaudeUsage: () => getClaudeUsage(),
    getSettings: () => getSettings(),
    patchSettings: (...a: unknown[]) => patchSettings(...a),
  };
});

const CONFIG = (over = {}) => ({
  automationEnabled: true, briefHour: 8, idleThresholdDays: 7, patternCheckEnabled: true,
  errorChannel: "inapp", timezone: "Asia/Ho_Chi_Minh", displayName: "",
  riskCapitalSmallUsd: 50000, riskCapitalLargeUsd: 500000, pinnedRoutes: [], ...over,
});
const ok = <T,>(data: T) => ({ success: true, data });

/** Let the mount-time async fetches (badges + settings) settle inside act() so their
 *  state updates don't land after the test (the act() warning). The projects badge
 *  resolving to "7" is the last of the badge fetches. */
async function settle() {
  await waitFor(() => expect(screen.getByTestId("nav-badge-/projects")).toHaveTextContent("7"));
}

// #74 change 4: sections default-collapsed. These pin/privacy tests assert nav links →
// seed all sections open so the full nav renders (collapse behavior tested separately).
const ALL_SECTIONS = ["Tổng quan", "Dự án", "Tài chính", "Tin tức", "Hằng ngày", "Tri thức", "Sự nghiệp", "Hệ thống", "Cấu hình"];

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("lifeos.navgroups", JSON.stringify({ open: ALL_SECTIONS }));
  document.body.removeAttribute("data-privacy");
  getRoutines.mockResolvedValue(ok({ routines: [], activeCount: 5, total: 5, runsToday: 0, lastRunAt: null }));
  getProjects.mockResolvedValue(ok({ projects: [], summary: { total: 7 } }));
  getMarket.mockResolvedValue(ok({ quotes: [], triggers: [], macro: [], alertHistory: [] }));
  getClaudeUsage.mockResolvedValue(ok({ pct5h: 18.9, pct: 1873 }));
  getSettings.mockResolvedValue(ok(CONFIG()));
});
afterEach(() => {
  cleanup();
  [getRoutines, getProjects, getMarket, getClaudeUsage, getSettings, patchSettings].forEach((m) => m.mockReset());
  localStorage.clear();
  document.body.removeAttribute("data-privacy");
});

/* ───────────────────────── PRIVACY (feature A) ─────────────────────────
   The toggle BUTTON moved to the TopBar (#74 change 3) — its click/persist tests live
   in TopBar.test.tsx now. Here we only assert the SIDEBAR's behavior under privacy:
   #74 blur-only means privacy does NOT hide any nav route. Drive privacy via the body
   attr directly (what usePrivacy sets) since the button is no longer in the Sidebar. */
describe("#74 Privacy is BLUR-ONLY in the sidebar (no hide-tab)", () => {
  it("privacy ON does NOT hide any nav route — every screen stays visible", async () => {
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await settle();
    // OFF baseline: all routes present (sections seeded open)
    for (const r of ["/decision", "/finance", "/portfolio", "/exchange", "/journal", "/market", "/macro", "/wiki"]) {
      expect(container.querySelector(`a[href="${r}"]`)).toBeTruthy();
    }
    // simulate privacy ON (the TopBar toggle sets this body attr app-wide)
    document.body.setAttribute("data-privacy", "on");
    // the Sidebar does NOT branch on privacy anymore → every route STILL present
    for (const r of ["/decision", "/finance", "/portfolio", "/exchange", "/journal", "/market", "/macro", "/wiki"]) {
      expect(container.querySelector(`a[href="${r}"]`)).toBeTruthy();
    }
    document.body.removeAttribute("data-privacy");
  });

  it("the sidebar header has NO privacy button (it moved to the TopBar)", async () => {
    render(<Sidebar onToggleCollapse={() => {}} />);
    await settle();
    expect(screen.queryByTestId("sb-privacy-toggle")).toBeNull();
  });
});

/* ───────────────────────── PIN (feature B, backend) ───────────────────────── */
describe("#72 Pin/Favorite — backend round-trip", () => {
  it("no pins → NO Ghim group (no empty header)", async () => {
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("pin-/finance")).toBeInTheDocument());
    expect(screen.queryByTestId("nav-group-pinned")).toBeNull();
    await settle();
  });

  it("pin /finance → PATCH {pinnedRoutes:[/finance]} → server-truth reflected → Ghim shows it", async () => {
    // the PATCH returns the new config (fail-closed: UI trusts the server value).
    patchSettings.mockResolvedValueOnce(ok(CONFIG({ pinnedRoutes: ["/finance"] })));
    const user = userEvent.setup();
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("pin-/finance")).toBeInTheDocument());
    await user.click(screen.getByTestId("pin-/finance"));
    // the real round-trip: PATCH called with the new array
    await waitFor(() => expect(patchSettings).toHaveBeenCalledWith({ pinnedRoutes: ["/finance"] }));
    // Ghim group appears with the pinned route
    await waitFor(() => expect(screen.getByTestId("nav-group-pinned")).toBeInTheDocument());
    expect(within(screen.getByTestId("nav-group-pinned")).getByText("Tổng quan tài chính")).toBeInTheDocument();
    await settle();
  });

  it("pin ADD-not-move: a pinned route shows in BOTH Ghim AND its home section", async () => {
    getSettings.mockResolvedValue(ok(CONFIG({ pinnedRoutes: ["/finance"] })));
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-group-pinned")).toBeInTheDocument());
    // /finance link appears TWICE: once in Ghim, once in its "Tài chính" home section
    const links = container.querySelectorAll('a[href="/finance"]');
    expect(links.length).toBe(2);
    await settle();
  });

  it("fail-soft: a pinnedRoute that doesn't resolve to a nav item is SKIPPED (no crash)", async () => {
    getSettings.mockResolvedValue(ok(CONFIG({ pinnedRoutes: ["/ghost-route", "/finance"] })));
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-group-pinned")).toBeInTheDocument());
    const ghim = screen.getByTestId("nav-group-pinned");
    // only the real route renders; the ghost is dropped (no crash, no broken link)
    expect(within(ghim).getByText("Tổng quan tài chính")).toBeInTheDocument();
    expect(within(ghim).queryByText(/ghost/i)).toBeNull();
    await settle();
  });

  it("Home ('/') has no pin star (it's the fixed root, not pinnable)", async () => {
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("pin-/finance")).toBeInTheDocument());
    expect(screen.queryByTestId("pin-/")).toBeNull();
    await settle();
  });
});

/* ───────────────────────── COLLAPSE bugfix intact ───────────────────────── */
describe("#72 collapse bugfix not regressed", () => {
  it("the collapse toggle still renders + fires (team-lead's quick-fix preserved)", async () => {
    const onToggle = vi.fn();
    render(<Sidebar onToggleCollapse={onToggle} />);
    await settle();
    const collapseBtn = screen.getByLabelText("Thu gọn sidebar");
    expect(collapseBtn).toBeInTheDocument();
    collapseBtn.click();
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

/* ───────────────── #74 change 4 — collapsible nav groups (default collapsed) ─────────────── */
describe("#74 collapsible nav groups", () => {
  // these tests do NOT seed all-open — they exercise the DEFAULT collapsed behavior.
  beforeEach(() => localStorage.removeItem("lifeos.navgroups"));

  it("DEFAULT collapsed: a non-active group's items are hidden; the active group auto-expands", async () => {
    mockPath = "/finance"; // active route → "Tài chính" group auto-expands
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(container.querySelector('a[href="/finance"]')).toBeTruthy());
    // active group OPEN → its sibling finance routes render
    expect(container.querySelector('a[href="/portfolio"]')).toBeTruthy();
    // a DIFFERENT group (Tri thức / wiki) is collapsed by default → its items hidden
    expect(container.querySelector('a[href="/wiki"]')).toBeNull();
    // its header toggle still renders (so the user can expand it)
    expect(screen.getByTestId("nav-sec-toggle-Tri thức")).toBeInTheDocument();
    mockPath = "/";
  });

  it("clicking a collapsed section header expands it (reveals its items)", async () => {
    mockPath = "/";
    const user = userEvent.setup();
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-sec-toggle-Tài chính")).toBeInTheDocument());
    // "Tài chính" is NOT the active group (active="/" → Tổng quan) → collapsed
    expect(container.querySelector('a[href="/finance"]')).toBeNull();
    // expand it
    await user.click(screen.getByTestId("nav-sec-toggle-Tài chính"));
    await waitFor(() => expect(container.querySelector('a[href="/finance"]')).toBeTruthy());
  });

  it("a manually-opened group persists across reload (localStorage)", async () => {
    mockPath = "/";
    const user = userEvent.setup();
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-sec-toggle-Tài chính")).toBeInTheDocument());
    await user.click(screen.getByTestId("nav-sec-toggle-Tài chính"));
    await waitFor(() => expect(localStorage.getItem("lifeos.navgroups")).toContain("Tài chính"));
    // remount = reload → the manually-opened group is still open
    cleanup();
    const r2 = render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(r2.container.querySelector('a[href="/finance"]')).toBeTruthy());
  });

  it("whole-sidebar collapse (64px) FORCES all groups open (group-collapse is moot there)", async () => {
    mockPath = "/";
    // collapsed sidebar → every group's items render (so the icon rail shows all)
    const { container } = render(<Sidebar collapsed onToggleCollapse={() => {}} />);
    await waitFor(() => expect(container.querySelector('a[href="/"]')).toBeTruthy());
    // even non-active, non-manually-open groups render their items when sidebar collapsed
    expect(container.querySelector('a[href="/finance"]')).toBeTruthy();
    expect(container.querySelector('a[href="/wiki"]')).toBeTruthy();
  });
});
