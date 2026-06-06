"""modules/claude_usage — Claude Usage feature module (Sprint 7, SPEC §S9).

Reads REAL token usage from ~/.claude/stats-cache.json; derives cost from a
pricing table (stats-cache costUSD is often 0). Quota cap / reset-window /
per-project are NOT on disk → cap is a configurable default + manual override,
reset/weekly/byProject are honest stubs. The registry discovers MODULE from
router.py (T2). GET /claude-usage (ARCH §7).
"""
