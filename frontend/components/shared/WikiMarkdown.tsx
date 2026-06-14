"use client";
/* ============================================================
   WikiMarkdown — the READ/preview renderer for a wiki note body (WEXP-FE polish).
   Proper CommonMark + GFM via react-markdown + remark-gfm (headings/lists/code/
   tables/quotes — the "dễ đọc" Obsidian-feel reading the hand-rolled renderer
   couldn't do), WHILE preserving `[[id|title]]` wikilinks → clickable /wiki/[id].

   The wikilink logic is REUSED from WikiLinkRenderer (not discarded): react-markdown
   gives us string text nodes, and a custom renderer post-splits every string child
   on the three wikilink forms → real Next <Link>s. So markdown structure comes from
   the lib; wikilink behavior stays ours. The EDIT surface stays a <textarea> (no
   heavy editor framework) — this is read-only render.
   ============================================================ */
import { Fragment, type ReactNode } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** The three wikilink forms (mock order, most specific first):
 *  [[47|title]] → labelled link · [[47]] → bare-id link · [[Title]] → ghost. */
const WIKILINK_RE = /\[\[(\d+)\|([^\]]+)\]\]|\[\[(\d+)\]\]|\[\[([^\]\d][^\]]*)\]\]/g;

/** title (lowercased) → note id, for resolving `[[Title]]` body links. Built by the
 *  caller from the note's resolved outbound edges (backend-computed). Absent / empty
 *  → every title link stays a ghost (the pre-resolution behavior). */
export type WikiLinkResolve = Map<string, number>;

/** Split a plain string into text + wikilink nodes (REUSED from WikiLinkRenderer).
 *  ``resolve`` maps a lowercased title → id so `[[Title]]` of an EXISTING note renders
 *  a clickable link (like the outbound-links panel); an unresolved title stays a ghost. */
function splitWikilinks(text: string, keyBase: string, resolve?: WikiLinkResolve): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  WIKILINK_RE.lastIndex = 0;
  while ((m = WIKILINK_RE.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const k = `${keyBase}-wl${i++}`;
    if (m[1] !== undefined) {
      out.push(<Link key={k} href={`/wiki/${m[1]}`} className="wlink" data-wikilink={m[1]}>{m[2]}</Link>);
    } else if (m[3] !== undefined) {
      out.push(<Link key={k} href={`/wiki/${m[3]}`} className="wlink" data-wikilink={m[3]}>#{m[3]}</Link>);
    } else {
      // [[Title]] — resolve the title → id (case-insensitive) against the note's
      // resolved outbound edges. Resolvable → clickable link; else → ghost.
      const title = m[4];
      const id = resolve?.get(title.trim().toLowerCase());
      if (id !== undefined) {
        out.push(<Link key={k} href={`/wiki/${id}`} className="wlink" data-wikilink={id}>{title}</Link>);
      } else {
        out.push(<span key={k} className="wlink ghost" data-wikilink-ghost title="Ghost link — note chưa tồn tại">{title}</span>);
      }
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Walk react-markdown's rendered children; replace any string child with its
 *  wikilink-split nodes. Non-string children (already-rendered elements: bold,
 *  code, nested links) pass through untouched. */
function withWikilinks(children: ReactNode, keyBase: string, resolve?: WikiLinkResolve): ReactNode {
  const arr = Array.isArray(children) ? children : [children];
  return arr.map((child, i) =>
    typeof child === "string"
      ? <Fragment key={`${keyBase}-${i}`}>{splitWikilinks(child, `${keyBase}-${i}`, resolve)}</Fragment>
      : child,
  );
}

export function WikiMarkdown(
  { content, testId, resolve }: { content: string; testId?: string; resolve?: WikiLinkResolve },
) {
  const body = (content ?? "").trim();
  if (!body) {
    return (
      <span className="wmd-empty faint" data-testid={testId ? `${testId}-empty` : "wiki-body-empty"}>
        (note chưa có nội dung)
      </span>
    );
  }
  return (
    <div className="wnote-body wmd" data-testid={testId ?? "wiki-body"}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Inject wikilink-splitting into every block that holds inline text. The
          // children may be strings (→ split) or elements (bold/code/em → kept).
          p: ({ children }) => <p>{withWikilinks(children, "p", resolve)}</p>,
          li: ({ children }) => <li>{withWikilinks(children, "li", resolve)}</li>,
          h1: ({ children }) => <h2 className="wmd-h">{withWikilinks(children, "h1", resolve)}</h2>,
          h2: ({ children }) => <h2 className="wmd-h">{withWikilinks(children, "h2", resolve)}</h2>,
          h3: ({ children }) => <h3 className="wmd-h">{withWikilinks(children, "h3", resolve)}</h3>,
          h4: ({ children }) => <h4 className="wmd-h">{withWikilinks(children, "h4", resolve)}</h4>,
          td: ({ children }) => <td>{withWikilinks(children, "td", resolve)}</td>,
          th: ({ children }) => <th>{withWikilinks(children, "th", resolve)}</th>,
          blockquote: ({ children }) => <blockquote className="wmd-quote">{children}</blockquote>,
          // links the markdown itself contains ([text](url)) — keep as plain anchors.
          a: ({ href, children }) => <a href={href} className="wlink" target="_blank" rel="noreferrer">{children}</a>,
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
