"""modules/claude_usage/reader.py — parse stats-cache.json (Sprint 7, fail-open).

READ-ONLY: loads ~/.claude/stats-cache.json (Claude Code's usage cache). NEVER
raises — a missing or malformed file returns None and the service degrades to
manual mode (the fail-open decision, like projects status.md / finance).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.config import settings

logger = logging.getLogger("life-os.claude_usage.reader")


def read_stats(path: str | Path | None = None) -> dict | None:
    """Load + JSON-parse the stats-cache file. None on missing/unreadable/malformed.

    ``path`` defaults to ``settings.claude_stats_path`` (env-overridable). A None
    return signals "manual mode" to the service — never an exception.
    """
    p = Path(path) if path is not None else Path(settings.claude_stats_path)
    p = p.expanduser()
    if not p.is_file():
        logger.warning("stats-cache.json not found at %s — manual mode", p)
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.warning("stats-cache.json unreadable/malformed (%s) — manual mode", exc)
        return None
    if not isinstance(data, dict):
        logger.warning("stats-cache.json is not a JSON object — manual mode")
        return None
    return data
