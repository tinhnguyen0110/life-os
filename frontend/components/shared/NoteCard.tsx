/* ============================================================
   NoteCard — one note tile. Ported from mock screens-system.js note card markup
   (.note-card .nt/.nb/.nm). Shows title (+ pin icon), body, tag chips, relative
   updatedAt. Edit/delete/pin actions are caller-driven. render-only display.
   ============================================================ */
import type { Note } from "@/lib/useNotes";
import { relativeTime } from "@/lib/format";
import { Icon } from "@/lib/icons";

export function NoteCard({
  note,
  onEdit,
  onDelete,
  onTogglePin,
}: {
  note: Note;
  onEdit?: (n: Note) => void;
  onDelete?: (n: Note) => void;
  onTogglePin?: (n: Note) => void;
}) {
  return (
    <div className="note-card" data-testid={`note-${note.id}`} data-pinned={note.pinned}>
      <div className="nt">
        {note.pinned && <Icon name="i-note" />}
        <span style={{ flex: 1 }}>{note.title || "(không tiêu đề)"}</span>
        {onTogglePin && (
          <button
            className="btn sm"
            type="button"
            onClick={() => onTogglePin(note)}
            title={note.pinned ? "Bỏ ghim" : "Ghim"}
            data-testid={`pin-${note.id}`}
          >
            {note.pinned ? "📌" : "📍"}
          </button>
        )}
      </div>
      {note.body && <div className="nb">{note.body}</div>}
      <div className="nm">
        <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
          {(note.tags ?? []).map((t) => (
            <span className="tagchip" key={t}>
              {t}
            </span>
          ))}
        </div>
        <span style={{ marginLeft: "auto" }}>{relativeTime(note.updatedAt)}</span>
        {onEdit && (
          <button className="btn sm" type="button" onClick={() => onEdit(note)} data-testid={`edit-${note.id}`}>
            sửa
          </button>
        )}
        {onDelete && (
          <button className="btn sm" type="button" onClick={() => onDelete(note)} data-testid={`del-${note.id}`}>
            xóa
          </button>
        )}
      </div>
    </div>
  );
}
