"use client";
/* ============================================================
   WikiExplorer — the LEFT file-tree pane (WEXP-FE #108 · #127-W3 ops menu).

   #108: Obsidian-style collapsible folders (GET /wiki/tree), click a file → open
   /wiki/[id], move a note → PUT {folder} → tree refetches.

   #127-W3 (the wiki work-dir ops — the HEADLINE: create a sub-folder INSIDE a folder +
   delete, ON the browser UI). Adds an ops menu:
   • toolbar: "+ Thư mục" (new folder at root) + "Nhập" (import .md/.txt — file picker AND
     paste).
   • per-folder ⋯ menu: "Thư mục con mới" (NESTED create → POST /wiki/folders {path:
     parent+"/"+name}) · "Đổi tên / Chuyển" (move/rename → PUT /wiki/folders/{path}/move)
     · "Xóa" (in-page confirm #72, NOT window.confirm → DELETE /wiki/folders/{path} →
     the subtree leaves the tree; soft-delete, recoverable).
   🔴 the W1 gotcha: after a delete, "gone" is observed via the REFRESHED /wiki/tree
   (reload()), NOT get_note (still returns the tombstone). All folder ops bump the tree bus.
   ============================================================ */
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useWikiTree } from "@/lib/useWiki";
import { Icon } from "@/lib/icons";
import { Popover } from "@/components/Popover";
import {
  ApiError, createWikiFolder, deleteWikiFolder, moveWikiFolder, importWiki,
  createWikiNote, updateWikiNote,
} from "@/lib/api";
import type { WikiTreeNode, WikiTreeNote, WikiImportResult } from "@/lib/types";

const EMPTY_NODE: WikiTreeNode = { name: "", path: "", folders: [], notes: [] };
const ALLOWED_EXT = [".md", ".txt"]; // mirror the BE _ALLOWED_EXT (client-side guard too)

/** the per-folder ⋯ ops (#127-W3 + #127-W3A import-here / note-here). */
type FolderOpKind = "new-sub" | "rename" | "delete" | "import-here" | "new-note";

/** All folder paths in the (backend-nested) tree — for the move-to-folder picker. */
function allFolderPaths(node: WikiTreeNode, out: string[] = []): string[] {
  for (const child of node.folders) {
    out.push(child.path);
    allFolderPaths(child, out);
  }
  return out;
}

/** ApiError message + hint (agent-error #46/#70). */
function errText(e: unknown): string {
  if (e instanceof ApiError) return e.hint ? `${e.message} (${e.hint})` : e.message;
  return (e as Error).message;
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
  node, depth, openFolders, toggle, activeId, onOpen, onMove, onFolderOp,
}: {
  node: WikiTreeNode; depth: number;
  openFolders: Set<string>; toggle: (path: string) => void;
  activeId: number | null;
  onOpen: (id: number) => void; onMove: (note: WikiTreeNote) => void;
  onFolderOp: (op: FolderOpKind, node: WikiTreeNode) => void;
}) {
  const isOpen = openFolders.has(node.path);
  const childFolders = [...node.folders].sort((a, b) => a.name.localeCompare(b.name));
  const [menuOpen, setMenuOpen] = useState(false);
  // #142-P1 — the folder ⋯ menu is now a portaled <Popover> (escapes the scrollable
  // explorer tree's overflow clip + adds the click-away/Escape it previously LACKED).
  const menuBtnRef = useRef<HTMLButtonElement | null>(null);
  return (
    <div className="wex-folder" data-testid="wex-folder" data-folder={node.path}>
      <div className="wex-folder-head-row">
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
        {/* #127-W3 — the per-folder ops ⋯ menu */}
        <div className="wex-folder-ops" data-testid={`wex-folder-ops-${node.path}`}>
          <button type="button" ref={menuBtnRef} className="wex-ops-btn" onClick={() => setMenuOpen((o) => !o)}
            aria-haspopup="menu" aria-expanded={menuOpen} data-testid={`wex-ops-toggle-${node.path}`} title="Thao tác thư mục">⋯</button>
          <Popover open={menuOpen} anchorRef={menuBtnRef} onClose={() => setMenuOpen(false)}
            className="wex-ops-menu" testId={`wex-ops-menu-${node.path}`}>
            {/* #127-W3A — add a file/note SCOPED to this folder */}
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onFolderOp("new-note", node); }} data-testid={`wex-op-newnote-${node.path}`}>
              ＋ Note mới
            </button>
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onFolderOp("import-here", node); }} data-testid={`wex-op-importhere-${node.path}`}>
              📥 Import vào đây
            </button>
            <div className="wex-ops-sep" aria-hidden="true" />
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onFolderOp("new-sub", node); }} data-testid={`wex-op-newsub-${node.path}`}>
              ＋ Thư mục con mới
            </button>
            <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onFolderOp("rename", node); }} data-testid={`wex-op-rename-${node.path}`}>
              ✎ Đổi tên / Chuyển
            </button>
            <button type="button" role="menuitem" className="neg" onClick={() => { setMenuOpen(false); onFolderOp("delete", node); }} data-testid={`wex-op-delete-${node.path}`}>
              ✕ Xóa
            </button>
          </Popover>
        </div>
      </div>
      {isOpen && (
        <div className="wex-folder-body">
          {childFolders.map((c) => (
            <FolderNode key={c.path} node={c} depth={depth + 1} openFolders={openFolders} toggle={toggle} activeId={activeId} onOpen={onOpen} onMove={onMove} onFolderOp={onFolderOp} />
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

  const activeId = useMemo(() => {
    const seg = pathname?.split("/")[2];
    const n = seg ? parseInt(seg, 10) : NaN;
    return Number.isNaN(n) ? null : n;
  }, [pathname]);

  // refetch the tree on wiki-route change (#108).
  const prevPath = useRef(pathname);
  useEffect(() => {
    if (prevPath.current === pathname) return;
    prevPath.current = pathname;
    reload();
  }, [pathname, reload]);

  const folderPaths = useMemo(() => allFolderPaths(root), [root]);

  const [openFolders, setOpenFolders] = useState<Set<string>>(new Set());
  const toggle = (path: string) =>
    setOpenFolders((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });

  // move-note modal (#108)
  const [moving, setMoving] = useState<WikiTreeNote | null>(null);
  const [moveErr, setMoveErr] = useState("");
  const [moveBusy, setMoveBusy] = useState(false);

  // #127-W3 — folder-op state (a single op modal driven by `folderOp`). #127-W3A adds
  // "new-note" (create a note IN a folder).
  type FolderOp = { kind: "new-root" | "new-sub" | "rename" | "delete" | "new-note"; node: WikiTreeNode | null };
  const [folderOp, setFolderOp] = useState<FolderOp | null>(null);
  const [opVal, setOpVal] = useState("");           // the new-folder name / new path / new-note title
  const [opBusy, setOpBusy] = useState(false);
  const [opErr, setOpErr] = useState("");
  // #127-W3A — the import modal carries a TARGET folder ("" = root). null = closed.
  const [importTarget, setImportTarget] = useState<string | null>(null);

  async function doMove(folder: string) {
    if (!moving) return;
    setMoveErr(""); setMoveBusy(true);
    try {
      await move(moving.id, folder.trim());
      setMoving(null);
    } catch (e) {
      setMoveErr(errText(e));
    } finally {
      setMoveBusy(false);
    }
  }

  function startFolderOp(op: FolderOpKind, node: WikiTreeNode) {
    setOpErr("");
    if (op === "import-here") {
      // #127-W3A — open the import modal pre-targeted to THIS folder.
      setImportTarget(node.path);
      return;
    }
    setFolderOp({ kind: op, node });
    // prefill: rename → the current path; new-sub/new-note → empty.
    setOpVal(op === "rename" ? node.path : "");
  }
  function startNewRoot() {
    setFolderOp({ kind: "new-root", node: null });
    setOpErr(""); setOpVal("");
  }

  async function runFolderOp() {
    if (!folderOp) return;
    setOpErr(""); setOpBusy(true);
    try {
      if (folderOp.kind === "delete" && folderOp.node) {
        await deleteWikiFolder(folderOp.node.path);
      } else if (folderOp.kind === "new-root") {
        const name = opVal.trim();
        if (!name) { setOpErr("Nhập tên thư mục."); setOpBusy(false); return; }
        await createWikiFolder({ path: name });
      } else if (folderOp.kind === "new-sub" && folderOp.node) {
        const name = opVal.trim().replace(/^\/+|\/+$/g, "");
        if (!name) { setOpErr("Nhập tên thư mục con."); setOpBusy(false); return; }
        // 🔴 the NESTED create — parent path + "/" + the child name.
        await createWikiFolder({ path: `${folderOp.node.path}/${name}` });
      } else if (folderOp.kind === "rename" && folderOp.node) {
        const to = opVal.trim().replace(/^\/+|\/+$/g, "");
        if (!to) { setOpErr("Nhập đường dẫn mới."); setOpBusy(false); return; }
        if (to === folderOp.node.path) { setFolderOp(null); setOpBusy(false); return; }
        await moveWikiFolder(folderOp.node.path, to);
      } else if (folderOp.kind === "new-note" && folderOp.node) {
        // #127-W3A — create a NEW note IN this folder (the BE NoteCreateInput takes folder).
        const title = opVal.trim();
        if (!title) { setOpErr("Nhập tiêu đề note."); setOpBusy(false); return; }
        const res = await createWikiNote({ title, content: "", folder: folderOp.node.path });
        reload();
        setFolderOp(null); setOpVal("");
        if (res?.data?.id != null) router.push(`/wiki/${res.data.id}`); // open the new note
        setOpBusy(false);
        return;
      }
      reload(); // 🔴 observe the change via the refreshed tree (the W1 gotcha)
      setFolderOp(null); setOpVal("");
    } catch (e) {
      setOpErr(errText(e));
    } finally {
      setOpBusy(false);
    }
  }

  const topFolders = [...root.folders].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <div className="wex" data-testid="wiki-explorer">
      <div className="wex-head">
        <span className="kicker">Explorer</span>
        <span className="sp" style={{ flex: 1 }} />
        {/* #127-W3 toolbar: new root folder + import */}
        <button type="button" className="wex-tool" onClick={startNewRoot} title="Thư mục mới (gốc)" data-testid="wex-new-folder">＋</button>
        <button type="button" className="wex-tool" onClick={() => setImportTarget("")} title="Nhập .md/.txt" data-testid="wex-import-open"><Icon name="i-doc" /></button>
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
          Chưa có thư mục nào. Bấm ＋ để tạo thư mục, hoặc nhập .md/.txt.
        </div>
      ) : (
        <div className="wex-tree" data-testid="wex-tree">
          {topFolders.map((f) => (
            <FolderNode key={f.path} node={f} depth={0} openFolders={openFolders} toggle={toggle} activeId={activeId} onOpen={(id) => router.push(`/wiki/${id}`)} onMove={setMoving} onFolderOp={startFolderOp} />
          ))}
          {root.notes.length > 0 && (
            <div className="wex-root-notes" data-testid="wex-root-notes">
              {root.notes.map((n) => <NoteRow key={n.id} note={n} activeId={activeId} onOpen={(id) => router.push(`/wiki/${id}`)} onMove={setMoving} />)}
            </div>
          )}
        </div>
      )}

      {/* move-note modal (#108) */}
      {moving && (
        <div className="wex-move" data-testid="wex-move-modal">
          <div className="wex-move-box">
            <div className="kicker" style={{ marginBottom: 8 }}>Chuyển “{moving.title ?? `#${moving.id}`}” tới folder</div>
            <MoveForm folders={folderPaths} busy={moveBusy} err={moveErr} onCancel={() => { setMoving(null); setMoveErr(""); }} onMove={doMove} />
          </div>
        </div>
      )}

      {/* #127-W3 — the folder-op modal (new-root / new-sub / rename / delete-confirm) */}
      {folderOp && (
        <div className="wex-move" data-testid="wex-folderop-modal">
          <div className="wex-move-box">
            {folderOp.kind === "delete" ? (
              <div data-testid="wex-delete-confirm">
                <div className="kicker neg" style={{ marginBottom: 8 }}>Xóa thư mục “{folderOp.node?.path}”?</div>
                <div className="hint faint" style={{ marginBottom: 10, lineHeight: 1.5 }}>
                  Cả thư mục con + note bên trong sẽ vào thùng rác (khôi phục được). Thư mục khác không ảnh hưởng.
                </div>
                {opErr && <div className="hint" style={{ color: "var(--red)", marginBottom: 6 }} data-testid="wex-op-error">⚠ {opErr}</div>}
                <div style={{ display: "flex", gap: 7, justifyContent: "flex-end" }}>
                  <button type="button" className="btn sm ghost" onClick={() => setFolderOp(null)} disabled={opBusy} data-testid="wex-delete-cancel">Hủy</button>
                  <button type="button" className="btn sm neg" onClick={runFolderOp} disabled={opBusy} data-testid="wex-delete-confirm-yes">
                    {opBusy ? "Đang xóa…" : "Xóa thư mục"}
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <div className="kicker" style={{ marginBottom: 8 }}>
                  {folderOp.kind === "new-root" && "Thư mục mới (gốc)"}
                  {folderOp.kind === "new-sub" && `Thư mục con của “${folderOp.node?.path}”`}
                  {folderOp.kind === "rename" && `Đổi tên / chuyển “${folderOp.node?.path}”`}
                  {folderOp.kind === "new-note" && `Note mới trong “${folderOp.node?.path}”`}
                </div>
                <input
                  className="wex-move-input"
                  value={opVal}
                  onChange={(e) => setOpVal(e.target.value)}
                  placeholder={
                    folderOp.kind === "new-sub" ? "tên thư mục con (vd: zettel)"
                    : folderOp.kind === "rename" ? "đường dẫn mới (vd: pkm/zettel)"
                    : folderOp.kind === "new-note" ? "tiêu đề note (vd: Ý tưởng mới)"
                    : "tên thư mục (vd: pkm)"
                  }
                  data-testid="wex-op-input"
                  autoFocus
                  onKeyDown={(e) => { if (e.key === "Enter") runFolderOp(); }}
                />
                {opErr && <div className="hint" style={{ color: "var(--red)", marginTop: 6 }} data-testid="wex-op-error">⚠ {opErr}</div>}
                <div style={{ display: "flex", gap: 7, justifyContent: "flex-end", marginTop: 8 }}>
                  <button type="button" className="btn sm ghost" onClick={() => setFolderOp(null)} disabled={opBusy}>Hủy</button>
                  <button type="button" className="btn sm accent" onClick={runFolderOp} disabled={opBusy} data-testid="wex-op-submit">
                    {opBusy ? "Đang lưu…" : "Lưu"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* #127-W3 + W3A — the import modal (file picker + paste, .md/.txt only; #127-W3A:
          a folder-target picker, default = importTarget). */}
      {importTarget !== null && (
        <ImportModal
          target={importTarget}
          folders={folderPaths}
          onClose={() => setImportTarget(null)}
          onDone={() => { reload(); }}
        />
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

/** #127-W3 — import .md/.txt: a file picker (multi) AND a paste box (filename + content).
 *  Rejects non-.md/.txt client-side; ALSO surfaces the BE per-file agent-error honestly.
 *  #127-W3A — a folder-TARGET picker (default = `target`); imported notes land in that
 *  folder via the 2-step (import → root, then PUT {folder} per created note — the BE
 *  import path has no folder param). */
function ImportModal({
  target, folders, onClose, onDone,
}: {
  target: string; folders: string[];
  onClose: () => void; onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<WikiImportResult[] | null>(null);
  const [err, setErr] = useState("");
  const [targetFolder, setTargetFolder] = useState(target); // "" = root
  // paste mode
  const [pasteName, setPasteName] = useState("");
  const [pasteBody, setPasteBody] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  function extOk(filename: string): boolean {
    const lower = filename.toLowerCase();
    return ALLOWED_EXT.some((e) => lower.endsWith(e));
  }

  async function importFiles(files: { filename: string; content: string }[]) {
    if (files.length === 0) { setErr("Chưa có tệp nào."); return; }
    setErr(""); setBusy(true);
    try {
      const res = await importWiki({ files });
      setResults(res.data.imported);
      // #127-W3A — the 2-step: import lands at ROOT, then move each created note into the
      // target folder (the BE import path has no folder param). Root target → no move.
      const folder = targetFolder.trim();
      if (folder) {
        const created = res.data.imported.filter((r) => r.ok && r.noteId != null);
        await Promise.all(created.map((r) => updateWikiNote(r.noteId as number, { folder })));
      }
      if (res.data.createdCount > 0) onDone(); // refresh the tree if anything landed
    } catch (e) {
      setErr(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function onPickFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const list = Array.from(e.target.files ?? []);
    // client-side reject non-.md/.txt (the BE rejects too — this is the friendly guard).
    const bad = list.filter((f) => !extOk(f.name));
    if (bad.length > 0) {
      setErr(`Chỉ nhận .md/.txt — bỏ qua: ${bad.map((f) => f.name).join(", ")}`);
    }
    const good = list.filter((f) => extOk(f.name));
    const files = await Promise.all(good.map(async (f) => ({ filename: f.name, content: await f.text() })));
    if (files.length > 0) await importFiles(files);
  }

  async function onPasteImport() {
    const name = pasteName.trim();
    if (!name) { setErr("Nhập tên tệp (vd: ghi-chu.md)."); return; }
    if (!extOk(name)) { setErr("Tên tệp phải là .md hoặc .txt."); return; }
    if (!pasteBody.trim()) { setErr("Nội dung trống."); return; }
    await importFiles([{ filename: name, content: pasteBody }]);
  }

  return (
    <div className="wex-move" data-testid="wex-import-modal">
      <div className="wex-move-box" style={{ minWidth: 320 }}>
        <div className="kicker" style={{ marginBottom: 8 }}>Nhập ghi chú (.md / .txt)</div>

        {/* #127-W3A — the folder-TARGET picker (default = the pre-target; "" = root) */}
        <div style={{ marginBottom: 10 }}>
          <label className="hint faint" style={{ display: "block", marginBottom: 3 }}>Nhập vào thư mục</label>
          <select className="wex-move-input" value={targetFolder} onChange={(e) => setTargetFolder(e.target.value)} data-testid="wex-import-folder">
            <option value="">📁 (gốc / root)</option>
            {folders.map((f) => <option key={f} value={f}>{f.split("/").join(" / ")}</option>)}
          </select>
        </div>

        {/* file picker */}
        <div style={{ marginBottom: 10 }}>
          <input ref={fileRef} type="file" accept=".md,.txt,text/markdown,text/plain" multiple
            onChange={onPickFiles} data-testid="wex-import-file" style={{ display: "none" }} />
          <button type="button" className="btn sm" disabled={busy} onClick={() => fileRef.current?.click()} data-testid="wex-import-pick">
            Chọn tệp…
          </button>
          <span className="hint faint" style={{ marginLeft: 8 }}>chỉ .md / .txt</span>
        </div>

        {/* paste */}
        <div className="kicker faint" style={{ marginBottom: 4, fontSize: 10 }}>hoặc dán nội dung</div>
        <input className="wex-move-input" value={pasteName} onChange={(e) => setPasteName(e.target.value)}
          placeholder="tên tệp (vd: ghi-chu.md)" data-testid="wex-import-paste-name" style={{ marginBottom: 6 }} />
        <textarea className="wex-move-input" value={pasteBody} onChange={(e) => setPasteBody(e.target.value)} rows={4}
          placeholder="# Tiêu đề&#10;nội dung markdown…" data-testid="wex-import-paste-body" style={{ resize: "vertical", marginBottom: 6 }} />
        <button type="button" className="btn sm accent" disabled={busy} onClick={onPasteImport} data-testid="wex-import-paste-submit">
          {busy ? "Đang nhập…" : "Nhập từ nội dung"}
        </button>

        {err && <div className="hint" style={{ color: "var(--red)", marginTop: 8 }} data-testid="wex-import-error">⚠ {err}</div>}

        {/* per-file results (honest — ok / rejected) */}
        {results && (
          <div style={{ marginTop: 10 }} data-testid="wex-import-results">
            {results.map((r, i) => (
              <div key={i} className="hint" style={{ lineHeight: 1.5 }} data-testid={`wex-import-result-${i}`}>
                {r.ok ? (
                  <span className="pos">✓ {r.filename} → #{r.noteId}</span>
                ) : (
                  <span className="neg" data-testid={`wex-import-rejected-${i}`}>✕ {r.filename}: {r.error?.message}{r.error?.hint ? ` (${r.error.hint})` : ""}</span>
                )}
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 7, justifyContent: "flex-end", marginTop: 10 }}>
          <button type="button" className="btn sm ghost" onClick={onClose} data-testid="wex-import-close">Đóng</button>
        </div>
      </div>
    </div>
  );
}
