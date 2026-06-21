"""modules/brief/reader.py — cross-module fail-soft read harness (S11).

Pulls each source module's data for the brief generator, fail-soft PER SOURCE (one
module erroring → that source is None + a warning, the brief still generates from the
rest). Mirrors automation.morning_pull's pull pattern, but returns the structured
data (not a summary string) for the priority rules to evaluate.

READ-ONLY. NO business logic here — this is plumbing; the priority RULES (which read
this data) live in service.py per the architect's decided Logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("life-os.brief.reader")


@dataclass
class Sources:
    """The cross-module snapshot the brief rules read. Any field is None if its source
    failed (fail-soft); ``warnings`` collects the per-source failure notes."""

    projects: list | None = None          # list[ProjectStatus]
    finance: object | None = None         # FinanceOverview
    market: dict | None = None            # {quotes, triggers, macro}
    claude: object | None = None          # ClaudeUsage
    reminders: list | None = None         # REMINDERS-4 (#30): list[Reminder] un-done (week+overdue)
    tracing: object | None = None         # DAILY-TRACING-P4 (#65): TracingOverview (for streak-at-risk)
    # WIKI-CONTEXT (#36): {recentOps: list[dict], clusters: list[dict]} or None if wiki down.
    # recentOps = wiki_reader.recent_ops() rows; clusters = wiki_reader.detect_clusters().
    wiki: dict | None = None
    warnings: list[str] = field(default_factory=list)


def pull() -> Sources:
    """Read all source modules, fail-soft per source. Never raises."""
    src = Sources()

    try:
        from modules.projects import service as proj
        statuses, w = proj.list_projects()
        src.projects = statuses
        src.warnings.extend(w or [])
    except Exception as exc:
        logger.error("brief: projects read failed: %s", exc)
        src.warnings.append(f"projects nguồn lỗi ({type(exc).__name__})")

    try:
        from modules.finance import service as fin
        overview, w = fin.get_overview()
        src.finance = overview
        src.warnings.extend(w or [])
    except Exception as exc:
        logger.error("brief: finance read failed: %s", exc)
        src.warnings.append(f"finance nguồn lỗi ({type(exc).__name__})")

    try:
        from modules.market import service as mkt
        data, w = mkt.get_market()
        src.market = data
        src.warnings.extend(w or [])
    except Exception as exc:
        logger.error("brief: market read failed: %s", exc)
        src.warnings.append(f"market nguồn lỗi ({type(exc).__name__})")

    try:
        from modules.claude_usage import service as cu
        src.claude = cu.get_usage()
    except Exception as exc:
        logger.error("brief: claude_usage read failed: %s", exc)
        src.warnings.append(f"claude nguồn lỗi ({type(exc).__name__})")

    try:
        # REMINDERS-4 (#30): un-done reminders for the priority rule. 'undone' gives all un-done
        # (the rule filters overdue/due-today via the reader's overdue field + due_at) — reuse the
        # #29 reader, no new read path.
        from modules.reminders import service as rem
        view, w = rem.list_reminders("undone")
        src.reminders = view.reminders
        src.warnings.extend(w or [])
    except Exception as exc:
        logger.error("brief: reminders read failed: %s", exc)
        src.warnings.append(f"reminders nguồn lỗi ({type(exc).__name__})")

    try:
        # DAILY-TRACING-P4 (#65): the habit board for the streak-at-risk rule. Reuse the SAME
        # derived overview GET /tracing + the MCP tracing_overview wrap — no new read path, no
        # new derivation (the brief READS the already-derived streak/today.done).
        from modules.tracing import reader as trc
        src.tracing = trc.get_overview()
    except Exception as exc:
        logger.error("brief: tracing read failed: %s", exc)
        src.warnings.append(f"tracing nguồn lỗi ({type(exc).__name__})")

    try:
        # WIKI-CONTEXT (#36): the wiki-graph context (recent note activity + notable clusters).
        # REUSE the existing wiki reader surfaces — recent_ops (the op-log feed) + detect_clusters
        # (the MOC-candidate clusters) — NO recompute, NO new read path. Deterministic (no model).
        from modules.wiki import reader as wiki_reader
        src.wiki = {
            # recent_activity = the TITLED op-log feed ({ts, op, actor, noteId, noteTitle, detail});
            # the service filters to create|edit + caps. clusters = the MOC-candidate clusters.
            "recentOps": wiki_reader.recent_activity(20),
            "clusters": wiki_reader.detect_clusters(),
        }
    except Exception as exc:
        logger.error("brief: wiki read failed: %s", exc)
        src.warnings.append(f"wiki nguồn lỗi ({type(exc).__name__})")

    return src
