import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import { Sidebar } from "../Sidebar";
import { NAV, ALL_ROUTES } from "@/lib/nav";

let mockPath = "/";
vi.mock("@/lib/useNav", () => ({
  useSafePathname: () => mockPath,
  useSafeRouter: () => ({ push: vi.fn() }),
}));
// next/link → plain anchor in jsdom
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("Sidebar", () => {
  afterEach(() => cleanup());

  it("renders all 6 nav groups", () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    const secs = Array.from(container.querySelectorAll(".sb-sec")).map((e) => e.textContent);
    for (const g of NAV) {
      expect(secs).toContain(g.sec);
    }
    expect(NAV).toHaveLength(6);
  });

  it("renders a link for every nav route (13 nav items → 14 screens incl Home)", () => {
    mockPath = "/";
    const { container } = render(<Sidebar onToggleCollapse={() => {}} />);
    for (const route of ALL_ROUTES) {
      expect(container.querySelector(`a[href="${route}"]`)).toBeTruthy();
    }
    // 13 nav items + the settings user link
    expect(ALL_ROUTES).toHaveLength(13);
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
