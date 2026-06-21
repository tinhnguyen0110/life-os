"use client";
/* ============================================================
   WikiTrash (#94) — the recovery surface: see soft-deleted notes + RESTORE them (the
   "xoá nhầm → rollback" the user asked for). Lists GET /wiki/trash (newest-deleted
   first); each row = title + when-deleted + a Restore button (POST /restore → refetch
   trash + tell the parent to refresh the vault tree). Honest empty-state ("trash trống").
   RENDER-ONLY against the FROZEN #94-BE endpoints. fail-closed restore (error → shown).
   ============================================================ */
import { useState } from "react";
import { useWikiTrash } from "@/lib/useWikiTrash";
import { ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";

export function WikiTrash({ onClose, onRestored }: { onClose: () => void; onRestored: () => void }) {
  const { items, count, status, errMsg, reload, restore } = useWikiTrash();
  const [restoring, setRestoring] = useState<number | null>(null);
  const [rowErr, setRowErr] = useState<{ id: number; msg: string } | null>(null);

  async function onRestore(id: number) {
    setRowErr(null); setRestoring(id);
    try {
      await restore(id);
      onRestored(); // refresh the vault tree so the note reappears
    } catch (e) {
      setRowErr({ id, msg: e instanceof ApiError ? e.message : (e as Error).message });
    } finally {
      setRestoring(null);
    }
  }

  return (
    <div className="wimport-overlay" data-testid="wiki-trash" role="dialog" aria-label="Thùng rác wiki" aria-modal="true">
      <div className="wimport-modal">
        <div className="wimport-head">
          <span className="kicker">🗑 Thùng rác · {status === "ready" ? count : "…"} note đã xoá</span>
          <span className="sp" style={{ flex: 1 }} />
          <button type="button" className="btn sm" onClick={reload} data-testid="trash-reload">↻</button>
          <button type="button" className="btn sm" onClick={onClose} data-testid="trash-close">Đóng</button>
        </div>

        {status === "loading" && (
          <div data-testid="trash-loading" aria-busy="true" style={{ padding: "6px 2px" }}>
            <div className="sk-line" style={{ width: "70%" }} />
            <div className="sk-line" style={{ width: "50%", marginTop: 8 }} />
          </div>
        )}

        {status === "error" && (
          <div className="hint neg" style={{ padding: "12px 4px" }} data-testid="trash-error">
            Không tải được thùng rác: {errMsg}.
            <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
          </div>
        )}

        {status === "ready" && count === 0 && (
          <div className="hint faint" style={{ padding: "20px 4px", textAlign: "center" }} data-testid="trash-empty">
            🧹 Thùng rác trống — chưa có note nào bị xoá.
          </div>
        )}

        {status === "ready" && count > 0 && (
          <div className="wtrash-list" data-testid="trash-list">
            {items.map((it) => (
              <div className="wtrash-row" key={it.id} data-testid={`trash-row-${it.id}`}>
                <div className="wtrash-meta">
                  <span className="wtrash-title">{it.title || <span className="faint">(không có tiêu đề)</span>}</span>
                  <span className="hint faint" style={{ fontSize: 11 }} data-testid={`trash-when-${it.id}`}>
                    xoá {relativeTime(it.deletedAt)}{it.folder ? ` · ${it.folder}` : ""}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn sm acc"
                  disabled={restoring === it.id}
                  onClick={() => onRestore(it.id)}
                  data-testid={`trash-restore-${it.id}`}
                >
                  {restoring === it.id ? "Đang khôi phục…" : "↩ Khôi phục"}
                </button>
                {rowErr?.id === it.id && (
                  <span className="hint neg" style={{ marginLeft: 6 }} data-testid={`trash-row-err-${it.id}`}>⚠ {rowErr.msg}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
