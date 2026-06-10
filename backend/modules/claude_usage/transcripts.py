"""modules/claude_usage/transcripts.py — parse Claude Code session .jsonl (LIVE source).

stats-cache.json stopped regenerating (died 2026-04-17), but ~/.claude/projects/
<slug>/*.jsonl is written live on every turn. Each `type:assistant` line carries a
real `message.usage` block + model + cwd + timestamp — the true token/cost source,
and (via cwd) per-project attribution that stats-cache never had.

INCREMENTAL: 1.6GB across 6k+ files can't be re-parsed per request. We cache a
per-file aggregate keyed by (path, mtime, size); an unchanged file (closed session)
returns its cached aggregate instantly. Only the actively-written file re-parses.

READ-ONLY, fail-open: a missing dir / unreadable file / malformed line is skipped,
never raised — the service degrades, like reader.read_stats.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from core.config import settings

logger = logging.getLogger("life-os.claude_usage.transcripts")

# Project slugs to skip — scratch/temp sessions, not real projects.
_SKIP_PROJECTS = {"-tmp", "-"}


@dataclass
class Agg:
    """A token aggregate (one file, one project, one model — composable by +=)."""

    input: int = 0
    output: int = 0
    cacheRead: int = 0
    cacheCreate: int = 0
    cacheCreate1h: int = 0  # subset of cacheCreate written with the 1-hour TTL (2× rate)
    msgs: int = 0
    # per-model + per-day + per-project sub-aggregates (only populated at the roll-up)
    byModel: dict[str, "Agg"] = field(default_factory=dict)
    byDate: dict[str, int] = field(default_factory=dict)  # date → output tokens
    byProject: dict[str, "Agg"] = field(default_factory=dict)

    def _bump(self, in_t: int, out_t: int, cr: int, cc: int, cc1h: int) -> None:
        """Add raw token counts to THIS aggregate's flat totals (no sub-aggregates)."""
        self.input += in_t
        self.output += out_t
        self.cacheRead += cr
        self.cacheCreate += cc
        self.cacheCreate1h += cc1h
        self.msgs += 1

    def add_usage(self, u: dict, model: str, date: str, project: str) -> None:
        """Fold one assistant message's usage into this aggregate + sub-aggregates."""
        in_t = int(u.get("input_tokens", 0) or 0)
        out_t = int(u.get("output_tokens", 0) or 0)
        cr = int(u.get("cache_read_input_tokens", 0) or 0)
        cc = int(u.get("cache_creation_input_tokens", 0) or 0)
        # 1-hour cache-write subset (priced 2× vs 1.25× for 5m). Nested under
        # `cache_creation.ephemeral_1h_input_tokens`; absent on older transcripts → 0.
        cc1h = 0
        ccd = u.get("cache_creation")
        if isinstance(ccd, dict):
            cc1h = int(ccd.get("ephemeral_1h_input_tokens", 0) or 0)
        self._bump(in_t, out_t, cr, cc, cc1h)
        # per model
        self.byModel.setdefault(model, Agg())._bump(in_t, out_t, cr, cc, cc1h)
        # per day (output tokens, for the daily chart)
        if date:
            self.byDate[date] = self.byDate.get(date, 0) + out_t
        # per project (with its own per-model split so cost can be priced exactly)
        p = self.byProject.setdefault(project, Agg())
        p._bump(in_t, out_t, cr, cc, cc1h)
        p.byModel.setdefault(model, Agg())._bump(in_t, out_t, cr, cc, cc1h)


def _is_claude(model: str) -> bool:
    """Claude-only (exclude MiniMax/glm/gpt/arcee in the same transcripts)."""
    return str(model).startswith("claude-")


def _parse_file(path: Path) -> Agg:
    """Parse ONE .jsonl → a flat Agg (no sub-aggregates; project filled by caller).

    Cheap pre-filter: skip lines without the assistant+usage markers before json.loads
    (most lines are user/snapshot/etc). Never raises — a bad line is skipped.
    """
    agg = Agg()
    project = _project_of(path)
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                # Cheap pre-filter to skip the ~75% of lines that aren't billable
                # assistant turns before the (costly) json.loads. Whitespace-tolerant:
                # real CC writes compact ("type":"assistant") but fixtures/other
                # writers may add spaces, so match on the tokens, not exact bytes.
                if '"usage"' not in line or "assistant" not in line:
                    continue
                try:
                    o = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if o.get("type") != "assistant":
                    continue
                msg = o.get("message") or {}
                u = msg.get("usage")
                model = msg.get("model")
                if not isinstance(u, dict) or not isinstance(model, str) or not _is_claude(model):
                    continue
                ts = o.get("timestamp") or ""
                date = ts[:10] if isinstance(ts, str) and len(ts) >= 10 else ""
                # cwd basename = human project name; fall back to the dir slug
                cwd = o.get("cwd")
                proj = os.path.basename(cwd) if isinstance(cwd, str) and cwd else project
                agg.add_usage(u, model, date, proj)
    except OSError as exc:
        logger.warning("transcript unreadable %s (%s) — skipped", path, exc)
    return agg


def _project_of(path: Path) -> str:
    """Fallback project label from the dir slug (when a message has no cwd)."""
    return path.parent.name


# --------------------------------------------------------------------------- #
# Incremental file cache: (path → (mtime, size, Agg))                          #
# --------------------------------------------------------------------------- #
_CACHE: dict[str, tuple[float, int, Agg]] = {}


def _add_flat(into: Agg, src: Agg) -> None:
    """Add src's flat totals into `into` (all token fields + msgs; no sub-aggregates)."""
    into.input += src.input
    into.output += src.output
    into.cacheRead += src.cacheRead
    into.cacheCreate += src.cacheCreate
    into.cacheCreate1h += src.cacheCreate1h
    into.msgs += src.msgs


def _merge(into: Agg, part: Agg) -> None:
    """Fold a per-file Agg (which already carries byModel/byDate/byProject) into the roll-up."""
    _add_flat(into, part)
    for model, a in part.byModel.items():
        _add_flat(into.byModel.setdefault(model, Agg()), a)
    for date, out in part.byDate.items():
        into.byDate[date] = into.byDate.get(date, 0) + out
    for proj, a in part.byProject.items():
        p = into.byProject.setdefault(proj, Agg())
        _add_flat(p, a)
        for model, am in a.byModel.items():
            _add_flat(p.byModel.setdefault(model, Agg()), am)


def aggregate(projects_dir: str | Path | None = None) -> Agg | None:
    """Roll up ALL session transcripts → one Agg with byModel/byDate/byProject.

    Incremental: an unchanged file (same mtime+size) reuses its cached per-file Agg;
    only new/changed files re-parse. None if the projects dir is absent/empty (the
    service then falls back to stats-cache or manual — never an exception).
    """
    base = Path(projects_dir) if projects_dir is not None else Path(settings.claude_projects_dir)
    base = base.expanduser()
    if not base.is_dir():
        logger.info("claude projects dir not found at %s — no transcript data", base)
        return None

    roll = Agg()
    seen_any = False
    for proj_dir in base.iterdir():
        if not proj_dir.is_dir() or proj_dir.name in _SKIP_PROJECTS:
            continue
        for path in proj_dir.glob("*.jsonl"):
            try:
                st = path.stat()
            except OSError:
                continue
            key = str(path)
            cached = _CACHE.get(key)
            if cached and cached[0] == st.st_mtime and cached[1] == st.st_size:
                part = cached[2]  # unchanged → reuse
            else:
                part = _parse_file(path)
                _CACHE[key] = (st.st_mtime, st.st_size, part)
            seen_any = True
            _merge(roll, part)
    return roll if seen_any else None
