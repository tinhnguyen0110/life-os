"use client";
/* ============================================================
   WikiEditor — minimal markdown editor for a wiki note body (W2 edit mode + W3
   refine). Per FE recon + north-star: a plain controlled <textarea>, NO heavy
   editor lib (CodeMirror/Lexical). A "Xem trước" toggle renders the live body via
   WikiMarkdown (react-markdown + remark-gfm) so full markdown (headings/lists/code/
   tables/quotes) + `[[id|title]]` wikilinks preview correctly — WEXP-FE polish.

   Wikilink autocomplete (`[[` → title→id search) is a LATER enhancement — at M1
   the user types `[[47|title]]` directly; the textarea + preview is enough to
   write and verify links. Keeping it a textarea means zero new deps.
   ============================================================ */
import { useState } from "react";
import { WikiMarkdown } from "./WikiMarkdown";

interface WikiEditorProps {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  disabled?: boolean;
  testId?: string;
}

export function WikiEditor({ value, onChange, placeholder, disabled, testId }: WikiEditorProps) {
  const [preview, setPreview] = useState(false);
  return (
    <div className="wedit" data-testid={testId}>
      <div className="wedit-bar">
        <button
          type="button"
          className={`btn sm ${preview ? "" : "accent"}`}
          onClick={() => setPreview(false)}
          data-testid="wedit-write"
        >
          Viết
        </button>
        <button
          type="button"
          className={`btn sm ${preview ? "accent" : ""}`}
          onClick={() => setPreview(true)}
          data-testid="wedit-preview"
        >
          Xem trước
        </button>
        <span className="hint" style={{ marginLeft: "auto" }}>
          Markdown + <code>[[47|title]]</code> link
        </span>
      </div>
      {preview ? (
        <div className="wedit-preview" data-testid="wedit-preview-body">
          <WikiMarkdown content={value} testId="wedit-md" />
        </div>
      ) : (
        <textarea
          className="wedit-ta"
          value={value}
          placeholder={placeholder ?? "Viết note (markdown + [[id|title]] links)…"}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          data-testid="wedit-textarea"
          rows={14}
        />
      )}
    </div>
  );
}
