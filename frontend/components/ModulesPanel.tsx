"use client";
/* ============================================================
   ModulesPanel (FE-1 extended) — the per-user MODULE REGISTRY UI, embedded in
   Settings (S12). Lets the user enable/disable + reorder whole modules so the
   sidebar shows only what they use (the "đừng ngợp" requirement — not every one
   of ~15 modules at once).

   Catalog is DERIVED from NAV (buildCatalog) — no hardcoded list — so a NEW
   module added to NAV auto-appears here, togglable, default ON. Core modules
   (Tổng quan / Cấu hình) are pinned (Settings hosts this panel — disabling it
   would lock the user out).

   Uses the Settings page's existing set-group / set-row styling so it sits
   natively in the Settings layout. Driven by useModulePrefs() (localStorage,
   broadcasts → live sidebar updates instantly).
   ============================================================ */
import { NAV } from "@/lib/nav";
import { Icon } from "@/lib/icons";
import { useModulePrefs } from "@/lib/useSidebarPrefs";
import { buildCatalog, orderCatalog, isModuleEnabled } from "@/lib/module-catalog";

export function ModulesPanel() {
  const { modulePrefs, toggleModule, moveModule, resetModules } = useModulePrefs();

  // Catalog in the user's chosen order (derived from NAV — new modules auto-appear).
  const catalog = orderCatalog(buildCatalog(NAV), modulePrefs.order);
  const enabledCount = catalog.filter((m) => isModuleEnabled(modulePrefs, m.key)).length;

  return (
    <div>
      <div className="kicker" style={{ marginBottom: 10 }}>
        Modules <span className="hint" style={{ fontWeight: 400 }}>· {enabledCount}/{catalog.length} bật</span>
      </div>
      <div className="set-group" data-testid="settings-modules">
        <div className="hint" style={{ padding: "2px 2px 8px", lineHeight: 1.5 }}>
          Bật/tắt từng nhóm tính năng để sidebar gọn theo nhu cầu. Tắt một module chỉ ẩn khỏi nav —
          dữ liệu &amp; route vẫn còn (mở lại bất cứ lúc nào).
        </div>

        {catalog.map((m, idx) => {
          const enabled = isModuleEnabled(modulePrefs, m.key);
          return (
            <div className="set-row" key={m.key} data-testid={`module-row-${m.key}`} data-enabled={enabled ? "1" : "0"}>
              <div className="sr-info" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="mod-ic" aria-hidden="true"><Icon name={m.icon} /></span>
                <div>
                  <div className="sr-t">{m.label}</div>
                  <div className="sr-d">{m.count} màn hình{m.pinned ? " · lõi (luôn bật)" : ""}</div>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {/* reorder up/down */}
                <div className="mod-move">
                  <button
                    type="button"
                    className="sbc-mbtn"
                    aria-label={`Đưa "${m.label}" lên`}
                    title="Lên"
                    disabled={idx === 0}
                    onClick={() => moveModule(m.key, "up")}
                    data-testid={`module-up-${m.key}`}
                  >▲</button>
                  <button
                    type="button"
                    className="sbc-mbtn"
                    aria-label={`Đưa "${m.label}" xuống`}
                    title="Xuống"
                    disabled={idx === catalog.length - 1}
                    onClick={() => moveModule(m.key, "down")}
                    data-testid={`module-down-${m.key}`}
                  >▼</button>
                </div>

                {/* enable/disable toggle — pinned shows a locked marker */}
                {m.pinned ? (
                  <span className="sbc-pin" title="Module lõi — luôn bật" data-testid={`module-pin-${m.key}`}>lõi</span>
                ) : (
                  <div
                    className={`toggle${enabled ? " on" : ""}`}
                    role="switch"
                    aria-checked={enabled}
                    aria-label={`Bật module "${m.label}"`}
                    tabIndex={0}
                    data-testid={`module-toggle-${m.key}`}
                    onClick={() => toggleModule(m.key)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleModule(m.key); }
                    }}
                  />
                )}
              </div>
            </div>
          );
        })}

        <div className="set-row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn sm ghost" onClick={resetModules} data-testid="modules-reset">
            <Icon name="i-refresh" /> Bật lại tất cả
          </button>
        </div>
      </div>
    </div>
  );
}

export default ModulesPanel;
