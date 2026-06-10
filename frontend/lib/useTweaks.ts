"use client";
/* ============================================================
   useTweaks — S13 appearance state. Pure client-side (no backend):
   reads localStorage["lifeos.tweaks"] once on mount, applies the CSS-var
   overrides to :root, and on every setter call re-applies + persists.
   The no-flash inline script in layout.tsx <head> applies the SAME vars
   pre-paint so first render is already themed; this hook then takes over
   for interactive changes and keeps React state in sync.
   ============================================================ */
import { useCallback, useEffect, useRef, useState } from "react";
import { DEFAULT_TWEAKS, applyTweaks, loadTweaks, saveTweaks, type Tweaks } from "@/lib/tweaks";

export interface UseTweaks {
  tweaks: Tweaks;
  /** Patch one or more fields; re-applies CSS vars + persists immediately. */
  set: (patch: Partial<Tweaks>) => void;
}

export function useTweaks(): UseTweaks {
  // SSR + first client render must match: start from DEFAULT_TWEAKS (same value
  // the no-flash script falls back to). Real persisted value loads in the mount
  // effect, after hydration — avoids a hydration mismatch.
  const [tweaks, setTweaks] = useState<Tweaks>(DEFAULT_TWEAKS);
  const loaded = useRef(false);

  useEffect(() => {
    const stored = loadTweaks();
    loaded.current = true;
    setTweaks(stored);
    applyTweaks(stored);
  }, []);

  const set = useCallback((patch: Partial<Tweaks>) => {
    setTweaks((prev) => {
      const next = { ...prev, ...patch };
      applyTweaks(next);
      saveTweaks(next);
      return next;
    });
  }, []);

  return { tweaks, set };
}
