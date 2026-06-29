import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, within, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "../Sidebar";
import { NAV, ALL_ROUTES } from "@/lib/nav";

let mockPath = "/";
vi.mock("@/lib/useNav", () => ({
  useSafePathname: () => mockPath,
  useSafeRouter: () => ({ push: vi.fn() }),
}));
// Sidebar fetches all 4 module endpoints for the live nav badges (F2-M4) — mock them.
const getRoutines = vi.fn();
const getProjects = vi.fn();
const getMarket = vi.fn();
const getClaudeUsage = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getRoutines: () => getRoutines(),
    getProjects: () => getProjects(),
    getMarket: () => getMarket(),
    getClaudeUsage: () => getClaudeUsage(),
  };
});
// next/link → plain anchor in jsdom
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// Sidebar fires 4 badge fetches on mount (routines/projects/market/claude). Tests
// that assert structure synchronously must still let those settle, else React logs
// an act() warning when the badge state lands after the test. waitFor retries inside
// act() until the projects badge resolves to its live value (the default-mock "7").
async function settleSidebar() {
  await waitFor(() => expect(screen.getByTestId("nav-badge-/projects")).toHaveTextContent("7"));
}

// #74 change 4: nav sections default-COLLAPSED. These structural tests assume the full
// nav is visible → seed localStorage with ALL sections open so items/badges render. (The
// collapse behavior itself is tested in Sidebar.sidebarux.test.tsx.)
const ALL_SECTIONS = ["Tổng quan", "Dự án", "Tài chính", "Tin tức", "Hằng ngày", "Tri thức", "Sự nghiệp", "Hệ thống", "Cấu hình"];

describe("Sidebar", () => {
  beforeEach(() => {
    localStorage.setItem("lifeos.navgroups", JSON.stringify({ open: ALL_SECTIONS }));
    // defaults: all 4 badge fetches resolve so the sidebar has live values.
    getRoutines.mockResolvedValue({ success: true, data: { routines: [], activeCount: 5, total: 5, runsToday: 0, lastRunAt: null } });
    getProjects.mockResolvedValue({ success: true, data: { projects: [], summary: { total: 7 } } });
    getMarket.mockResolvedValue({ success: true, data: { quotes: [], triggers: [], macro: [], alertHistory: [] } });
    getClaudeUsage.mockResolvedValue({ success: true, data: { pct5h: 18.9, pct: 1873 } });
  });
  afterEach(() => {
    cleanup();
    localStorage.clear();
    getRoutines.mockReset();
    getProjects.mockReset();
    getMarket.mockReset();
    getClaudeUsage.mockReset();
  });

  it("Automation nav badge shows LIVE activeCount (was static '5')", async () => {
    getRoutines.mockResolvedValue({ success: true, data: { routines: [], activeCount: 6, total: 6, runsToday: 0, lastRunAt: null } });
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-badge-/routines")).toHaveTextContent("6"));
  });

  it("Automation badge fails soft → HONEST '—' fallback when /routines down (no stale number)", async () => {
    getRoutines.mockRejectedValue(new Error("down"));
    render(<Sidebar onToggleCollapse={() => {}} />);
    // UI-CLEANUP R2: the fallback is now "—" (honest no-data), NOT the stale "5".
    await waitFor(() => expect(screen.getByTestId("nav-badge-/routines")).toHaveTextContent("—"));
    expect(screen.getByTestId("nav-badge-/routines")).not.toHaveTextContent("5");
  });

  it("renders every nav group from NAV (default: all modules enabled)", async () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    // #74 change 4: the section header is now a toggle button; read the LABEL span
    // (.sb-sec-lbl) so the chevron glyph doesn't pollute the section name.
    const secs = Array.from(container.querySelectorAll(".sb-sec-lbl")).map((e) => e.textContent);
    for (const g of NAV) {
      expect(secs).toContain(g.sec);
    }
    // Derive the count from NAV (robust to module additions — e.g. the career
    // module added "Sự nghiệp"). Guards against a NAV that collapsed to empty.
    expect(NAV.length).toBeGreaterThanOrEqual(7);
    expect(secs.filter(Boolean)).toHaveLength(NAV.length);
    await settleSidebar();
  });

  it("renders a link for every nav route in ALL_ROUTES", async () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    for (const route of ALL_ROUTES) {
      expect(container.querySelector(`a[href="${route}"]`)).toBeTruthy();
    }
    // Count derived from NAV (was hardcoded 21; the career module's /career made it
    // grow — deriving keeps the test robust to legitimate module additions).
    expect(ALL_ROUTES).toHaveLength(NAV.flatMap((g) => g.items).length);
    // WIKI-TRIM: the MOC + Sync wiki screens were removed → no sidebar links for them.
    expect(container.querySelector('a[href="/wiki/moc"]')).toBeNull();
    expect(container.querySelector('a[href="/wiki/sync"]')).toBeNull();
    // a kept wiki route still links (the AI-first audit log).
    expect(container.querySelector('a[href="/wiki/proposals"]')).toBeTruthy();
    expect(container.querySelector('a[href="/decision-journal"]')).toBeTruthy();
    await settleSidebar();
  });

  it("marks the active route with `on` and aria-current", async () => {
    mockPath = "/market";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const active = container.querySelector('a[href="/market"]');
    expect(active?.className).toContain("on");
    expect(active?.getAttribute("aria-current")).toBe("page");
    await settleSidebar();
  });

  it("Home is only active at exactly `/` (not on sub-routes)", async () => {
    mockPath = "/projects";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const home = container.querySelector('a[href="/"]');
    expect(home?.className).not.toContain("on");
    await settleSidebar();
  });

  it("detail route /projects/abc keeps /projects active (prefix match)", async () => {
    mockPath = "/projects/abc";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    expect(container.querySelector('a[href="/projects"]')?.className).toContain("on");
    await settleSidebar();
  });

  it("collapse button fires the callback", async () => {
    mockPath = "/";
    const onToggle = vi.fn();
    render(<Sidebar onToggleCollapse={onToggle} />);
    screen.getByLabelText("Thu gọn sidebar").click();
    expect(onToggle).toHaveBeenCalledTimes(1);
    await settleSidebar();
  });

  it("F2-M4: all 4 badges render LIVE values (projects total, claude pct, automation activeCount)", async () => {
    mockPath = "/";
    render(<Sidebar onToggleCollapse={() => {}} />);
    // projects → summary.total=7 (was static "4")
    await waitFor(() => expect(screen.getByTestId("nav-badge-/projects")).toHaveTextContent("7"));
    // claude-usage → round(pct5h)=19% (was static "71%"). MUST use pct5h (18.9), NOT
    // the overflowing pct (1873) — matches the S9 screen + Home tile (honest-mirror).
    expect(screen.getByTestId("nav-badge-/claude-usage")).toHaveTextContent("19%");
    expect(screen.getByTestId("nav-badge-/claude-usage")).not.toHaveTextContent("1873");
    // automation → activeCount=5
    expect(screen.getByTestId("nav-badge-/routines")).toHaveTextContent("5");
  });

  it("F2-M4: market badge HIDDEN when 0 alerts (a red '0' alert is noise)", async () => {
    mockPath = "/";
    render(<Sidebar onToggleCollapse={() => {}} />);
    // default mock: triggers [] → 0 alerts → badge hidden
    await waitFor(() => expect(screen.getByTestId("nav-badge-/projects")).toHaveTextContent("7"));
    expect(screen.queryByTestId("nav-badge-/market")).toBeNull();
  });

  it("F2-M4: market badge SHOWN with the alert count when >0", async () => {
    mockPath = "/";
    getMarket.mockResolvedValue({ success: true, data: { quotes: [], triggers: [{}, {}, {}], macro: [], alertHistory: [] } });
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-badge-/market")).toHaveTextContent("3"));
  });

  it("UI-CLEANUP R2 (distinguishing-case): a forced fetch-fail shows HONEST '—', NOT the stale ghost (71%/4)", async () => {
    mockPath = "/";
    getProjects.mockRejectedValue(new Error("down"));
    getClaudeUsage.mockRejectedValue(new Error("down"));
    render(<Sidebar onToggleCollapse={() => {}} />);
    // R2: the fallbacks are now "—" — a failed live-fetch must NEVER show the stale
    // hardcoded number. The "71%" claude badge was the cap-overflow ghost (neutralized).
    await waitFor(() => expect(screen.getByTestId("nav-badge-/projects")).toHaveTextContent("—"));
    expect(screen.getByTestId("nav-badge-/projects")).not.toHaveTextContent("4");
    expect(screen.getByTestId("nav-badge-/claude-usage")).toHaveTextContent("—");
    expect(screen.getByTestId("nav-badge-/claude-usage")).not.toHaveTextContent("71%");
    // sidebar never blocks — the rest of the nav still renders
    expect(screen.getByTestId("nav-badge-/routines")).toBeInTheDocument();
  });

  it("does NOT render any AI route (ARCH §11 — embedded AI dropped)", async () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    expect(container.querySelector('a[href="/ai"]')).toBeNull();
    expect(screen.queryByText(/AI Brain/i)).toBeNull();
    await settleSidebar();
  });

  // ── FE-1: user-customizable sidebar (hide/show + reorder via prefs) ──
  it("FE-1: hides a module link when prefs hide its route (localStorage)", async () => {
    mockPath = "/";
    localStorage.setItem("lifeos.sidebar", JSON.stringify({ hidden: ["/market"], order: {} }));
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    // prefs load post-mount → /market link removed; settle badges first
    await settleSidebar();
    await waitFor(() => expect(container.querySelector('a[href="/market"]')).toBeNull());
    // a non-hidden route still present
    expect(container.querySelector('a[href="/finance"]')).toBeTruthy();
    localStorage.clear();
  });

  it("FE-1: opens the customizer panel from the customize button", async () => {
    mockPath = "/";
    const user = userEvent.setup();
    render(<Sidebar onToggleCollapse={() => {}} />);
    await settleSidebar();
    expect(screen.queryByTestId("sbcust-panel")).toBeNull();
    await user.click(screen.getByTestId("sb-customize"));
    await waitFor(() => expect(screen.getByTestId("sbcust-panel")).toBeTruthy());
  });

  it("FE-1: disabling a whole MODULE hides its entire nav group (module registry)", async () => {
    mockPath = "/";
    // disable the "Tài chính" module → finance/portfolio/exchange/journal/market all gone
    localStorage.setItem("lifeos.modules", JSON.stringify({ disabled: ["Tài chính"], order: [] }));
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await settleSidebar();
    await waitFor(() => {
      expect(container.querySelector('a[href="/finance"]')).toBeNull();
      expect(container.querySelector('a[href="/market"]')).toBeNull();
    });
    // the section label is gone too
    const secs = Array.from(container.querySelectorAll(".sb-sec")).map((e) => e.textContent);
    expect(secs).not.toContain("Tài chính");
    // a different module's routes still present
    expect(container.querySelector('a[href="/wiki"]')).toBeTruthy();
    localStorage.clear();
  });

  it("FE-1: pinned core modules (Cấu hình/Settings) can never be disabled — route stays", async () => {
    mockPath = "/";
    // even if a stale pref lists a pinned module, it's never dropped
    localStorage.setItem("lifeos.modules", JSON.stringify({ disabled: ["Cấu hình", "Tổng quan"], order: [] }));
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await settleSidebar();
    expect(container.querySelector('a[href="/settings"]')).toBeTruthy();
    expect(container.querySelector('a[href="/"]')).toBeTruthy();
    localStorage.clear();
  });

  it("FE-1: hiding a module in the customizer updates the LIVE sidebar in the same tab (no reload)", async () => {
    // Regression guard: the live Sidebar and the customizer each call useSidebarPrefs
    // (two instances). A toggle in the panel must broadcast so the live nav updates
    // immediately — caught in Chrome (the live links didn't change without a reload).
    mockPath = "/";
    const user = userEvent.setup();
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    await settleSidebar();
    // /market link present initially
    expect(container.querySelector('a[href="/market"]')).toBeTruthy();
    // open customizer + hide /market
    await user.click(screen.getByTestId("sb-customize"));
    await waitFor(() => expect(screen.getByTestId("sbc-toggle-/market")).toBeTruthy());
    await user.click(screen.getByTestId("sbc-toggle-/market"));
    // LIVE sidebar nav link disappears WITHOUT a reload (cross-instance sync)
    await waitFor(() => expect(container.querySelector('a[href="/market"]')).toBeNull());
    localStorage.clear();
  });
});
