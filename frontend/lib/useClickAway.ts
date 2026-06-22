"use client";
/* ============================================================
   useClickAway — call `onAway` when a pointer-down lands OUTSIDE the ref'd element.
   #137-T2 (UX): per-card ⋯ menus / inline editors should close on an outside click,
   not force re-clicking the exact opener icon. `active` gates the listener so it's only
   attached while the menu/editor is open (no global cost when closed).
   ============================================================ */
import { useEffect, useRef } from "react";

export function useClickAway<T extends HTMLElement>(active: boolean, onAway: () => void) {
  const ref = useRef<T | null>(null);
  // keep the latest callback without re-subscribing every render.
  const cb = useRef(onAway);
  cb.current = onAway;

  useEffect(() => {
    if (!active) return;
    function handle(e: MouseEvent) {
      const el = ref.current;
      if (el && !el.contains(e.target as Node)) cb.current();
    }
    // mousedown (not click) so it fires before a re-render swallows the target.
    // defer the attach a tick so the SAME click that opened the menu doesn't immediately close it.
    const id = setTimeout(() => document.addEventListener("mousedown", handle), 0);
    return () => { clearTimeout(id); document.removeEventListener("mousedown", handle); };
  }, [active]);

  return ref;
}
