"""modules/reminders — single-user reminders / agenda (REMINDERS-1, #27).

GAP-4: answer "what's on my plate this week." A reminder is an alarm/agenda item — a title + a
due instant + an optional repeat/re-notify policy. #27 is the STORAGE CORE: CRUD + the tick
lifecycle + due/done filters, in a module-owned SQLite table (`reminders`, same init-on-first-use
pattern as news/macro). The notify routine (#29), MCP tools (#28), brief surface (#30), and FE
(#31) all build on this frozen schema.

Single-user, no auth, no multi-user (north-star). The registry discovers MODULE from router.py.
"""

from .router import MODULE

__all__ = ["MODULE"]
