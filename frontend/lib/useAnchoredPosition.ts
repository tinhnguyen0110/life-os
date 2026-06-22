"use client";
/* ============================================================
   useAnchoredPosition (#142-P1) — compute viewport-fixed {top,left} for a floating
   panel anchored to a trigger element, with viewport-edge COLLISION (flip up when it
   would overflow the bottom; shift in when it would overflow left/right). Used by
   <Popover> for the per-card/per-folder ⋯ menus that previously rendered with
   `position:absolute; right:0; top:100%` and clipped off-screen / inside an
   overflow:hidden ancestor.

   The panel is portaled to <body>, so `position:fixed` coords == viewport coords
   (no ancestor offset to subtract). We recompute on open + scroll (capture, to catch
   ANY ancestor scrolling) + resize, so the panel tracks its trigger.

   The math is pure (a function of two rects + the window box) → jsdom-testable by
   mocking getBoundingClientRect + window.inner*; the VISUAL correctness (does it
   actually land on-screen at a viewport edge) is the live-Chrome gate, since jsdom
   can't compute real layout (memory: jsdom-cant-see-css-visibility-live-chrome-is-the-gate).
   ============================================================ */
import { useCallback, useLayoutEffect, useRef, useState, type RefObject } from "react";

/** viewport margin kept between the panel and the window edge. */
export const VIEWPORT_MARGIN = 8;

export interface AnchorCoords {
  top: number;
  left: number;
}

/** Pure collision solver — exported for unit testing. Given the trigger rect, the
 *  panel's measured size, and the window box, return the on-screen {top,left} for a
 *  `position:fixed` panel.
 *  Default placement mirrors the old `right:0; top:100%` (below the trigger, right
 *  edges aligned); then flip/shift to stay within [margin, inner-margin]. */
export function solveAnchoredPosition(
  anchor: { top: number; bottom: number; left: number; right: number },
  panel: { width: number; height: number },
  win: { innerWidth: number; innerHeight: number },
  margin = VIEWPORT_MARGIN,
): AnchorCoords {
  // default: below, right-aligned to the trigger (matches the legacy menu placement).
  let top = anchor.bottom;
  let left = anchor.right - panel.width;

  // vertical collision: would overflow the bottom → flip ABOVE the trigger.
  if (top + panel.height > win.innerHeight - margin) {
    const above = anchor.top - panel.height;
    // only flip if there's more room above (else keep below, clamped) — but per spec
    // the bottom-overflow case flips up; clamp to margin so it never goes off the top.
    top = Math.max(margin, above);
  }

  // horizontal collision: keep within [margin, innerWidth - panelWidth - margin].
  if (left < margin) left = margin;
  if (left + panel.width > win.innerWidth - margin) {
    left = win.innerWidth - panel.width - margin;
  }
  // final clamp (a panel wider than the viewport can't satisfy both → pin to margin).
  if (left < margin) left = margin;

  return { top, left };
}

/**
 * Track an on-screen anchored position for `panelRef`, anchored to `anchorRef`,
 * while `open`. Returns the coords (null until measured — the caller renders the
 * panel hidden/at the measured coords to avoid a flash at 0,0).
 */
export function useAnchoredPosition(
  anchorRef: RefObject<HTMLElement>,
  panelRef: RefObject<HTMLElement>,
  open: boolean,
): AnchorCoords | null {
  const [coords, setCoords] = useState<AnchorCoords | null>(null);
  // avoid a stale closure on the recompute callback.
  const compute = useCallback(() => {
    const a = anchorRef.current;
    const p = panelRef.current;
    if (!a) return;
    const ar = a.getBoundingClientRect();
    // panel size: use the measured panel if mounted, else a sane min so first paint
    // is close (then we re-measure on the next frame).
    const pw = p?.offsetWidth || 160;
    const ph = p?.offsetHeight || 0;
    setCoords(
      solveAnchoredPosition(
        { top: ar.top, bottom: ar.bottom, left: ar.left, right: ar.right },
        { width: pw, height: ph },
        { innerWidth: window.innerWidth, innerHeight: window.innerHeight },
      ),
    );
  }, [anchorRef, panelRef]);

  // keep the latest compute without re-subscribing listeners each render.
  const computeRef = useRef(compute);
  computeRef.current = compute;

  useLayoutEffect(() => {
    if (!open) {
      setCoords(null);
      return;
    }
    // measure now (layout effect → after DOM mutation, before paint) then once more
    // on the next frame so the panel's real size is known (first measure may be ph=0).
    computeRef.current();
    const raf = requestAnimationFrame(() => computeRef.current());
    const onScrollResize = () => computeRef.current();
    // capture:true catches scrolling on ANY ancestor (the wiki explorer tree scrolls).
    window.addEventListener("scroll", onScrollResize, true);
    window.addEventListener("resize", onScrollResize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScrollResize, true);
      window.removeEventListener("resize", onScrollResize);
    };
  }, [open]);

  return coords;
}
