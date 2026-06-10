/**
 * S13 T3 pre-scaffold — TweaksPanel component tests.
 * Tests: panel renders 6 swatches + 2 bg buttons + 2 effect toggles; interactivity.
 *
 * TweaksPanel uses a named export (not default) and testids per plan_sprint_13.md T2:
 *   tweaks-panel, tw-swatch-<key>, tw-bg-cool, tw-bg-warm, tw-glow, tw-scan, tweaks-close
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Mock useTweaks hook — we test the PANEL's rendering, not the hook internals.
// useTweaks returns { tweaks, set } (object, not array).
const mockSet = vi.fn();
vi.mock("@/lib/useTweaks", () => ({
  useTweaks: () => ({
    tweaks: { theme: "copper", bg: "cool", glow: true, scanline: false },
    set: mockSet,
  }),
}));

import { TweaksPanel } from "@/components/TweaksPanel";

const defaultProps = {
  open: true,
  onClose: vi.fn(),
};

afterEach(() => {
  vi.clearAllMocks();
  document.body.classList.remove("scanline");
  document.documentElement.style.cssText = "";
});

describe("TweaksPanel — structural integrity", () => {
  it("renders the panel container with testid 'tweaks-panel'", () => {
    render(<TweaksPanel {...defaultProps} />);
    expect(screen.getByTestId("tweaks-panel")).toBeInTheDocument();
  });

  it("renders exactly 6 theme swatches with tw-swatch-<key> testids", () => {
    render(<TweaksPanel {...defaultProps} />);
    // Plan T2 testids: tw-swatch-copper, tw-swatch-amber, tw-swatch-solar,
    //                   tw-swatch-cyan, tw-swatch-violet, tw-swatch-rose
    const swatchKeys = ["copper", "amber", "solar", "cyan", "violet", "rose"];
    for (const k of swatchKeys) {
      expect(screen.getByTestId(`tw-swatch-${k}`), `swatch tw-swatch-${k} missing`).toBeInTheDocument();
    }
  });

  it("renders exactly 2 BG buttons: tw-bg-cool and tw-bg-warm", () => {
    render(<TweaksPanel {...defaultProps} />);
    expect(screen.getByTestId("tw-bg-cool")).toBeInTheDocument();
    expect(screen.getByTestId("tw-bg-warm")).toBeInTheDocument();
  });

  it("renders glow toggle (tw-glow) and scanline toggle (tw-scan)", () => {
    render(<TweaksPanel {...defaultProps} />);
    expect(screen.getByTestId("tw-glow")).toBeInTheDocument();
    expect(screen.getByTestId("tw-scan")).toBeInTheDocument();
  });

  it("renders close button (tweaks-close)", () => {
    render(<TweaksPanel {...defaultProps} />);
    expect(screen.getByTestId("tweaks-close")).toBeInTheDocument();
  });

  it("shows VI section labels: Tông màu, Nền, Hiệu ứng", () => {
    render(<TweaksPanel {...defaultProps} />);
    expect(screen.getByText(/Tông màu/)).toBeInTheDocument();
    expect(screen.getByText(/Nền/)).toBeInTheDocument();
    expect(screen.getByText(/Hiệu ứng/)).toBeInTheDocument();
  });

  it("shows BG button labels: Trung tính and Ấm", () => {
    render(<TweaksPanel {...defaultProps} />);
    expect(screen.getByTestId("tw-bg-cool")).toHaveTextContent(/Trung tính/);
    expect(screen.getByTestId("tw-bg-warm")).toHaveTextContent(/Ấm/);
  });

  it("renders footer with current theme name + bg label (Đang dùng: … · nền trung tính)", () => {
    render(<TweaksPanel {...defaultProps} />);
    // Footer shows "Đang dùng: <name> · nền trung tính" (bg=cool → trung tính)
    const panel = screen.getByTestId("tweaks-panel");
    expect(panel.textContent).toMatch(/Đang dùng/);
    expect(panel.textContent).toMatch(/trung tính/i);
  });
});

describe("TweaksPanel — not rendered when closed", () => {
  it("panel is not in DOM when open=false (component returns null)", () => {
    render(<TweaksPanel open={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId("tweaks-panel")).toBeNull();
  });
});

describe("TweaksPanel — interactions call set()", () => {
  it("clicking a swatch calls set() with the correct theme key", async () => {
    const user = userEvent.setup();
    render(<TweaksPanel {...defaultProps} />);
    await user.click(screen.getByTestId("tw-swatch-violet"));
    expect(mockSet).toHaveBeenCalledWith(expect.objectContaining({ theme: "violet" }));
  });

  it("clicking tw-bg-warm calls set() with bg:'warm'", async () => {
    const user = userEvent.setup();
    render(<TweaksPanel {...defaultProps} />);
    await user.click(screen.getByTestId("tw-bg-warm"));
    expect(mockSet).toHaveBeenCalledWith(expect.objectContaining({ bg: "warm" }));
  });

  it("clicking tw-bg-cool calls set() with bg:'cool'", async () => {
    const user = userEvent.setup();
    render(<TweaksPanel {...defaultProps} />);
    await user.click(screen.getByTestId("tw-bg-cool"));
    expect(mockSet).toHaveBeenCalledWith(expect.objectContaining({ bg: "cool" }));
  });

  it("close button (tweaks-close) calls onClose", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<TweaksPanel open={true} onClose={onClose} />);
    await user.click(screen.getByTestId("tweaks-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
