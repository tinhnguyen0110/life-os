"""tests/test_news_backend.py — news module: parse / dedup / tag / digest / fail-open (NEWS-1).

Behavior-tested against a FIXED mock RSS feed (no network): RSS+Atom parse, dedup by
url, exact-tag filter, digest cites every source + is NEUTRAL (no good/bad/predict
words), fail-open on a broken feed, and honest-empty when nothing captured.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from modules.news import reader, service, store
from modules.news.reader import Feed

# --------------------------------------------------------------------------- #
# Fixed mock feeds (no network)
# --------------------------------------------------------------------------- #
RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>MockWire</title>
  <item>
    <title>Bitcoin ETF sees record inflows</title>
    <description>A &lt;b&gt;big&lt;/b&gt; week for BTC funds.</description>
    <link>https://mock.example/btc-etf</link>
    <pubDate>Mon, 15 Jun 2026 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Ethereum upgrade ships on mainnet</title>
    <description>Ether devs deploy the update.</description>
    <link>https://mock.example/eth-upgrade</link>
    <pubDate>Mon, 15 Jun 2026 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Untitled-link-missing</title>
    <description>no link here</description>
  </item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>AtomWire</title>
  <entry>
    <title>Federal Reserve holds rates steady</title>
    <summary>The FOMC kept policy unchanged.</summary>
    <link rel="alternate" href="https://mock.example/fed-hold"/>
    <published>2026-06-15T07:00:00Z</published>
  </entry>
</feed>"""

RSS_FEED = Feed("MockWire", "https://mock.example/rss", ["CRYPTO"])
ATOM_FEED = Feed("AtomWire", "https://mock.example/atom", ["MACRO"])

# Forbidden tokens — the digest must be NEUTRAL (no sentiment / prediction / advice).
FORBIDDEN = ["tốt cho giá", "xấu cho giá", "nên mua", "nên bán", "dự đoán",
             "bullish", "bearish", "should buy", "will rise", "will fall", "predict"]


# --------------------------------------------------------------------------- #
# parse
# --------------------------------------------------------------------------- #
def test_parse_rss_extracts_items_and_strips_html():
    items = reader.parse_feed_xml(RSS_XML, RSS_FEED)
    assert len(items) == 2  # the link-less item is skipped (no grounding anchor)
    btc = next(i for i in items if "Bitcoin" in i["title"])
    assert btc["url"] == "https://mock.example/btc-etf"
    assert "<b>" not in btc["summary"] and "big" in btc["summary"]  # HTML stripped
    assert btc["source"] == "MockWire"


def test_parse_atom_link_href_and_iso_ts():
    items = reader.parse_feed_xml(ATOM_XML, ATOM_FEED)
    assert len(items) == 1
    fed = items[0]
    assert fed["url"] == "https://mock.example/fed-hold"
    assert fed["published_ts"].startswith("2026-06-15T07:00:00")


def test_parse_malformed_xml_returns_empty():
    assert reader.parse_feed_xml("<not valid xml", RSS_FEED) == []
    assert reader.parse_feed_xml("", RSS_FEED) == []


def test_infer_tags_literal_only_no_invention():
    # 'Bitcoin' → BTC + feed topic CRYPTO; no spurious tags.
    tags = reader.infer_tags("Bitcoin rallies", "btc up", ["CRYPTO"])
    assert "BTC" in tags and "CRYPTO" in tags
    assert "ETH" not in tags and "FED" not in tags
    # word-boundary: 'solution' must NOT yield SOL
    assert "SOL" not in reader.infer_tags("A new solution emerges", "", [])


# --------------------------------------------------------------------------- #
# capture + dedup (fail-open) — mock fetch_feed
# --------------------------------------------------------------------------- #
@pytest.fixture
def mock_feeds(monkeypatch):
    """Replace the configured feeds + fetch with the fixed mock XML (no network)."""
    monkeypatch.setattr(reader, "configured_feeds", lambda: [RSS_FEED, ATOM_FEED])

    def fake_fetch(feed):
        if feed is RSS_FEED:
            return reader.parse_feed_xml(RSS_XML, RSS_FEED), None
        if feed is ATOM_FEED:
            return reader.parse_feed_xml(ATOM_XML, ATOM_FEED), None
        return [], f"{feed.name}: unknown"

    monkeypatch.setattr(reader, "fetch_feed", fake_fetch)


def test_capture_persists_and_dedups(isolated_paths, mock_feeds):
    new1, warn1 = service.capture()
    assert new1 == 3 and warn1 == []  # 2 RSS + 1 Atom (link-less skipped)
    assert store.count_items() == 3
    # re-capture the SAME feeds → 0 NEW (dedup by url), total unchanged
    new2, _ = service.capture()
    assert new2 == 0
    assert store.count_items() == 3


def test_capture_fail_open_one_broken_feed(isolated_paths, monkeypatch):
    monkeypatch.setattr(reader, "configured_feeds", lambda: [RSS_FEED, ATOM_FEED])

    def half_broken(feed):
        if feed is RSS_FEED:
            return reader.parse_feed_xml(RSS_XML, RSS_FEED), None
        return [], "AtomWire: HTTP 503"  # broken feed → warning, no crash

    monkeypatch.setattr(reader, "fetch_feed", half_broken)
    new, warnings = service.capture()
    assert new == 2  # RSS items still captured
    assert any("503" in w for w in warnings)
    assert store.count_items() == 2  # the good feed landed; broken one didn't block


def test_capture_all_feeds_fail_keeps_cache(isolated_paths, mock_feeds, monkeypatch):
    service.capture()  # seed 3 items
    assert store.count_items() == 3
    # now ALL feeds fail → 0 new, store untouched (cache preserved, NOT wiped)
    monkeypatch.setattr(reader, "fetch_feed", lambda f: ([], f"{f.name}: down"))
    new, warnings = service.capture()
    assert new == 0 and len(warnings) == 2
    assert store.count_items() == 3  # last-fetched cache intact


def test_fetch_feed_network_error_is_fail_open(isolated_paths, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "get", boom)
    items, warn = reader.fetch_feed(RSS_FEED)
    assert items == [] and warn is not None and "MockWire" in warn


# --------------------------------------------------------------------------- #
# list + tag filter
# --------------------------------------------------------------------------- #
def test_list_newest_first(isolated_paths, mock_feeds):
    service.capture()
    out = service.list_news(limit=10)
    assert out.count == 3
    ts = [i.publishedTs for i in out.items]
    assert ts == sorted(ts, reverse=True)  # newest first


def test_list_tag_filter_exact(isolated_paths, mock_feeds):
    service.capture()
    btc = service.list_news(tag="BTC")
    assert btc.count == 1 and "Bitcoin" in btc.items[0].title
    assert btc.tag == "BTC"
    # unknown tag → clean empty
    assert service.list_news(tag="DOGE").count == 0
    # case-insensitive
    assert service.list_news(tag="btc").count == 1


# --------------------------------------------------------------------------- #
# digest — cites sources + NEUTRAL + honest empty
# --------------------------------------------------------------------------- #
def test_digest_cites_every_source(isolated_paths, mock_feeds):
    service.capture()
    d = service.digest(limit=10)
    assert d.count == 3
    assert all(i.url.startswith("https://mock.example/") for i in d.items)
    assert d.headline.startswith("3 tin")
    assert d.note is None


def test_digest_is_neutral_no_sentiment(isolated_paths, mock_feeds):
    service.capture()
    d = service.digest(limit=10)
    blob = (d.headline + " " + " ".join(f"{i.title}" for i in d.items)).lower()
    for word in FORBIDDEN:
        assert word.lower() not in blob, f"digest must be neutral; found {word!r}"


def test_digest_empty_is_honest_not_fabricated(isolated_paths):
    d = service.digest()
    assert d.count == 0 and d.items == []
    assert "0 tin" in d.headline
    assert d.note and ("Chưa có tin" in d.note or "empty" in d.note.lower())


def test_digest_tag_no_match_is_honest(isolated_paths, mock_feeds):
    service.capture()
    d = service.digest(tag="DOGE")
    assert d.count == 0 and d.note is not None


# --------------------------------------------------------------------------- #
# API end-to-end
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(isolated_paths, mock_feeds):
    from main import app
    return TestClient(app)


def test_api_capture_then_list_and_digest(client):
    cap = client.post("/news/capture")
    assert cap.status_code == 200
    assert cap.json()["data"]["new"] == 3

    lst = client.get("/news?limit=5")
    assert lst.status_code == 200
    body = lst.json()
    assert body["success"] is True and body["data"]["count"] == 3
    assert all(i["url"] for i in body["data"]["items"])  # every item grounded

    dig = client.get("/news/digest")
    assert dig.status_code == 200
    dd = dig.json()["data"]
    assert dd["count"] == 3 and all(i["url"] for i in dd["items"])


def test_api_tag_filter(client):
    client.post("/news/capture")
    r = client.get("/news?tag=ETH")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1 and "Ethereum" in items[0]["title"]


def test_api_digest_empty_warning(client):
    # no capture → honest empty digest with a note (warning)
    r = client.get("/news/digest")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["count"] == 0
    assert body.get("warning")  # note surfaced as warning


def test_api_list_limit_validation(client):
    assert client.get("/news?limit=0").status_code == 422
    assert client.get("/news?limit=999").status_code == 422
