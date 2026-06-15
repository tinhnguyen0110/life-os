"""modules/news/router.py — News REST endpoints + capture routine (NEWS-1).

Mounts at ``/news`` via the registry (``MODULE``). Locked envelope
``{success, data, warning?}``. Business logic is in service.py; this layer is HTTP
shape + status codes only.

Endpoints:
  GET  /news?tag=BTC&limit=N → captured headlines, newest first, each with source+ts.
  GET  /news/digest?tag=&limit=N → NEUTRAL source-cited roll-up (no commentary).
  POST /news/capture → run a capture sweep now (also the scheduled routine's work).

Routine: ``news-capture`` — fetch the feeds on an interval (fail-open, gated on the
master automation switch). No AI, pure RSS poll.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query

from core.base import BaseModule, Routine
from core.responses import ok

from . import service, store

logger = logging.getLogger("life-os.news.router")

router = APIRouter(tags=["news"])

NEWS_CAPTURE_ID = "news-capture"


@router.get("")
def list_news(
    tag: str | None = Query(None, description="exact asset/topic tag, e.g. BTC"),
    limit: int = Query(30, ge=1, le=200),
):
    """Captured headlines, newest first. Optional exact-tag filter (unknown tag → [])."""
    data = service.list_news(tag=tag, limit=limit)
    warning = None if data.count or not data.asOf else "no captured news yet"
    return ok(data=data.model_dump(), warning=warning)


@router.get("/digest")
def news_digest(
    tag: str | None = Query(None, description="restrict the digest to one tag"),
    limit: int = Query(10, ge=1, le=50),
):
    """A NEUTRAL, source-cited roll-up of captured news — only what was captured, each
    line citing its source. No commentary, no prediction, no good/bad-for-price."""
    data = service.digest(tag=tag, limit=limit)
    return ok(data=data.model_dump(), warning=data.note)


@router.post("/capture")
def capture_now():
    """Run a capture sweep now (fetch the feeds → store, dedup). Returns how many NEW
    items landed + any per-feed warnings. Fail-open: a flaky feed warns, never 500s."""
    new_count, warnings = service.capture()
    return ok(
        data={"new": new_count, "total": store.count_items()},
        warning="; ".join(warnings) if warnings else None,
    )


# --------------------------------------------------------------------------- #
# Routine — news-capture (rule-based RSS poll; no AI).                          #
# --------------------------------------------------------------------------- #
def _news_capture_work() -> tuple[str, str]:
    """Fetch the feeds + persist. Returns (status, detail) for the run log. Fail-open:
    a sweep where every feed failed is a 'warn', not an 'error' (cache still serves)."""
    new_count, warnings = service.capture()
    if warnings and new_count == 0:
        return "warn", f"news-capture: 0 new; warnings: {'; '.join(warnings)}"
    detail = f"news-capture: +{new_count} new"
    if warnings:
        detail += f" ({len(warnings)} feed warning(s))"
    return "ok", detail


def news_capture() -> None:
    """Scheduler entry point — runs the sweep via the unified run-record wrapper, gated
    on the master automation switch (no-ops when automation is off)."""
    from modules.automation import service as auto
    auto.run_scheduled(NEWS_CAPTURE_ID, _news_capture_work)


_NEWS_CAPTURE_ROUTINE = Routine(
    id=NEWS_CAPTURE_ID,
    func=news_capture,
    trigger="interval",
    trigger_args={"minutes": 30},
    name="news-capture (fetch public RSS feeds every 30m)",
    enabled=True,
)


MODULE = BaseModule(name="news", router=router, routines=[_NEWS_CAPTURE_ROUTINE])
