"use client";
/* ============================================================
   <Popover> (#142-P1) — a shared anchored-overlay primitive for the per-card /
   per-folder ⋯ ops menus (A1 tracing TimelineRow, A2 tracing NoteCard, A3 wiki
   folder). Fixes the "wrong located" bug: the old menus used
   `position:absolute; right:0; top:100%` relative to a parent, so they (a) overflowed
   off-screen near a viewport edge and (b) were CLIPPED by an overflow:hidden/auto
   ancestor (the wiki explorer tree scrolls → A3 clipped).

   Fix = portal the floating panel to <body> (escapes EVERY clip ancestor) + position
   it with viewport-edge collision via useAnchoredPosition (flip up at the bottom edge,
   shift in at the left/right edges) + track on scroll/resize + close on outside-click
   (mousedown, counting BOTH the anchor and the portaled panel as "inside") + Escape.

   API: <Popover open anchorRef onClose>{menu content}</Popover>
   - `open`       — render the panel when true.
   - `anchorRef`  — ref to the trigger element (the ⋯ button) to anchor + collision against.
   - `onClose`    — called on outside-click / Escape (the parent flips its open state).
   - children     — the menu contents (unchanged from the legacy inline menu).

   z-index 600 = above every panel/modal (PrivacyReveal 500, panels 400) so a transient
   menu is always the topmost thing. ONE constant (POPOVER_Z).

   NOTE on visibility: jsdom can't compute the real position, so the unit tests cover
   open/close/portal-mount + the collision MATH (solveAnchoredPosition); the live-Chrome
   edge-position check is the load-bearing gate (memory:
   jsdom-cant-see-css-visibility-live-chrome-is-the-gate).
   ============================================================ */
import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { useAnchoredPosition } from "@/lib/useAnchoredPosition";

/** the single z-index for popover menus — above panels (400) + modals (500). */
export const POPOVER_Z = 600;

export function Popover({
  open,
  anchorRef,
  onClose,
  className,
  role = "menu",
  testId,
  children,
}: {
  open: boolean;
  anchorRef: RefObject<HTMLElement>;
  onClose: () => void;
  /** class applied to the floating panel (e.g. "tl-ops-menu" / "wex-ops-menu" — keeps
   *  the existing menu styling; the positional props are overridden inline). */
  className?: string;
  role?: string;
  testId?: string;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const coords = useAnchoredPosition(anchorRef, panelRef, open);

  // keep onClose fresh without re-subscribing.
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  // outside-click (mousedown) + Escape close. The panel is portaled OUT of the
  // anchor's subtree, so "inside" = inside the panel OR inside the anchor (the ⋯
  // button) — a click on the trigger toggles via its own handler, not a close here.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      const t = e.target as Node;
      const p = panelRef.current;
      const a = anchorRef.current;
      if (p && p.contains(t)) return;
      if (a && a.contains(t)) return;
      closeRef.current();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeRef.current();
    }
    // defer the mousedown attach a tick so the SAME click that opened the menu
    // doesn't immediately close it (same guard as useClickAway).
    const id = setTimeout(() => document.addEventListener("mousedown", onDown), 0);
    document.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(id);
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, anchorRef]);

  // SSR / pre-mount guard: createPortal needs document; render nothing on the server.
  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={panelRef}
      className={className}
      role={role}
      data-testid={testId}
      style={{
        position: "fixed",
        top: coords?.top ?? 0,
        left: coords?.left ?? 0,
        zIndex: POPOVER_Z,
        // until measured, keep it invisible so it doesn't flash at 0,0 (top-left).
        visibility: coords ? "visible" : "hidden",
        // the portaled panel positions itself — neutralize any inherited absolute offsets.
        right: "auto",
        bottom: "auto",
        margin: 0,
      }}
    >
      {children}
    </div>,
    document.body,
  );
}
