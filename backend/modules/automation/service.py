"""modules/automation/service.py — routine catalog + run-record wrapper (Sprint 10A).

The run-record wrapper (`record_routine_run`) times + logs every routine execution
to run_log, fail-soft per-routine (a raised routine → error row, never re-raised).
The catalog is the single source of routine metadata (id/trigger/label/desc/action
+ owning func), merged with run_log stats for GET /routines. Toggles persist in
md_store `automation/toggles.md` (survives restart — the 3B-class lesson).

NO AI — pure rules (CLAUDE.md hard rule). The 4 routine algorithms are decided
(architect Logic block); idle-hunter/pattern-check live in projects, journal-nudge
is event-driven (market-poll calls it), morning-pull lives here.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone

import yaml

from store import db, md_store

from .schema import RoutineInfo, RoutinesView, RunResultView

logger = logging.getLogger("life-os.automation.service")

TOGGLES_MD = "automation/toggles.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Run-record wrapper — every routine run → 1 run_log row, fail-soft             #
# --------------------------------------------------------------------------- #
def record_routine_run(routine_id: str, func) -> dict:
    """Run ``func`` and record exactly one run_log row. Returns the run summary.

    func() returns a (status, detail) tuple OR None (→ "ok", ""). On exception →
    "error" row with a traceback summary, and the exception is SWALLOWED (fail-soft:
    one routine erroring must not crash the scheduler or other routines). Returns
    {id, status, detail, startedAt, finishedAt}.
    """
    started = _now_iso()
    try:
        result = func()
        if isinstance(result, tuple) and len(result) == 2:
            status, detail = result
        else:
            status, detail = "ok", (str(result) if result else "")
        if status not in ("ok", "warn", "error"):
            status = "ok"
    except Exception as exc:  # fail-soft — record error, never re-raise
        status = "error"
        detail = f"{type(exc).__name__}: {exc}"
        logger.error("routine %r raised (recorded as error run): %s\n%s",
                     routine_id, exc, traceback.format_exc())
    finished = _now_iso()
    try:
        db.record_run(routine_id, status, started, finished_at=finished, detail=detail)
    except Exception as exc:  # run_log write itself failing must not propagate
        logger.error("failed to record run_log for %r: %s", routine_id, exc)
    return {"id": routine_id, "status": status, "detail": detail,
            "startedAt": started, "finishedAt": finished}


# --------------------------------------------------------------------------- #
# The routine algorithms (decided — NO AI, pure rules)                          #
# --------------------------------------------------------------------------- #
def idle_hunter() -> tuple[str, str]:
    """cron 22:00 — projects idle >7 days (lastDays>7, not abandoned) → warn."""
    from modules.projects import service as proj
    statuses, _ = proj.list_projects()  # excludes abandoned already
    idle = [s for s in statuses if s.lastDays is not None and s.lastDays > 7]
    if not idle:
        return "ok", "Không có dự án đứng >7 ngày."
    names = ", ".join(f"{s.name} ({s.lastDays}d)" for s in idle)
    return "warn", f"{len(idle)} dự án đứng >7 ngày: {names}"


def pattern_check() -> tuple[str, str]:
    """cron 09:00 — build-to-90 pattern: progress>=90 & users==0 & not abandoned → warn.

    Operates on progress+users (NOT health=dead — abandon-orthogonal). list_projects
    already excludes abandoned.
    """
    from modules.projects import service as proj
    statuses, _ = proj.list_projects()
    flagged = [s for s in statuses if (s.progress or 0) >= 90 and s.users == 0]
    if not flagged:
        return "ok", "Không có dự án build-to-90 (≥90% & 0 user)."
    names = ", ".join(f"{s.name} ({s.progress}%, {s.users} user)" for s in flagged)
    return "warn", f"{len(flagged)} dự án ≥90% nhưng 0 user: {names}"


def journal_nudge(alert: dict | None = None) -> tuple[str, str]:
    """event — a ladder-rung hit → nudge to journal the decision. No own timer.

    Event-driven: market-poll passes the fired ``alert`` dict ({symbol,...}) directly.
    Called with no arg (catalog / on-demand) it falls back to the most-recent
    market-poll alert in run_log. The arg makes the event simulable in a test.
    """
    if alert is not None and alert.get("symbol"):
        return "warn", f"Giá {alert['symbol']} chạm ngưỡng — ghi journal quyết định?"
    import json
    for row in db.recent_runs("market-poll", limit=20):
        detail = row["detail"]
        if not detail:
            continue
        try:
            payload = json.loads(detail)
        except (json.JSONDecodeError, TypeError):
            continue
        if payload.get("kind") == "alert":
            sym = payload.get("symbol", "?")
            return "warn", f"Giá {sym} chạm ngưỡng — ghi journal quyết định?"
    return "ok", "Chưa có cảnh báo giá mới để nhắc journal."


def morning_pull() -> tuple[str, str]:
    """cron 08:00 — read each module's data + ASSEMBLE+PERSIST the daily brief (S11-T2).

    Reads projects + market + finance for the pull summary, then generates + persists the
    daily brief to md_store (brief/<date>.md). Fail-soft per source (one source down → note
    it, still record the pull) AND fail-soft on the brief step (a brief/persist failure
    notes it but never aborts the pull — the run_log row is the routine's contract).
    """
    parts: list[str] = []
    try:
        from modules.projects import service as proj
        statuses, _ = proj.list_projects()
        parts.append(f"{len(statuses)} projects")
    except Exception as exc:
        parts.append(f"projects ERR ({type(exc).__name__})")
    try:
        from modules.market import service as mkt
        data, _ = mkt.get_market()
        parts.append(f"{len(data.get('quotes', []))} quotes")
    except Exception as exc:
        parts.append(f"market ERR ({type(exc).__name__})")
    try:
        from modules.finance import service as fin
        ov, _ = fin.get_overview()
        parts.append(f"finance ${ov.totalValue:,.0f}")
    except Exception as exc:
        parts.append(f"finance ERR ({type(exc).__name__})")
    # The pull's success is decided BEFORE the brief step — a brief-save failure must
    # not retroactively fail a pull that worked (policy: the pull is morning-pull's
    # primary contract; the brief snapshot is a best-effort add-on).
    pull_status = "warn" if any("ERR" in p for p in parts) else "ok"

    # S11-T2: assemble + save the daily brief snapshot (the morning brief the screen reads).
    # Fail-soft: a brief/save failure is NOTED (so it's visible) but does NOT downgrade a
    # successful pull to warn — the pull work already completed. (record_routine_run also
    # wraps the whole routine, so even an uncaught raise here would be a logged error row,
    # but we catch it to keep the pull's status + the other parts intact.)
    brief_status = "ok"
    try:
        from modules.brief import service as brief_svc
        b = brief_svc.generate_brief()
        brief_svc.save_brief(b)
        parts.append(f"brief {len(b.priorities)} ưu tiên")
    except Exception as exc:
        logger.error("morning-pull: brief save failed (pull still ok): %s", exc)
        parts.append(f"brief ERR ({type(exc).__name__})")
        brief_status = "warn"

    # If the PULL succeeded, the routine is ok even if the brief add-on warned; if the
    # pull itself warned, that stands.
    status = pull_status if pull_status == "warn" else brief_status
    return status, "Morning pull: " + ", ".join(parts)


# --------------------------------------------------------------------------- #
# Catalog — single source of routine metadata (merged w/ scheduler + run_log)   #
# --------------------------------------------------------------------------- #
# (id, name, trigger, triggerLabel, desc, action, default_enabled, func)
_CATALOG: list[dict] = [
    {"id": "market-poll", "name": "Market Poll", "trigger": "interval",
     "triggerLabel": "mỗi 5 phút", "desc": "Lấy giá + eval cảnh báo + ghi alert",
     "action": "fetch + persist + alert", "enabled": True, "func": None},
    {"id": "wiki-refresh", "name": "Wiki Refresh", "trigger": "interval",
     "triggerLabel": "mỗi 6 giờ", "desc": "Đọc lại git của mọi project + lastAuto",
     "action": "re-read git", "enabled": True, "func": None},
    {"id": "idle-hunter", "name": "Idle Hunter", "trigger": "cron",
     "triggerLabel": "22:00 mỗi tối", "desc": "Tìm dự án đứng >7 ngày",
     "action": "flag idle projects", "enabled": True, "func": idle_hunter},
    {"id": "pattern-check", "name": "Pattern Check", "trigger": "cron",
     "triggerLabel": "09:00 hằng ngày", "desc": "Phát hiện build-to-90 (≥90% & 0 user)",
     "action": "flag build-to-90", "enabled": True, "func": pattern_check},
    {"id": "journal-nudge", "name": "Journal Nudge", "trigger": "event",
     "triggerLabel": "khi giá chạm rung", "desc": "Nhắc ghi journal khi có cảnh báo giá",
     "action": "nudge journal", "enabled": True, "func": journal_nudge},
    {"id": "morning-pull", "name": "Morning Pull", "trigger": "cron",
     "triggerLabel": "08:00 hằng ngày", "desc": "Đọc dữ liệu các module buổi sáng",
     "action": "pull + summary", "enabled": True, "func": morning_pull},
]
_CATALOG_BY_ID = {c["id"]: c for c in _CATALOG}


# --------------------------------------------------------------------------- #
# Toggle persistence (md_store — survives restart)                              #
# --------------------------------------------------------------------------- #
def _load_toggles() -> dict[str, bool]:
    try:
        content = md_store.read(TOGGLES_MD)
    except Exception as exc:
        logger.warning("toggles.md read failed: %s", exc)
        return {}
    if not content:
        return {}
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return {}
    block = text[len("---"):].split("\n---", 1)[0]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): bool(v) for k, v in (data.get("toggles") or {}).items()}


def _write_toggles(toggles: dict[str, bool]) -> None:
    body = "---\n" + yaml.safe_dump({"toggles": toggles}, sort_keys=True).strip() + "\n---\n"
    md_store.write_file(TOGGLES_MD, body, "update routine toggles")


def _is_enabled(routine_id: str) -> bool:
    """Persisted toggle if set, else the catalog default."""
    toggles = _load_toggles()
    if routine_id in toggles:
        return toggles[routine_id]
    return bool(_CATALOG_BY_ID.get(routine_id, {}).get("enabled", True))


def set_enabled(routine_id: str, enabled: bool) -> RoutineInfo | None:
    """Toggle a routine on/off (persisted). None if unknown id (router → 404)."""
    if routine_id not in _CATALOG_BY_ID:
        return None
    toggles = _load_toggles()
    toggles[routine_id] = enabled
    _write_toggles(toggles)
    return _routine_info(_CATALOG_BY_ID[routine_id])


# --------------------------------------------------------------------------- #
# List + run                                                                    #
# --------------------------------------------------------------------------- #
def _routine_info(cat: dict) -> RoutineInfo:
    rows = db.recent_runs(cat["id"], limit=1000)
    last = rows[0] if rows else None
    return RoutineInfo(
        id=cat["id"], name=cat["name"], trigger=cat["trigger"],
        triggerLabel=cat["triggerLabel"], desc=cat["desc"], action=cat["action"],
        enabled=_is_enabled(cat["id"]),
        lastRun=last["started_at"] if last else None,
        lastResult=last["status"] if last else None,
        runs=len(rows),
    )


def list_routines() -> RoutinesView:
    """All routines + per-id run_log stats + roll-up. Never raises."""
    infos = [_routine_info(c) for c in _CATALOG]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # runsToday / lastRunAt across all routines.
    runs_today = 0
    last_run_at: str | None = None
    for c in _CATALOG:
        for row in db.recent_runs(c["id"], limit=1000):
            if isinstance(row["started_at"], str) and row["started_at"][:10] == today:
                runs_today += 1
            if last_run_at is None or (isinstance(row["started_at"], str) and row["started_at"] > last_run_at):
                last_run_at = row["started_at"]
    return RoutinesView(
        routines=infos, activeCount=sum(1 for i in infos if i.enabled),
        total=len(infos), runsToday=runs_today, lastRunAt=last_run_at,
    )


def run_routine(routine_id: str) -> RunResultView | None:
    """Run a routine on-demand NOW via the wrapper (records a run_log row). None if
    unknown id (router → 404). A failed run is still a 200 (logged error run)."""
    cat = _CATALOG_BY_ID.get(routine_id)
    if cat is None:
        return None
    func = cat["func"]
    if func is None:
        # market-poll/wiki-refresh own their funcs in their modules — import on demand.
        func = _external_func(routine_id)
    run = record_routine_run(routine_id, func)
    return RunResultView(**run)


def _external_func(routine_id: str):
    """Resolve the (status,detail)-returning work func for routines owned by other
    modules (market/projects) — the SAME work the scheduled timer runs, so on-demand
    and scheduled share one path."""
    if routine_id == "market-poll":
        from modules.market.router import _market_poll_work
        return _market_poll_work
    if routine_id == "wiki-refresh":
        from modules.projects.router import _wiki_refresh_work
        return _wiki_refresh_work
    return lambda: ("ok", "")
