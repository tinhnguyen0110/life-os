"""modules/news/service.py — capture orchestration + grounded reads (NEWS-1).

Three jobs:
  - capture(): fetch every configured feed (fail-open per feed), upsert into the store
    (dedup by url), return (new_count, warnings). NEVER raises; a fully-failed sweep
    keeps whatever is already stored (last-fetched cache) — no fabrication.
  - list_news(tag, limit): captured headlines newest-first, optional exact-tag filter.
  - digest(): a NEUTRAL roll-up — ONLY captured items, each citing its source url. No
    commentary, no prediction, no good/bad-for-price. Honest empty-state when nothing
    has been captured.

Honesty contract (the whole point of this module): the digest is a *projection* of the
store, never an opinion. The headline is a factual count sentence. There is no code path
that adds analysis, sentiment, or a price call.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import reader, store
from .schema import DigestItem, NewsDigest, NewsItem, NewsList

logger = logging.getLogger("life-os.news.service")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_item(row) -> NewsItem:
    return NewsItem(
        id=int(row["id"]),
        title=row["title"],
        summary=row["summary"] or "",
        url=row["url"],
        source=row["source"] or "",
        publishedTs=row["published_ts"],
        tags=store._unpad_tags(row["tags"]),
    )


def capture() -> tuple[int, list[str]]:
    """Fetch all configured feeds + persist (dedup). Returns (new_items, warnings).

    Fail-open per feed: one broken feed warns + is skipped, never aborts the sweep.
    A fully-failed sweep returns (0, warnings) and leaves the store untouched (the
    last-fetched items remain readable — cache, not fabrication).
    """
    captured_at = _now_iso()
    new_count = 0
    warnings: list[str] = []
    any_ok = False

    for feed in reader.configured_feeds():
        items, warn = reader.fetch_feed(feed)
        if warn:
            warnings.append(warn)
        if not items:
            continue
        any_ok = True
        for it in items:
            try:
                is_new = store.upsert_item(
                    title=it["title"], summary=it["summary"], url=it["url"],
                    source=it["source"], published_ts=it["published_ts"],
                    tags=it["tags"], captured_at=captured_at,
                )
                if is_new:
                    new_count += 1
            except Exception as exc:  # one bad row never aborts the sweep
                logger.warning("news: store upsert failed for %r: %s", it.get("url"), exc)
                warnings.append(f"store error for one item ({type(exc).__name__})")

    if not any_ok and warnings:
        logger.info("news: capture sweep yielded nothing — keeping last-fetched cache")
    return new_count, warnings


def list_news(tag: str | None = None, limit: int = 30) -> NewsList:
    """Captured headlines, newest-first. Optional exact-tag filter (unknown tag → [])."""
    rows = store.list_items(tag=tag, limit=limit)
    items = [_row_to_item(r) for r in rows]
    return NewsList(
        items=items,
        count=len(items),
        asOf=store.latest_capture_ts(),
        tag=(tag.strip().upper() if tag and tag.strip() else None),
    )


def digest(tag: str | None = None, limit: int = 10) -> NewsDigest:
    """A NEUTRAL, source-cited roll-up of captured news. ONLY lists what's in the store;
    each line carries its source url. NO commentary / prediction / sentiment. Honest
    empty-state when nothing has been captured (never invents a headline)."""
    rows = store.list_items(tag=tag, limit=limit)
    total = store.count_items()
    as_of = store.latest_capture_ts()

    if not rows:
        if total == 0:
            note = "Chưa có tin nào được capture. (Honest empty — không bịa tin.)"
        else:
            note = (
                f"Không có tin nào khớp tag {tag!r}."
                if tag and tag.strip()
                else "Chưa có tin nào được capture."
            )
        return NewsDigest(headline="0 tin đáng chú ý đã được capture.", items=[], count=0, asOf=as_of, note=note)

    items = [
        DigestItem(
            title=r["title"], source=r["source"] or "",
            url=r["url"], publishedTs=r["published_ts"],
            tags=store._unpad_tags(r["tags"]),
        )
        for r in rows
    ]
    scope = f" về {tag.strip().upper()}" if tag and tag.strip() else ""
    # Purely factual count sentence — NO opinion, NO prediction, NO good/bad.
    headline = f"{len(items)} tin đáng chú ý đã được capture{scope} (mỗi tin kèm nguồn)."
    return NewsDigest(headline=headline, items=items, count=len(items), asOf=as_of, note=None)
