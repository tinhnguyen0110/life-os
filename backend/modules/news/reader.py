"""modules/news/reader.py — RSS capture (NEWS-1).

Fetches public, FREE, NO-KEY RSS feeds and parses them with the stdlib XML parser
(no new dependency — RSS/Atom is plain XML). Handles both RSS 2.0 (`<item>`) and
Atom (`<entry>`) shapes.

FAIL-OPEN (honesty-critical): any feed timeout / non-200 / network error / malformed
XML → that feed yields ZERO items + a warning; it NEVER raises and never blocks the
other feeds. A feed that needs a key/payment is simply NOT configured here — we never
call a paid endpoint. If NO feed yields anything, the caller keeps whatever is already
in the store (last-fetched cache) — we never fabricate a headline.

Tagging is rule-based + conservative: an item is tagged with an asset symbol only when
that asset's name/symbol literally appears in the title/summary (substring, word-ish).
No tag is invented; an item with no match simply carries its feed's topic tag(s).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger("life-os.news.reader")

FETCH_TIMEOUT_S = 8.0
MAX_BYTES = 2_000_000  # cap a feed response (defensive — never read an unbounded body)
MAX_ITEMS_PER_FEED = 25


class Feed:
    """A configured RSS source: a display name, its url, and the topic tags every item
    from it carries by default (e.g. a crypto feed tags everything 'CRYPTO')."""

    def __init__(self, name: str, url: str, topics: list[str]) -> None:
        self.name = name
        self.url = url
        self.topics = topics


# Default FREE, no-key public RSS feeds. Override the whole set via LIFEOS_NEWS_FEEDS
# (JSON list of {name,url,topics}). These are well-known public RSS endpoints — no key.
_DEFAULT_FEEDS: list[Feed] = [
    Feed("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", ["CRYPTO"]),
    Feed("CoinTelegraph", "https://cointelegraph.com/rss", ["CRYPTO"]),
    Feed("CNBC Finance", "https://www.cnbc.com/id/10000664/device/rss/rss.html", ["FINANCE", "MACRO"]),
]


def configured_feeds() -> list[Feed]:
    """The active feed set. Env override (LIFEOS_NEWS_FEEDS JSON) wins; else defaults."""
    raw = os.environ.get("LIFEOS_NEWS_FEEDS")
    if raw:
        try:
            import json

            data = json.loads(raw)
            feeds = [
                Feed(d["name"], d["url"], list(d.get("topics", [])))
                for d in data
                if isinstance(d, dict) and d.get("name") and d.get("url")
            ]
            if feeds:
                return feeds
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("LIFEOS_NEWS_FEEDS malformed (%s) — using defaults", exc)
    return list(_DEFAULT_FEEDS)


# Asset keyword → canonical tag. Conservative literal matching only (no inference).
_ASSET_KEYWORDS: dict[str, str] = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "ether": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
    "federal reserve": "FED", "the fed": "FED", "fomc": "FED",
    "inflation": "CPI", "cpi": "CPI",
    "nasdaq": "NASDAQ", "s&p 500": "SPX", "s&p500": "SPX",
}
# Word-boundary patterns so 'sol' doesn't match 'solution', 'eth' not 'method', etc.
_ASSET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", re.IGNORECASE), tag)
    for kw, tag in _ASSET_KEYWORDS.items()
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_tags(title: str, summary: str, topics: list[str]) -> list[str]:
    """Topic tags (from the feed) + any asset symbol that LITERALLY appears in the
    title/summary. Conservative — never invents a tag. De-duplicated, order-stable."""
    text = f"{title} {summary}"
    out: list[str] = list(topics)
    for pat, tag in _ASSET_PATTERNS:
        if tag not in out and pat.search(text):
            out.append(tag)
    # de-dup preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in out:
        u = t.strip().upper()
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped


def _normalize_ts(raw: str | None) -> str:
    """Parse an RSS/Atom date (RFC-822 or ISO-8601) → ISO-8601 UTC. Unparseable /
    missing → now (so it still sorts sensibly; never crashes)."""
    if not raw or not raw.strip():
        return _now_iso()
    s = raw.strip()
    # RSS 2.0 pubDate is RFC-822 ("Mon, 15 Jun 2026 09:00:00 GMT").
    try:
        dt = parsedate_to_datetime(s)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        pass
    # Atom updated/published is ISO-8601 ("2026-06-15T09:00:00Z").
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        return _now_iso()


def _strip_ns(tag: str) -> str:
    """Drop an XML namespace prefix: '{http://www.w3.org/2005/Atom}entry' → 'entry'."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _find_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if _strip_ns(child.tag) == name:
            return child
    return None


def _extract_link(entry: ET.Element) -> str:
    """RSS: <link>text</link>. Atom: <link href="..."/> (prefer rel='alternate')."""
    alt = ""
    fallback = ""
    for child in entry:
        if _strip_ns(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            if child.attrib.get("rel", "alternate") == "alternate":
                alt = href
            elif not fallback:
                fallback = href
        elif child.text and child.text.strip():
            fallback = child.text.strip()
    return alt or fallback


def parse_feed_xml(xml_text: str, feed: Feed) -> list[dict]:
    """Parse one feed's XML → a list of raw item dicts (title/summary/url/ts/source/tags).
    Returns [] on malformed XML (caller fail-opens). Handles RSS <item> + Atom <entry>."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("news: feed %r XML parse failed: %s", feed.name, exc)
        return []

    # RSS items live under channel/item; Atom entries are direct children of feed.
    entries: list[ET.Element] = []
    for el in root.iter():
        if _strip_ns(el.tag) in ("item", "entry"):
            entries.append(el)

    items: list[dict] = []
    for entry in entries[:MAX_ITEMS_PER_FEED]:
        title = _text(_find_child(entry, "title"))
        if not title:
            continue  # an item with no title is unusable — skip (never fabricate one)
        url = _extract_link(entry)
        if not url:
            continue  # no source link = no grounding anchor — skip
        summary = _text(_find_child(entry, "description")) or _text(_find_child(entry, "summary"))
        summary = re.sub(r"<[^>]+>", "", summary).strip()  # strip any HTML tags
        if len(summary) > 500:
            summary = summary[:497] + "…"
        ts_raw = (
            _text(_find_child(entry, "pubDate"))
            or _text(_find_child(entry, "published"))
            or _text(_find_child(entry, "updated"))
        )
        items.append({
            "title": title,
            "summary": summary,
            "url": url,
            "source": feed.name,
            "published_ts": _normalize_ts(ts_raw),
            "tags": infer_tags(title, summary, feed.topics),
        })
    return items


def fetch_feed(feed: Feed) -> tuple[list[dict], str | None]:
    """Fetch + parse one feed. FAIL-OPEN: returns ([], warning) on any error; never raises."""
    try:
        resp = httpx.get(
            feed.url,
            timeout=FETCH_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "life-os-news/1.0 (+local)"},
        )
    except httpx.HTTPError as exc:
        return [], f"{feed.name}: fetch error ({type(exc).__name__})"
    if resp.status_code != 200:
        return [], f"{feed.name}: HTTP {resp.status_code}"
    body = resp.text
    if len(body.encode("utf-8", "ignore")) > MAX_BYTES:
        body = body[: MAX_BYTES // 2]  # defensive truncation; parser tolerates a cut tail
    items = parse_feed_xml(body, feed)
    if not items:
        return [], f"{feed.name}: no items parsed"
    return items, None
