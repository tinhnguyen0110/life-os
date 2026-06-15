"use client";
/* ============================================================
   SidebarCustomizer (FE-1) — floating panel to customize the sidebar:
   per-module show/hide toggle + up/down reorder + reset-to-default.
   Mirrors TweaksPanel chrome (backdrop + bottom-right floating card, Esc-to-close).
   Driven by useSidebarPrefs() (localStorage-backed).

   Renders ALL nav items (including hidden ones) grouped by section, working off
   the canonical NAV + the user's prefs (the LIVE Sidebar renders the *applied*
   filtered list; this panel is the full editable surface). Reorder operates on
   the effective per-section order so up/down reflects what the user sees.
   ============================================================ */
import { useEffect } from "react";
import { NAV } from "@/lib/nav";
import { Icon } from "@/lib/icons";
import { useSidebarPrefs } from "@/lib/useSidebarPrefs";
import { applyPrefs, PINNED_ROUTES } from "@/lib/sidebar-prefs";

export function SidebarCustomizer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { prefs, toggleHidden, move, reset } = useSidebarPrefs();

  // Esc closes the panel (matches TweaksPanel).
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const hidden = new Set(prefs.hidden);
  // Effective ordered NAV (applyPrefs with an EMPTY hidden set → keeps every item
  // visible but in the user's chosen order, so the panel lists hidden items too
  // and lets the user re-enable them).
  const ordered = applyPrefs({ hidden: [], order: prefs.order }, NAV);
  const hiddenCount = prefs.hidden.length;

  return (
    <>
      <div id="sbcust-backdrop" onClick={onClose} data-testid="sbcust-backdrop" />
      <div id="sbcust" className="show" role="dialog" aria-label="Tùy chỉnh sidebar" data-testid="sbcust-panel">
        <div className="sbc-head">
          <span className="dotlogo" />
          <b>Tùy chỉnh sidebar</b>
          <button type="button" className="x" onClick={onClose} aria-label="Đóng" data-testid="sbcust-close">✕</button>
        </div>

        <div className="sbc-body">
          <div className="sbc-intro">
            Ẩn/hiện hoặc sắp xếp các mục. Lưu trên máy này.
            {hiddenCount > 0 && <> · <b>{hiddenCount}</b> đang ẩn</>}
          </div>

          {ordered.map((group) => (
            <div key={group.sec} data-testid={`sbc-group-${group.sec}`}>
              <div className="sbc-sec">{group.sec}</div>
              {group.items.map((item, idx) => {
                const pinned = PINNED_ROUTES.includes(item.route);
                const isHidden = hidden.has(item.route);
                return (
                  <div
                    key={item.route}
                    className={`sbc-row${isHidden ? " off" : ""}`}
                    data-testid={`sbc-row-${item.route}`}
                    data-hidden={isHidden ? "1" : "0"}
                  >
                    <span className="sbc-ic"><Icon name={item.icon} /></span>
                    <span className="sbc-lbl">{item.label}</span>

                    {/* reorder up/down within section */}
                    <div className="sbc-move">
                      <button
                        type="button"
                        className="sbc-mbtn"
                        aria-label={`Đưa "${item.label}" lên`}
                        title="Lên"
                        disabled={idx === 0}
                        onClick={() => move(group.sec, item.route, "up")}
                        data-testid={`sbc-up-${item.route}`}
                      >▲</button>
                      <button
                        type="button"
                        className="sbc-mbtn"
                        aria-label={`Đưa "${item.label}" xuống`}
                        title="Xuống"
                        disabled={idx === group.items.length - 1}
                        onClick={() => move(group.sec, item.route, "down")}
                        data-testid={`sbc-down-${item.route}`}
                      >▼</button>
                    </div>

                    {/* show/hide toggle — pinned routes show a locked marker instead */}
                    {pinned ? (
                      <span className="sbc-pin" title="Luôn hiển thị" data-testid={`sbc-pin-${item.route}`}>cố định</span>
                    ) : (
                      <div
                        className={`toggle${!isHidden ? " on" : ""}`}
                        role="switch"
                        aria-checked={!isHidden}
                        aria-label={`Hiện "${item.label}"`}
                        tabIndex={0}
                        data-testid={`sbc-toggle-${item.route}`}
                        onClick={() => toggleHidden(item.route)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleHidden(item.route); }
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          <div className="sbc-foot">
            <button type="button" className="btn sm ghost" onClick={reset} data-testid="sbcust-reset">
              <Icon name="i-refresh" /> Khôi phục mặc định
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

export default SidebarCustomizer;
