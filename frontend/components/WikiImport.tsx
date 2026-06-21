"use client";
/* ============================================================
   WikiImport (#93) — import .md/.txt files into the wiki. Pick file(s) OR paste text →
   PREVIEW (filename + snippet) → confirm → POST /wiki/import (FAIL-SOFT multi-file) →
   per-file RESULTS (created → title + link to the note · errors → the agent-error
   message + hint). On any success, calls onImported() so the parent refreshes the tree.

   RENDER-ONLY against the FROZEN endpoint: the BE parses frontmatter + creates the note;
   the FE reads files client-side (FileReader) + surfaces the honest per-file outcome.
   reqId guard drops a stale POST response (if the user re-submits before the first lands).
   ============================================================ */
import { useRef, useState } from "react";
import Link from "next/link";
import { importWiki, ApiError } from "@/lib/api";
import type { WikiImportFile, WikiImportResult } from "@/lib/types";

const SNIPPET_LEN = 120;

export function WikiImport({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [files, setFiles] = useState<WikiImportFile[]>([]);
  const [pasteName, setPasteName] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<WikiImportResult[] | null>(null);
  const [err, setErr] = useState("");
  const reqId = useRef(0);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    if (picked.length === 0) return;
    setErr(""); setResults(null);
    const read = await Promise.all(
      picked.map(
        (f) =>
          new Promise<WikiImportFile>((resolve) => {
            const r = new FileReader();
            r.onload = () => resolve({ filename: f.name, content: String(r.result ?? "") });
            r.onerror = () => resolve({ filename: f.name, content: "" });
            r.readAsText(f);
          })
      )
    );
    setFiles((prev) => [...prev, ...read]);
  }

  function addPaste() {
    const name = pasteName.trim() || "pasted.md";
    const fn = /\.(md|txt)$/i.test(name) ? name : `${name}.md`;
    if (!pasteText.trim()) { setErr("Dán nội dung trước khi thêm"); return; }
    setErr("");
    setFiles((prev) => [...prev, { filename: fn, content: pasteText }]);
    setPasteName(""); setPasteText("");
  }

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function onConfirm() {
    if (files.length === 0) { setErr("Chọn hoặc dán ít nhất một file"); return; }
    setErr(""); setImporting(true); setResults(null);
    const id = ++reqId.current;
    try {
      const res = await importWiki({ files });
      if (id !== reqId.current) return; // stale
      setResults(res.data.imported);
      if (res.data.createdCount > 0) onImported(); // refresh the tree
    } catch (e) {
      if (id !== reqId.current) return;
      setErr(e instanceof ApiError ? (e.hint ? `${e.message} (${e.hint})` : e.message) : (e as Error).message);
    } finally {
      if (id === reqId.current) setImporting(false);
    }
  }

  const createdCount = results?.filter((r) => r.ok).length ?? 0;
  const errorCount = results?.filter((r) => !r.ok).length ?? 0;

  return (
    <div className="wimport-overlay" data-testid="wiki-import" role="dialog" aria-label="Import wiki" aria-modal="true">
      <div className="wimport-modal">
        <div className="wimport-head">
          <span className="kicker">Import .md / .txt</span>
          <span className="sp" style={{ flex: 1 }} />
          <button type="button" className="btn sm" onClick={onClose} data-testid="import-close">Đóng</button>
        </div>

        {/* pick + paste */}
        <div className="wimport-inputs">
          <label className="btn sm" data-testid="import-pick-label">
            Chọn file…
            <input
              type="file"
              accept=".md,.txt,text/markdown,text/plain"
              multiple
              onChange={onPick}
              data-testid="import-file-input"
              style={{ display: "none" }}
            />
          </label>
          <span className="hint faint">hoặc dán nội dung:</span>
        </div>
        <div className="wimport-paste">
          <input
            type="text"
            placeholder="tên file (vd: ghi-chu.md)"
            value={pasteName}
            onChange={(e) => setPasteName(e.target.value)}
            data-testid="import-paste-name"
            style={{ width: 200 }}
          />
          <textarea
            placeholder="dán markdown ở đây…"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            data-testid="import-paste-text"
            rows={3}
          />
          <button type="button" className="btn sm" onClick={addPaste} data-testid="import-paste-add">Thêm vào danh sách</button>
        </div>

        {/* preview list (before confirm) */}
        {files.length > 0 && !results && (
          <div className="wimport-preview" data-testid="import-preview">
            <div className="kicker" style={{ margin: "8px 0 4px" }}>Sẽ import {files.length} file</div>
            {files.map((f, i) => (
              <div className="wimport-file" key={`${f.filename}-${i}`} data-testid={`import-file-${i}`}>
                <span className="wimport-fn">{f.filename}</span>
                <span className="hint faint wimport-snip">{f.content.slice(0, SNIPPET_LEN).replace(/\n/g, " ") || "(trống)"}</span>
                <button type="button" className="btn sm" onClick={() => removeFile(i)} data-testid={`import-remove-${i}`}>Bỏ</button>
              </div>
            ))}
          </div>
        )}

        {err && <div className="hint neg" style={{ marginTop: 6 }} data-testid="import-error">⚠ {err}</div>}

        {/* results (after confirm) — fail-soft per file */}
        {results && (
          <div className="wimport-results" data-testid="import-results">
            <div className="kicker" style={{ margin: "8px 0 4px" }} data-testid="import-summary">
              <span className="pos">{createdCount} tạo</span>{errorCount > 0 && <span className="neg"> · {errorCount} lỗi</span>}
            </div>
            {results.map((r, i) => (
              <div className={`wimport-result ${r.ok ? "ok" : "bad"}`} key={`${r.filename}-${i}`} data-testid={`import-result-${i}`}>
                <span className="wimport-fn">{r.filename}</span>
                {r.ok ? (
                  <Link
                    href={`/wiki/${r.noteId}`}
                    className="acc"
                    onClick={onClose}
                    data-testid={`import-ok-${i}`}
                  >
                    ✓ {r.title ?? `note ${r.noteId}`}
                  </Link>
                ) : (
                  <span className="hint neg" data-testid={`import-bad-${i}`}>
                    ✗ {r.error?.message ?? "lỗi không rõ"}
                    {r.error?.hint && <span className="hint faint" style={{ marginLeft: 6 }}>({r.error.hint})</span>}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* action bar */}
        <div className="wimport-actions">
          {!results ? (
            <button type="button" className="btn accent" disabled={importing || files.length === 0} onClick={onConfirm} data-testid="import-confirm">
              {importing ? "Đang import…" : `Import ${files.length || ""} file`}
            </button>
          ) : (
            <button type="button" className="btn accent" onClick={onClose} data-testid="import-done">Xong</button>
          )}
        </div>
      </div>
    </div>
  );
}
