"""modules/news — real-time news capture + grounded read (NEWS-1).

The problem this solves: an agent asked "what news/events are notable?" otherwise
answers from stale training knowledge = fabrication. The honest path (same instinct
as wiki grounded retrieval): CAPTURE real headlines from public feeds → STORE each
with its SOURCE url + published timestamp + asset/topic tags → the agent only ever
SUMMARISES what was actually captured, citing the source. Nothing is invented.

Capture source = FREE, no-key public RSS feeds (CoinDesk, CNBC, etc.). RSS is plain
XML — parsed with the stdlib (no new dependency). Any source needing a key/payment is
NOT called: a marked mock + warning is surfaced instead, never a block.

Storage = one module-owned SQLite table (`news_items`) on the shared connection
(same pattern as macro_history / price_history) — news is time-series (by published
ts), so SQLite, not md_store (ARCH §6). Dedup by source url (a story never repeats).

The registry discovers MODULE from router.py.
"""
