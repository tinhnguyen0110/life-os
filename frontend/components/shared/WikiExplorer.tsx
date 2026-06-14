"use client";
/* ============================================================
   WikiExplorer — the LEFT file-tree pane (WEXP-FE). Obsidian-style: collapsible
   virtual folders (from each note's `folder` field via GET /wiki/tree), click a
   file → open /wiki/[id] in the content pane, + a move-note UX (move a note to a
   folder → PUT {folder} → tree refetches).

   Folders are VIRTUAL (the path string is "/"-delimited, e.g. "pkm/zettel") — the
   FE nests the flat groups into a tree by splitting the path. Fail-soft: tree error
   → an inline notice, never blanks the pane. Empty vault → honest empty.
   ============================================================ */
import { useMemo, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useWikiTree } from "@/lib/useWiki";
import { Icon } from "@/lib/icons";
import { ApiError } from "@/lib/api";
import type { WikiTreeNode, WikiTreeNote } from "@/lib/types";

const EMPTY_NODE: WikiTreeNode = { name: "", path: "", folders: [], notes: [] };

/** All folder paths in the (backend-nested) tree — for the move-to-folder picker. */
function allFolderPaths(node: WikiTreeNode, out: string[] = []): string[] {
  for (const child of node.folders) {
    out.push(child.path);
    allFolderPaths(child, out);
  }
  return out;
}

function NoteRow({
  note, activeId, onOpen, onMove,
}: {
  note: WikiTreeNote; activeId: number | null;
  onOpen: (id: number) => void;
  onMove: (note: WikiTreeNote) => void;
}) {
  const active = activeId === note.id;
  return (
    <div className={`wex-file ${active ? "on" : ""}`} data-testid="wex-file" data-note-id={note.id}>
      <button type="button" className="wex-file-open" onClick={() => onOpen(note.id)} data-testid="wex-file-open" title={note.title ?? `#${note.id}`}>
        <Icon name="i-doc" />
        <span className="wex-file-lbl">{note.title ?? <span className="faint">#{note.id}</span>}</span>
      </button>
      <button type="button" className="wex-file-move" onClick={() => onMove(note)} title="Chuyển thư mục" data-testid="wex-file-move">⇄</button>
    </div>
  );
}

function FolderNode({
  node, depth, openFolders, toggle, activeId, onOpen, onMove,
}: {
  node: WikiTreeNode; depth: number;
  openFolders: Set<string>; toggle: (path: string) => void;
  activeId: number | null;
  onOpen: (id: number) => void; onMove: (note: WikiTreeNote) => void;
}) {
  const isOpen = openFolders.has(node.path);
  const childFolders = [...node.folders].sort((a, b) => a.name.localeCompare(b.name));
  return (
    <div className="wex-folder" data-testid="wex-folder" data-folder={node.path}>
      <button
        type="button"
        className="wex-folder-head"
        style={{ paddingLeft: 6 + depth * 12 }}
        onClick={() => toggle(node.path)}
        aria-expanded={isOpen}
        data-testid="wex-folder-toggle"
      >
        <span className={`wex-caret ${isOpen ? "open" : ""}`}>▸</span>
        <span className="wex-folder-name">{node.name}</span>
        <span className="faint wex-count">{node.notes.length}</span>
      </button>
      {isOpen && (
        <div className="wex-folder-body">
          {childFolders.map((c) => (
            <FolderNode key={c.path} node={c} depth={depth + 1} openFolders={openFolders} toggle={toggle} activeId={activeId} onOpen={onOpen} onMove={onMove} />
          ))}
          <div style={{ paddingLeft: 6 + (depth + 1) * 12 }}>
            {node.notes.map((n) => <NoteRow key={n.id} note={n} activeId={activeId} onOpen={onOpen} onMove={onMove} />)}
          </div>
        </div>
      )}
    </div>
  );
}

export function WikiExplorer() {
  const router = useRouter();
  const pathname = usePathname();
  const { tree, status, errMsg, reload, move } = useWikiTree();
  const root = tree ?? EMPTY_NODE;

  // active note id from the current /wiki/<id> path (numeric segment).
  const activeId = useMemo(() => {
    const seg = pathname?.split("/")[2];
    const n = seg ? parseInt(seg, 10) : NaN;
    return Number.isNaN(n) ? null : n;
  }, [pathname]);

  const folderPaths = useMemo(() => allFolderPaths(root), [root]);

  // open-folder state (top-level folders open by default for discoverability).
  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set());
  const toggle = (path: string) =>
    setOpenFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });

  // move-note modal state
  const [moving, setMoving] = useState<WikiTreeNote | null>(null);
  const [moveErr, setMoveErr] = useState("");
  const [moveBusy, setMoveBusy] = useState(false);

  async function doMove(folder: string) {
    if (!moving) return;
    setMoveErr(""); setMoveBusy(true);
    try {
      await move(moving.id, folder.trim());
      setMoving(null);
    } catch (e) {
      setMoveErr(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setMoveBusy(false);
    }
  }

  const topFolders = [...root.folders].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="wex" data-testid="wiki-explorer">
      <div className="wex-head">
        <span className="kicker">Explorer</span>
        <button type="button" className="wex-refresh" onClick={reload} title="Tải lại cây" data-testid="wex-refresh"><Icon name="i-refresh" /></button>
      </div>

      {status === "loading" ? (
        <div className="hint" style={{ padding: "12px 10px" }} data-testid="wex-loading">Đang tải cây…</div>
      ) : status === "error" ? (
        <div className="hint" style={{ padding: "12px 10px", color: "var(--red)" }} data-testid="wex-error">
          {errMsg || "Không tải được cây."} <button type="button" className="link" onClick={reload}>thử lại</button>
        </div>
      ) : topFolders.length === 0 && root.notes.length === 0 ? (
        <div className="hint" style={{ padding: "12px 10px" }} data-testid="wex-empty">
          Chưa có note nào. Capture ở Inbox rồi gắn folder để cây xuất hiện.
        </div>
      ) : (
        <div className="wex-tree" data-testid="wex-tree">
          {topFolders.map((f) => (
            <FolderNode key={f.path} node={f} depth={0} openFolders={openFolders} toggle={toggle} activeId={activeId} onOpen={(id) => router.push(`/wiki/${id}`)} onMove={setMoving} />
          ))}
          {/* root-level notes (folder "") */}
          {root.notes.length > 0 && (
            <div className="wex-root-notes" data-testid="wex-root-notes">
              {root.notes.map((n) => <NoteRow key={n.id} note={n} activeId={activeId} onOpen={(id) => router.push(`/wiki/${id}`)} onMove={setMoving} />)}
            </div>
          )}
        </div>
      )}

      {/* move-to-folder modal */}
      {moving && (
        <div className="wex-move" data-testid="wex-move-modal">
          <div className="wex-move-box">
            <div className="kicker" style={{ marginBottom: 8 }}>Chuyển “{moving.title ?? `#${moving.id}`}” tới folder</div>
            <MoveForm folders={folderPaths} busy={moveBusy} err={moveErr} onCancel={() => { setMoving(null); setMoveErr(""); }} onMove={doMove} />
          </div>
        </div>
      )}
    </div>
  );
}

function MoveForm({
  folders, busy, err, onCancel, onMove,
}: {
  folders: string[]; busy: boolean; err: string;
  onCancel: () => void; onMove: (folder: string) => void;
}) {
  const [val, setVal] = useState("");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <input
        className="wex-move-input"
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="vd: pkm/zettel — để trống = vault root"
        list="wex-folder-list"
        data-testid="wex-move-input"
      />
      <datalist id="wex-folder-list">
        {folders.map((f) => <option key={f} value={f} />)}
      </datalist>
      {err && <div className="hint" style={{ color: "var(--red)" }} data-testid="wex-move-error">⚠ {err}</div>}
      <div style={{ display: "flex", gap: 7, justifyContent: "flex-end" }}>
        <button type="button" className="btn sm ghost" onClick={onCancel} disabled={busy}>Hủy</button>
        <button type="button" className="btn sm accent" onClick={() => onMove(val)} disabled={busy} data-testid="wex-move-submit">
          {busy ? "Đang chuyển…" : "Chuyển"}
        </button>
      </div>
    </div>
  );
}
