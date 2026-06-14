"use client";
/* ============================================================
   WikiLinkRenderer + minimal in-house markdown — renders a wiki note body.
   Ported from mock screens-wiki.js renderWikiLinks() (L20-25) — VERBATIM regex,
   but to React nodes (not HTML strings) so links are real Next <Link>s.

   Wikilink forms (mock order — most specific first):
     [[47|title]]  → <Link href=/wiki/47>title</Link>           (resolved, labelled)
     [[47]]        → <Link href=/wiki/47>#47</Link>             (resolved, bare id)
     [[Title]]     → <span class="wlink ghost">Title</span>     (ghost — no note yet)
   Minimal markdown (per FE recon — NO heavy lib): **bold**, paragraphs (blank line),
   single newline → <br>. Headings/lists kept simple (line-prefix). Anything else is
   literal text — we do NOT attempt full CommonMark (north-star: simplest).
   ============================================================ */
import { Fragment, type ReactNode } from "react";
import Link from "next/link";

/** Split one text segment on `**bold**` → React nodes. */
function renderBold(text: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push(<b key={`${keyBase}-b${i++}`}>{m[1]}</b>);
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Combined wikilink matcher — the three mock forms, tried in order. Capturing
 *  groups: 1=id (of `[[id|title]]`), 2=title, 3=id (of `[[id]]`), 4=ghost title. */
const WIKILINK_RE = /\[\[(\d+)\|([^\]]+)\]\]|\[\[(\d+)\]\]|\[\[([^\]\d][^\]]*)\]\]/g;

/** Render inline content of one line: wikilinks + **bold** + plain text. */
function renderInline(line: string, keyBase: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  WIKILINK_RE.lastIndex = 0;
  while ((m = WIKILINK_RE.exec(line)) !== null) {
    if (m.index > last) out.push(...renderBold(line.slice(last, m.index), `${keyBase}-t${i}`));
    const k = `${keyBase}-l${i++}`;
    if (m[1] !== undefined) {
      // [[id|title]]
      out.push(
        <Link key={k} href={`/wiki/${m[1]}`} className="wlink" data-wikilink={m[1]}>
          {m[2]}
        </Link>,
      );
    } else if (m[3] !== undefined) {
      // [[id]]
      out.push(
        <Link key={k} href={`/wiki/${m[3]}`} className="wlink" data-wikilink={m[3]}>
          #{m[3]}
        </Link>,
      );
    } else {
      // [[Title]] — ghost (no resolvable id)
      out.push(
        <span key={k} className="wlink ghost" data-wikilink-ghost title="Ghost link — note chưa tồn tại">
          {m[4]}
        </span>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < line.length) out.push(...renderBold(line.slice(last), `${keyBase}-tEnd`));
  return out;
}

/** Render a block (paragraph / heading / list) — splits a paragraph's single
 *  newlines into <br>. */
function renderBlock(block: string, key: string): ReactNode {
  const trimmed = block.trimStart();
  // Heading: leading #'s
  const h = /^(#{1,3})\s+(.*)$/.exec(trimmed);
  if (h) {
    const level = h[1].length;
    const Tag = (`h${Math.min(level + 1, 4)}`) as "h2" | "h3" | "h4";
    return (
      <Tag key={key} className="wmd-h">
        {renderInline(h[2], key)}
      </Tag>
    );
  }
  // Unordered list: every line starts with "- " or "* "
  const lines = block.split("\n");
  const isList = lines.length > 0 && lines.every((l) => /^\s*[-*]\s+/.test(l));
  if (isList) {
    return (
      <ul key={key} className="wmd-ul">
        {lines.map((l, li) => (
          <li key={`${key}-li${li}`}>{renderInline(l.replace(/^\s*[-*]\s+/, ""), `${key}-li${li}`)}</li>
        ))}
      </ul>
    );
  }
  // Paragraph: single newlines → <br>
  return (
    <p key={key}>
      {lines.map((l, li) => (
        <Fragment key={`${key}-p${li}`}>
          {li > 0 && <br />}
          {renderInline(l, `${key}-p${li}`)}
        </Fragment>
      ))}
    </p>
  );
}

/**
 * Render a markdown wiki-note body to React nodes. Blank line separates blocks.
 * Empty content → an empty-state span (not a crash).
 */
export function WikiLinkRenderer({ content }: { content: string }) {
  const body = (content ?? "").trim();
  if (!body) {
    return (
      <span className="wmd-empty faint" data-testid="wiki-body-empty">
        (note chưa có nội dung)
      </span>
    );
  }
  const blocks = body.split(/\n{2,}/);
  return (
    <div className="wnote-body" data-testid="wiki-body">
      {blocks.map((b, i) => renderBlock(b, `blk${i}`))}
    </div>
  );
}
