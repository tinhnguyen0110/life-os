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
def automation_on() -> bool:
    """The master automation switch (settings.automationEnabled). SCHEDULED routine jobs
    check this + skip when off; the on-demand POST /routines/{id}/run path does NOT (a
    manual run is an explicit user action). Fail-open: settings unreadable → True (don't
    silently disable automation because a config read hiccuped)."""
    try:
        from modules.settings import service as cfg
        return cfg.get_config().automationEnabled
    except Exception as exc:
        logger.warning("automation_on check failed — defaulting ON: %s", exc)
        return True


def pattern_check_on() -> bool:
    """Per-routine enable for pattern-check (settings.patternCheckEnabled). Fail-open True."""
    try:
        from modules.settings import service as cfg
        return cfg.get_config().patternCheckEnabled
    except Exception as exc:
        logger.warning("pattern_check_on check failed — defaulting ON: %s", exc)
        return True


def run_scheduled(routine_id: str, func, *, gate: bool = True) -> dict | None:
    """Scheduled-path entry: gate on automationEnabled (master switch) then record the run.
    Returns None (skipped, no run_log row) when automation is OFF — the cron still fires but
    the routine no-ops. ``gate=False`` bypasses the master switch (unused; kept explicit).
    The MANUAL path (run_routine) does NOT call this — it always runs."""
    if gate and not automation_on():
        logger.info("automation OFF — skipping scheduled routine %r", routine_id)
        return None
    return record_routine_run(routine_id, func)


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
    """cron 22:00 — projects idle > idleThresholdDays (config; default 7), not abandoned → warn.

    Reads the threshold from settings at RUNTIME (S12 wiring) so a config PATCH takes
    effect on the next run without a code edit. Fail-open: settings unreadable → default 7.
    """
    from modules.projects import service as proj
    from modules.settings import service as cfg
    threshold = cfg.get_config().idleThresholdDays
    statuses, _ = proj.list_projects()  # excludes abandoned already
    idle = [s for s in statuses if s.lastDays is not None and s.lastDays > threshold]
    if not idle:
        return "ok", f"Không có dự án đứng >{threshold} ngày."
    names = ", ".join(f"{s.name} ({s.lastDays}d)" for s in idle)
    return "warn", f"{len(idle)} dự án đứng >{threshold} ngày: {names}"


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

    # D2: capture today's finance snapshot so the equity curve fills day-by-day
    # (take_snapshot was built but never scheduled — built-but-not-wired). SAME fail-soft
    # add-on discipline as the brief: a snapshot failure is NOTED (visible) but must NOT
    # downgrade a successful pull. take_snapshot upserts ONE row per UTC day, so calling
    # it daily (or twice) is idempotent — no dup. Forward-only (no backfill).
    snapshot_status = "ok"
    try:
        from modules.finance import service as fin
        snap = fin.take_snapshot()
        parts.append(f"snapshot ${snap['totalValue']:,.0f}")
    except Exception as exc:
        logger.error("morning-pull: snapshot failed (pull still ok): %s", exc)
        parts.append(f"snapshot ERR ({type(exc).__name__})")
        snapshot_status = "warn"

    # If the PULL succeeded, the routine is ok even if an ADD-ON (brief/snapshot) warned;
    # if the pull itself warned, that stands. The add-on tier is the worst of the add-ons.
    addon_status = "warn" if "warn" in (brief_status, snapshot_status) else "ok"
    status = pull_status if pull_status == "warn" else addon_status
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
    # FINANCE-ASSISTANT P1 (#52): daily macro+sentiment snapshot (F&G / BTC.d / yield-curve →
    # macro_history). func owned by the macro module → resolved on demand (_external_func) to
    # avoid an import-time cycle, same as market-poll/wiki-refresh.
    {"id": "macro-snapshot", "name": "Macro Snapshot", "trigger": "cron",
     "triggerLabel": "07:30 hằng ngày", "desc": "Snapshot F&G / BTC.d / yield-curve",
     "action": "snapshot sentiment", "enabled": True, "func": None},
    # FINANCE-AUDIT-S3 (#62): daily held-coin OHLC capture (→ RSI → s_asset). func owned by the
    # market module → resolved on demand (_external_func), same as market-poll.
    {"id": "held-history", "name": "Held History", "trigger": "cron",
     "triggerLabel": "00:10 hằng ngày", "desc": "Capture OHLC for held coins → RSI/s_asset",
     "action": "capture held OHLC", "enabled": True, "func": None},
    # JOURNAL-NUDGE (#14) Part 3 — routine attribution: these run_log routine_ids existed
    # (records were written) but were NOT in the catalog → the activity feed showed the raw id
    # instead of a friendly name. Register them so they attribute (func owned by their own module;
    # they run via their module's routine, NOT triggered from here → func None, like market-poll).
    {"id": "macro-poll", "name": "Macro Poll", "trigger": "interval",
     "triggerLabel": "định kỳ", "desc": "Refresh FRED macro indicators",
     "action": "fetch macro", "enabled": True, "func": None},
    {"id": "news-capture", "name": "News Capture", "trigger": "cron",
     "triggerLabel": "định kỳ", "desc": "Capture RSS headlines → grounded digest",
     "action": "capture news", "enabled": True, "func": None},
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
def _routine_info(cat: dict, rows: list | None = None) -> RoutineInfo:
    """Build a RoutineInfo. ``rows`` (this routine's run_log) may be passed in to
    avoid a redundant db.recent_runs call when the caller already has them."""
    if rows is None:
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
    """All routines + per-id run_log stats + roll-up. Never raises.

    Fetches each routine's run_log ONCE (was: twice — once in _routine_info and
    again in the roll-up loop) and reuses the rows for both the per-routine info and
    the runsToday / lastRunAt aggregates.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    infos: list[RoutineInfo] = []
    runs_today = 0
    last_run_at: str | None = None
    for c in _CATALOG:
        rows = db.recent_runs(c["id"], limit=1000)  # single fetch per routine
        infos.append(_routine_info(c, rows=rows))
        for row in rows:
            sa = row["started_at"]
            if isinstance(sa, str) and sa[:10] == today:
                runs_today += 1
            if isinstance(sa, str) and (last_run_at is None or sa > last_run_at):
                last_run_at = sa
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
    if routine_id == "macro-snapshot":
        from modules.macro.service import macro_sentiment_snapshot
        return macro_sentiment_snapshot
    if routine_id == "held-history":
        from modules.market.router import _held_history_work
        return _held_history_work
    return lambda: ("ok", "")
