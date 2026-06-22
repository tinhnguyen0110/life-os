import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import { useRef } from "react";
import { Popover, POPOVER_Z } from "../Popover";
import { solveAnchoredPosition, VIEWPORT_MARGIN } from "@/lib/useAnchoredPosition";

afterEach(cleanup);

/* ============================================================================
   #142-P1 — <Popover> + the collision math. jsdom CANNOT compute real layout
   (getBoundingClientRect returns 0s, no paint) — so the POSITIONAL correctness at a
   viewport edge is the live-Chrome gate. Here we unit-test (a) the pure collision
   solver near each edge (real arithmetic, jsdom-independent), and (b) the component's
   open/close/portal-mount + outside-click/Escape close behavior.
   ============================================================================ */

describe("solveAnchoredPosition — viewport-edge collision (pure math)", () => {
  const WIN = { innerWidth: 1000, innerHeight: 800 };
  const PANEL = { width: 160, height: 120 };

  it("default placement: below the trigger, right edges aligned", () => {
    // trigger mid-screen, plenty of room → top=anchor.bottom, left=anchor.right-panelW.
    const anchor = { top: 100, bottom: 120, left: 400, right: 460 };
    const { top, left } = solveAnchoredPosition(anchor, PANEL, WIN);
    expect(top).toBe(120);            // anchor.bottom
    expect(left).toBe(460 - 160);     // anchor.right - panelWidth = 300
  });

  it("BOTTOM edge → flips ABOVE the trigger", () => {
    // anchor near the bottom: bottom=780, panel height 120 → 780+120=900 > 800 → flip up.
    const anchor = { top: 760, bottom: 780, left: 400, right: 460 };
    const { top } = solveAnchoredPosition(anchor, PANEL, WIN);
    expect(top).toBe(760 - 120);      // anchor.top - panelHeight = 640 (above)
  });

  it("RIGHT edge → shifts LEFT to stay on-screen", () => {
    // anchor.right=995 → default left=995-160=835; 835+160=995 > 1000-8 → shift left.
    const anchor = { top: 100, bottom: 120, left: 935, right: 995 };
    const { left } = solveAnchoredPosition(anchor, PANEL, WIN);
    expect(left).toBe(1000 - 160 - VIEWPORT_MARGIN); // innerWidth - panelW - margin = 832
  });

  it("LEFT edge → shifts RIGHT to the margin", () => {
    // anchor near the left: right=120 → default left=120-160=-40 (<8) → clamp to margin.
    const anchor = { top: 100, bottom: 120, left: 60, right: 120 };
    const { left } = solveAnchoredPosition(anchor, PANEL, WIN);
    expect(left).toBe(VIEWPORT_MARGIN); // 8
  });

  it("keeps a 8px margin from the bottom on the default (no-collision) case", () => {
    // exactly fits: bottom=600, +120=720 < 800-8 → stays below.
    const anchor = { top: 580, bottom: 600, left: 400, right: 460 };
    const { top } = solveAnchoredPosition(anchor, PANEL, WIN);
    expect(top).toBe(600);
  });
});

function Harness({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLButtonElement | null>(null);
  return (
    <div>
      <button ref={ref} data-testid="anchor">⋯</button>
      <Popover open={open} anchorRef={ref} onClose={onClose} className="tl-ops-menu" testId="pop">
        <button data-testid="item" onClick={onClose}>Item</button>
      </Popover>
      <button data-testid="outside">outside</button>
    </div>
  );
}

describe("<Popover> — mount / portal / close behavior", () => {
  it("renders nothing when closed", () => {
    render(<Harness open={false} onClose={() => {}} />);
    expect(screen.queryByTestId("pop")).toBeNull();
  });

  it("portals the panel to document.body when open (escapes the anchor's subtree)", () => {
    const { container } = render(<Harness open onClose={() => {}} />);
    const panel = screen.getByTestId("pop");
    expect(panel).toBeInTheDocument();
    // portaled → NOT inside the component's own container subtree.
    expect(container.contains(panel)).toBe(false);
    expect(document.body.contains(panel)).toBe(true);
    // fixed-position + the single z-index constant.
    expect(panel).toHaveStyle({ position: "fixed", zIndex: String(POPOVER_Z) });
  });

  it("renders the menu contents (items clickable)", () => {
    const onClose = vi.fn();
    render(<Harness open onClose={onClose} />);
    fireEvent.click(screen.getByTestId("item"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on an outside mousedown (the click-away A3 previously lacked)", () => {
    // the listener attaches on a deferred setTimeout(0) (so the OPENING click doesn't
    // immediately close it) — fake timers BEFORE render, then flush, so it's attached.
    vi.useFakeTimers();
    const onClose = vi.fn();
    try {
      render(<Harness open onClose={onClose} />);
      // flush the deferred addEventListener + the rAF position re-measure (wrap in act
      // so the coords state-update doesn't warn).
      act(() => { vi.runAllTimers(); });
      fireEvent.mouseDown(screen.getByTestId("outside"));
      expect(onClose).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("does NOT close on a mousedown inside the panel", () => {
    const onClose = vi.fn();
    render(<Harness open onClose={onClose} />);
    fireEvent.mouseDown(screen.getByTestId("item"));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<Harness open onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
