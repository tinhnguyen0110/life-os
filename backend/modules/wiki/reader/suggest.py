"""modules/wiki/reader/suggest.py — WIKI-SUGGEST-LINK (#34): suggested links for a note.

Post-#25 write-through, an agent writes a note but may not link it → the graph fragments. ``suggest_links``
FTS-searches the note's TITLE against the rest of the vault (matching it against each other note's full
indexed title+body) and returns the top NEW link candidates, so the agent (or UI) can link the fresh note
+ keep the graph connected. DETERMINISTIC (FTS5 relevance, NO AI) and SUGGEST-ONLY (never auto-applies a
link). Querying by TITLE (not full content) is a deliberate #34 call — see the fn body for why (real-vault
common-word noise); falls back to content only for a title-less note.

Return shape (frozen #34, #107-updated): ``[{id: int, title: str, score: float, relevance: float}]`` —
top 3-5, more-relevant first. ``relevance`` is the #99/#107 agent-readable 0..1 magnitude (= ``1 -
exp(score)``, higher = stronger match — the SAME 1-exp value wiki_search returns, reused not recomputed);
``score`` is the raw bm25 rank (≤0, more-negative=better) kept for transparency, mirroring search's shape.
(#107 fixed a path #99 missed: this used to surface the RAW negative ``score`` AS ``relevance``, which an
agent can't read.) EXCLUDES the note ITSELF and notes ALREADY LINKED from it (resolved outbound edges) —
only NEW candidates. No match → ``[]`` (honest-empty, never raises — the FTS store sanitizes bad queries).

Living in ``reader`` (not the write path or MCP/REST layer) makes it the ONE source of truth — the
write-through response, the optional MCP tool, and the REST endpoint all call this, so they can't drift
(#24, same pattern as reader.context).
"""

from __future__ import annotations

from typing import Any

from .backlinks import backlinks


def suggest_links(note_id: int, limit: int = 5) -> list[dict[str, Any]]:
    """Top NEW link candidates for ``note_id`` (see module docstring). FTS the note's title+content,
    EXCLUDE self + already-linked (resolved outbound), map to {id,title,score,relevance}, top ``limit``
    (default 5; 3-5 band). ``relevance`` = the #99/#107 1-exp 0..1 (agent-readable), ``score`` = raw
    bm25. Missing note or no matches → ``[]`` (never raises)."""
    from .backlinks import search as _fts
    from ..service import get_note as _get_note

    note = _get_note(int(note_id))
    if note is None:
        return []

    # DECIDE-AND-LOG (#34, verified on the real vault): query FTS with the note's TITLE, not
    # title+content. The title is the high-signal topic descriptor; querying the full body matches
    # COMMON words ("token", "unique", "data"…) against every note in a populated vault → noisy,
    # low-relevance suggestions, and a genuinely-unrelated note would NEVER get the honest-empty []
    # the spec wants. Title-only gives clean topic matches + honest-empty for a truly-new topic
    # (proven: a unique-title note → [] vs title+content → spurious common-word hits). Falls back to
    # content ONLY if the note has no title (capture/fleeting notes). The FTS store sanitizes special
    # chars / bad queries → [] (never raises).
    query = (note.title or note.content or "").strip()
    if not query:
        return []

    # over-fetch (limit + the count we'll exclude) so after dropping self + already-linked we still
    # have up to `limit` NEW candidates.
    already_linked = {e["id"] for e in backlinks(int(note_id))["outbound"]
                      if e.get("isResolved") and e.get("id") is not None}
    exclude = already_linked | {int(note_id)}
    raw = _fts(query, limit=int(limit) + len(exclude) + 5)

    out: list[dict[str, Any]] = []
    for hit in raw:
        if hit["id"] in exclude:
            continue
        # #107: surface the #99 1-exp ``relevance`` (0..1, agent-readable) that backlinks.search
        # already computed — NOT the raw negative bm25 ``score``. Carry ``score`` too so suggest's
        # shape mirrors search's {id,title,score,relevance} (parity + transparency). Do NOT recompute
        # the transform — reuse the value in the hit.
        out.append({"id": hit["id"], "title": hit["title"],
                    "score": hit["score"], "relevance": hit["relevance"]})
        if len(out) >= int(limit):
            break
    return out
