"""modules/tracing/reader.py — tracing READ surface (DAILY-TRACING-P1, #65).

The read-only entrypoints the router (and P2 MCP) call to GET tracing data. Tracing is
derive-heavy: every read metric is computed in ``service`` from the raw logs (raw-data-first),
so this reader is a thin, honest indirection over the service's derivations — it exists as the
named read-surface (parity with the other modules' reader.py) without duplicating the derive
logic. NO writes here (reads only); NO recomputation outside ``service``.
"""

from __future__ import annotations

from . import service
from .schema import Activity, ActivityView, TracingOverview


def get_overview() -> TracingOverview:
    """The whole tracing board for today-VN (delegates to the service derivations)."""
    return service.overview()


def get_activity(activity_id: str) -> Activity | None:
    """One activity def (incl. archived), or None if absent."""
    return service.get_activity(activity_id)


def get_activity_view(activity_id: str) -> ActivityView | None:
    """One activity's full derived card (today/streak/week/history12w), or None if absent."""
    act = service.get_activity(activity_id)
    if act is None or act.archived:
        return None
    return service._derive_activity_view(act)
