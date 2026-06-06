/* ============================================================
   Icons — PORTED VERBATIM from mock shell.js ICONS map.
   Stroke 1.8 line icons; sizing comes from CSS (.sb-item svg etc.).
   AI sparkle icon ('i-ai') intentionally omitted — no embedded AI (ARCH §11).
   ============================================================ */
import type { ReactElement } from "react";

const C = { fill: "none", stroke: "currentColor", strokeWidth: 1.8 } as const;

export type IconKey =
  | "i-home" | "i-proj" | "i-grave" | "i-fin" | "i-pie" | "i-journal"
  | "i-mkt" | "i-cpu" | "i-note" | "i-set" | "i-bolt" | "i-pulse"
  | "i-refresh" | "i-chevron" | "i-bell" | "i-doc";

const PATHS: Record<IconKey, ReactElement> = {
  "i-home": <><path {...C} d="M3 11l9-7 9 7" /><path {...C} d="M5 10v10h14V10" /></>,
  "i-proj": <path {...C} d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />,
  "i-grave": <><path {...C} d="M5 21V11a7 7 0 0 1 14 0v10z" /><path {...C} d="M9 21v-4h6v4" /></>,
  "i-fin": <><path {...C} d="M4 19h16" /><path {...C} d="M6 16l4-5 3 3 5-7" /></>,
  "i-pie": <><path {...C} d="M12 3v9l7 5" /><circle {...C} cx="12" cy="12" r="9" /></>,
  "i-journal": <><path {...C} d="M5 4h11l3 3v13H5z" /><path {...C} d="M9 9h7M9 13h7M9 17h4" /></>,
  "i-mkt": <path {...C} d="M3 12h4l2 6 4-14 2 8h6" />,
  "i-cpu": <><rect {...C} x="7" y="7" width="10" height="10" rx="1.5" /><path {...C} d="M10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3" /></>,
  "i-note": <><path {...C} d="M6 3h9l5 5v13H6z" /><path {...C} d="M14 3v6h6M9 13h6M9 17h6" /></>,
  "i-doc": <><path {...C} d="M6 3h9l5 5v13H6z" /><path {...C} d="M14 3v6h6M9 13h6M9 17h4" /></>,
  "i-set": <><circle {...C} cx="12" cy="12" r="3" /><path {...C} d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2" /></>,
  "i-bolt": <path {...C} d="M13 2L4 14h7l-1 8 9-12h-7z" />,
  "i-pulse": <path {...C} d="M3 12h4l2-7 4 16 2-9h6" />,
  "i-refresh": <><path {...C} d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path {...C} d="M21 4v4h-4" /></>,
  "i-chevron": <path fill="none" stroke="currentColor" strokeWidth={2} d="M15 6l-6 6 6 6" />,
  "i-bell": <><path {...C} d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path {...C} d="M13.7 21a2 2 0 0 1-3.4 0" /></>,
};

export function Icon({ name, className }: { name: IconKey; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
