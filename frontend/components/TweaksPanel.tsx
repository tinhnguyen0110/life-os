"use client";
/* ============================================================
   TweaksPanel (S13) — appearance customizer. Markup ported VERBATIM from mock
   shell.js buildTweaksPanel (lines 187–215): 6-swatch theme grid, 2-button BG
   segment (Trung tính / Ấm), Glow + Scanline toggles, live footer.
   Driven by useTweaks() (localStorage-backed). Renders as a floating panel +
   backdrop; opened from the Settings "Mở Tweaks" button (the mock's global FAB
   is dropped — entry point is Settings per S13 dispatch).
   ============================================================ */
import { useEffect } from "react";
import { THEMES, BG, type ThemeKey, type BgKey } from "@/lib/tweaks";
import { useTweaks } from "@/lib/useTweaks";

const THEME_ENTRIES = Object.entries(THEMES) as [ThemeKey, (typeof THEMES)[ThemeKey]][];
const BG_OPTS: { key: BgKey; label: string }[] = [
  { key: "cool", label: "Trung tính" },
  { key: "warm", label: "Ấm (warm)" },
];

export function TweaksPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { tweaks, set } = useTweaks();

  // Esc closes the panel (matches the mock's close affordance).
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const cur = THEMES[tweaks.theme] ?? THEMES.copper;

  return (
    <>
      <div id="tweaks-backdrop" onClick={onClose} data-testid="tweaks-backdrop" />
      <div id="tweaks" className="show" role="dialog" aria-label="Tweaks giao diện" data-testid="tweaks-panel">
        <div className="tw-head">
          <span className="dotlogo" />
          <b>Tweaks</b>
          <button type="button" className="x" onClick={onClose} aria-label="Đóng" data-testid="tweaks-close">✕</button>
        </div>
        <div className="tw-body">
          {/* ── theme swatches ── */}
          <div className="tw-sec">Tông màu thương hiệu</div>
          <div className="swatches" data-testid="tweaks-swatches">
            {THEME_ENTRIES.map(([k, t]) => (
              <div
                key={k}
                className={`sw${tweaks.theme === k ? " on" : ""}`}
                data-k={k}
                data-testid={`tw-swatch-${k}`}
                onClick={() => set({ theme: k })}
                role="button"
                aria-pressed={tweaks.theme === k}
              >
                <div className="chip" style={{ background: t.grad }} />
                <div className="nm">{t.name}</div>
              </div>
            ))}
          </div>

          {/* ── background ── */}
          <div className="tw-sec">Nền</div>
          <div className="seg2" data-testid="tweaks-bg">
            {BG_OPTS.map((b) => (
              <button
                key={b.key}
                type="button"
                className={tweaks.bg === b.key ? "on" : ""}
                data-bg={b.key}
                data-testid={`tw-bg-${b.key}`}
                onClick={() => set({ bg: b.key })}
              >
                {b.label}
              </button>
            ))}
          </div>

          {/* ── effects ── */}
          <div className="tw-sec">Hiệu ứng</div>
          <div className="togrow">
            <span className="lbl">Glow accent</span>
            <div
              className={`toggle${tweaks.glow ? " on" : ""}`}
              data-testid="tw-glow"
              role="switch"
              aria-checked={tweaks.glow}
              aria-label="Glow accent"
              tabIndex={0}
              onClick={() => set({ glow: !tweaks.glow })}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); set({ glow: !tweaks.glow }); } }}
            />
          </div>
          <div className="togrow">
            <span className="lbl">Scanline (console)</span>
            <div
              className={`toggle${tweaks.scanline ? " on" : ""}`}
              data-testid="tw-scan"
              role="switch"
              aria-checked={tweaks.scanline}
              aria-label="Scanline (console)"
              tabIndex={0}
              onClick={() => set({ scanline: !tweaks.scanline })}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); set({ scanline: !tweaks.scanline }); } }}
            />
          </div>

          {/* ── footer (live summary) ── */}
          <div className="tw-foot" data-testid="tweaks-foot">
            Đang dùng: <b style={{ color: cur.primary }}>{cur.name}</b> · nền {tweaks.bg === "warm" ? "ấm" : "trung tính"}
          </div>
        </div>
      </div>
    </>
  );
}

export default TweaksPanel;
