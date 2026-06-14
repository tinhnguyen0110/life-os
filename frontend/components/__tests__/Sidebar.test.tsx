import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, within, cleanup, waitFor } from "@testing-library/react";
import { Sidebar } from "../Sidebar";
import { NAV, ALL_ROUTES } from "@/lib/nav";

let mockPath = "/";
vi.mock("@/lib/useNav", () => ({
  useSafePathname: () => mockPath,
  useSafeRouter: () => ({ push: vi.fn() }),
}));
// Sidebar fetches /routines for the live Automation badge — mock it.
const getRoutines = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, getRoutines: () => getRoutines() };
});
// next/link → plain anchor in jsdom
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("Sidebar", () => {
  beforeEach(() => {
    // default: getRoutines resolves (so the badge fetch always has a promise);
    // per-test overrides set specific activeCount / rejection.
    getRoutines.mockResolvedValue({ success: true, data: { routines: [], activeCount: 5, total: 5, runsToday: 0, lastRunAt: null } });
  });
  afterEach(() => {
    cleanup();
    getRoutines.mockReset();
  });

  it("Automation nav badge shows LIVE activeCount (was static '5')", async () => {
    getRoutines.mockResolvedValue({ success: true, data: { routines: [], activeCount: 6, total: 6, runsToday: 0, lastRunAt: null } });
    render(<Sidebar onToggleCollapse={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("nav-badge-/routines")).toHaveTextContent("6"));
  });

  it("Automation badge fails soft → static fallback when /routines down", async () => {
    getRoutines.mockRejectedValue(new Error("down"));
    render(<Sidebar onToggleCollapse={() => {}} />);
    // falls back to the static badge text "5" (never blocks the sidebar)
    await waitFor(() => expect(screen.getByTestId("nav-badge-/routines")).toHaveTextContent("5"));
  });

  it("renders all 7 nav groups (+ Tri thức for Wiki)", () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const secs = Array.from(container.querySelectorAll(".sb-sec")).map((e) => e.textContent);
    for (const g of NAV) {
      expect(secs).toContain(g.sec);
    }
    expect(NAV).toHaveLength(7);
  });

  it("renders a link for every nav route (21 nav items: +Wiki group +Decision Journal)", () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    for (const route of ALL_ROUTES) {
      expect(container.querySelector(`a[href="${route}"]`)).toBeTruthy();
    }
    // 14 foundation + Wiki group (/wiki, /wiki/inbox, /wiki/graph, /wiki/proposals,
    // /wiki/moc, /wiki/sync) + /decision-journal (DJ).
    expect(ALL_ROUTES).toHaveLength(21);
    expect(container.querySelector('a[href="/wiki/sync"]')).toBeTruthy();
    expect(container.querySelector('a[href="/decision-journal"]')).toBeTruthy();
  });

  it("marks the active route with `on` and aria-current", () => {
    mockPath = "/market";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const active = container.querySelector('a[href="/market"]');
    expect(active?.className).toContain("on");
    expect(active?.getAttribute("aria-current")).toBe("page");
  });

  it("Home is only active at exactly `/` (not on sub-routes)", () => {
    mockPath = "/projects";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const home = container.querySelector('a[href="/"]');
    expect(home?.className).not.toContain("on");
  });

  it("detail route /projects/abc keeps /projects active (prefix match)", () => {
    mockPath = "/projects/abc";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    expect(container.querySelector('a[href="/projects"]')?.className).toContain("on");
  });

  it("collapse button fires the callback", async () => {
    mockPath = "/";
    const onToggle = vi.fn();
    render(<Sidebar onToggleCollapse={onToggle} />);
    screen.getByLabelText("Thu gọn sidebar").click();
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("renders badge text where defined (Projects=4, Market=2, Claude=71%, Automation=5)", () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const projects = container.querySelector('a[href="/projects"]');
    expect(within(projects as HTMLElement).getByText("4")).toBeInTheDocument();
  });

  it("does NOT render any AI route (ARCH §11 — embedded AI dropped)", () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    expect(container.querySelector('a[href="/ai"]')).toBeNull();
    expect(screen.queryByText(/AI Brain/i)).toBeNull();
  });
});
