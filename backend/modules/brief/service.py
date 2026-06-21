"""modules/brief/service.py — template brief generator + 5 priority rules (S11).

DETERMINISTIC RULES on real data — NO AI (CLAUDE.md + ARCH §11 hard constraint). Reads
the source modules via reader.pull() (fail-soft per source), runs 5 priority rules,
sorts the emitted priorities by severity (urgent>warn>info, rule-order tiebreak), and
returns a numbered Brief. honest-empty: no rule fires → priorities=[] + real summary.

Decided thresholds (architect Logic, §Assumptions):
  - market/ladder: a fired trigger (state=="hit") → urgent; next rung within ≤2%
    (state=="near" & |distancePct|≤2) → info; else none.
  - project: build-to-90 (progress≥90 & users==0 & not-abandoned) → urgent;
    idle (lastDays>7 & not-abandoned) → warn. (abandon-orthogonal, NOT health=dead.)
  - claude quota: pct≥90 → urgent, pct≥75 → warn, <75 → none; if stale, cap at warn.
  - finance drift: a channel with driftAlert (|drift|>5, finance owns the rule) → warn.
  - alerts: the top non-ladder market alert fired today → warn; else none (rule 1 owns
    ladder hits → no dup here).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from store import md_store

from . import reader
from .schema import (
    Brief,
    BriefSummary,
    ClusterRef,
    Priority,
    RecentNote,
    Severity,
    WikiContext,
)

logger = logging.getLogger("life-os.brief.service")

HISTORY_DIR = "brief"  # md_store brief/<date>.md (T2 owns the write side)

# Severity rank for the display sort (higher = shown first).
_SEV_RANK = {"urgent": 3, "warn": 2, "info": 1}
# Rule order = generation order = stable tiebreak within a severity (architect Logic).
_RULE_ORDER = {"market": 1, "projects": 2, "claude": 3, "finance": 4, "alerts": 5,
               "reminders": 6, "tracing": 7}  # DAILY-TRACING-P4 (#65)

LADDER_NEAR_PCT = 2.0   # next rung within ≤2% → info ("sắp chạm rung")
CLAUDE_URGENT_PCT = 90.0
CLAUDE_WARN_PCT = 75.0
IDLE_DAYS = 7
BUILD90_PROGRESS = 90
STREAK_AT_RISK_MIN = 3  # DAILY-TRACING-P4 (#65): a streak ≥3 days is hard-won → at-risk if undone today
PRIORITY_CAP = 7  # DAILY-TRACING-P4 (#65): +tracing rule → 7 rules, cap 7 so none is silently dropped (#30 was 6)
WIKI_RECENT_CAP = 7      # WIKI-CONTEXT (#36): newest create|edit notes surfaced into the brief
WIKI_CLUSTER_CAP = 5     # WIKI-CONTEXT (#36): top notable clusters (importance-ranked by the reader)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --------------------------------------------------------------------------- #
# The 5 priority rules — each reads its source + emits 0-1 Priority             #
# (n is a placeholder 0 here; the display rank is assigned AFTER the sort)       #
# --------------------------------------------------------------------------- #
def _market_priority(market: dict | None) -> Priority | None:
    """Rule 1 — a fired ladder rung (urgent) or a next rung within ≤2% (info)."""
    if not market:
        return None
    triggers = market.get("triggers") or []
    # urgent: any fired trigger (price hit the threshold/rung)
    hits = [t for t in triggers if t.get("state") == "hit"]
    if hits:
        t = hits[0]
        return Priority(n=0, source="market", severity="urgent",
                        text=f"{t['symbol']} chạm ngưỡng ${t['price']:,.0f} ({t['op']} ${t['threshold']:,.0f}) — cân nhắc DCA.")
    # info: a next rung within ≤2% (near, tightened from market's 5% to the ladder 2%)
    near = [t for t in triggers
            if t.get("state") == "near" and abs(t.get("distancePct", 99)) <= LADDER_NEAR_PCT]
    if near:
        t = min(near, key=lambda x: abs(x.get("distancePct", 99)))
        return Priority(n=0, source="market", severity="info",
                        text=f"{t['symbol']} sắp chạm rung (${t['price']:,.0f}, cách {abs(t['distancePct']):.1f}%).")
    return None


def _project_priority(projects: list | None) -> Priority | None:
    """Rule 2 — build-to-90 (urgent) takes precedence over idle (warn). abandon-orthogonal:
    progress+users, NOT health=dead. list_projects already excludes abandoned."""
    if not projects:
        return None
    build90 = [p for p in projects if (p.progress or 0) >= BUILD90_PROGRESS and p.users == 0]
    if build90:
        p = build90[0]
        return Priority(n=0, source="projects", severity="urgent",
                        text=f"{p.name} {p.progress}% / 0 user — khớp build-to-90: quyết bỏ hay đẩy ra mắt?")
    idle = [p for p in projects if p.lastDays is not None and p.lastDays > IDLE_DAYS]
    if idle:
        p = max(idle, key=lambda x: x.lastDays or 0)
        return Priority(n=0, source="projects", severity="warn",
                        text=f"{p.name} đứng {p.lastDays} ngày — xem lại hay bỏ?")
    return None


def _reminders_priority(reminders: list | None) -> Priority | None:
    """REMINDERS-4 (#30) — any OVERDUE un-done reminder → URGENT; else any DUE-TODAY un-done →
    WARN; none → nothing (0-1 priority, like the sibling rules). Uses the reader's ``overdue``
    field (#29 = un-done AND past-due); due-today = un-done, not overdue, due ≤ end-of-today UTC."""
    if not reminders:
        return None
    overdue = [r for r in reminders if getattr(r, "overdue", False)]
    if overdue:
        return Priority(n=0, source="reminders", severity="urgent",
                        text=f"{len(overdue)} nhắc nhở quá hạn — xử lý hoặc đánh dấu xong.")
    today_end = (datetime.now(timezone.utc)
                 .replace(hour=23, minute=59, second=59, microsecond=999999).isoformat())
    due_today = [r for r in reminders
                 if r.done_at is None and not getattr(r, "overdue", False) and r.due_at <= today_end]
    if due_today:
        return Priority(n=0, source="reminders", severity="warn",
                        text=f"{len(due_today)} nhắc nhở đến hạn hôm nay.")
    return None


def _tracing_priority(tracing: object | None) -> Priority | None:
    """DAILY-TRACING-P4 (#65) — a hard-won streak about to break → WARN (today-actionable nudge,
    NOT urgent: nothing is past-due, the day isn't over). At-risk = an activity whose streak ≥
    STREAK_AT_RISK_MIN AND today is NOT yet done. None if no source / no activities / none at-risk
    (honest, no crash). READS the already-derived streak + today.done (no new derivation)."""
    if tracing is None:
        return None
    activities = getattr(tracing, "activities", None)
    if not activities:
        return None
    at_risk = [a for a in activities
               if a.streak >= STREAK_AT_RISK_MIN and a.today.done is False]
    if not at_risk:
        return None
    top = max(a.streak for a in at_risk)
    return Priority(n=0, source="tracing", severity="warn",
                    text=(f"{len(at_risk)} chuỗi sắp đứt (dài nhất {top} ngày) — "
                          f"hoàn thành hôm nay để giữ streak."))


def _quota_pct(claude) -> float | None:
    """G6 — the QUOTA % to surface in the brief = ``pct5h``, the LIVE 5h rate-limit
    used % (a real 0-100 from the quota snapshot, confirmed correct ~71%).

    ROOT-CAUSE fix (NOT a clamp): we consume the CORRECT field the data already has,
    we do NOT read + clamp the raw ``pct`` (= round(used/cap*100), where cap is a
    too-small token-window guess → reads absurd like 3316%). Clamping would HIDE the
    symptom and leave the raw field for the next consumer to re-hit; wiring to pct5h
    fixes it at the source (same lesson as the M4 sidebar-badge field bug).

    R2-G2 — fallback chain: ``pct5h`` (5h window, preferred) → ``weekly`` (the 7-day
    quota %, still a real 0-100 from the snapshot) → None. So when the 5h snapshot is
    absent but the weekly one is present, the brief still surfaces a SANE quota %
    instead of going dark. Never the broken raw ``pct``. None only when BOTH window
    %s are absent (claude down / no snapshot) → the existing None-handling kicks in.

    NOTE: the dispatch said ``pctWeek`` — but on the ClaudeUsage model the brief
    consumes, the 7-day % field is named ``weekly`` (``pctWeek`` is only the internal
    quota-snapshot DICT key in claude_usage/service.py, mapped to ``weekly=`` on the
    model). Reading ``pctWeek`` off the model would be a no-op (always None). So we
    read the REAL field ``weekly`` (the G7/M4 phantom-field lesson — wire to the field
    that actually exists)."""
    pct5h = getattr(claude, "pct5h", None)
    if pct5h is not None:
        return float(pct5h)
    weekly = getattr(claude, "weekly", None)
    if weekly is not None:
        return float(weekly)
    return None


def _claude_priority(claude) -> Priority | None:
    """Rule 3 — quota bands on the meaningful quota % (pct5h, else clamped pct — G6).
    Stale claude cache caps severity at warn (don't cry urgent on old data) + notes asOf."""
    if claude is None:
        return None
    pct = _quota_pct(claude)
    if pct is None:
        return None
    stale = bool(getattr(claude, "stale", False))
    asof = getattr(claude, "asOf", None)
    stale_note = f" (dữ liệu {asof})" if stale else ""
    if pct >= CLAUDE_URGENT_PCT:
        sev: Severity = "warn" if stale else "urgent"  # cap at warn on stale
        return Priority(n=0, source="claude", severity=sev,
                        text=f"Quota Claude đốt {pct:.0f}% — {'sắp hết' if not stale else 'cao'}, ưu tiên việc quan trọng{stale_note}.")
    if pct >= CLAUDE_WARN_PCT:
        return Priority(n=0, source="claude", severity="warn",
                        text=f"Quota Claude {pct:.0f}% — cao, để ý phần còn lại{stale_note}.")
    return None


def _finance_priority(finance) -> Priority | None:
    """Rule 4 — a channel with driftAlert (|drift|>5, finance's rule). warn."""
    if finance is None:
        return None
    allocs = getattr(finance, "allocations", None) or []
    drifted = [a for a in allocs if getattr(a, "driftAlert", False)]
    if not drifted:
        return None
    a = max(drifted, key=lambda x: abs(getattr(x, "drift", 0)))
    return Priority(n=0, source="finance", severity="warn",
                    text=f"Phân bổ lệch {a.channel} {a.drift:+.1f}% (mục tiêu {a.target:.0f}%) — rebalance?")


def _alerts_priority(market: dict | None) -> Priority | None:
    """Rule 5 — the top NON-LADDER market alert fired today (warn). Ladder hits are rule
    1's job → not duplicated here. This build: market alertHistory is ladder-rule alerts,
    so once rule 1 covers the hits, rule 5 emits nothing unless a distinct alert exists.
    Surfaces the most-recent alert today that is NOT already the rule-1 hit."""
    if not market:
        return None
    history = market.get("alertHistory") or []
    today = _today()
    todays = [e for e in history if isinstance(e.get("ts"), str) and e["ts"][:10] == today]
    if not todays:
        return None
    # rule 1 already surfaces a CURRENTLY-fired trigger; rule 5 surfaces a today alert that
    # isn't currently a live hit (avoids the dup). If a today alert's symbol is the live
    # hit, skip it (rule 1 owns it).
    live_hit_syms = {t.get("symbol") for t in (market.get("triggers") or []) if t.get("state") == "hit"}
    extra = [e for e in todays if e.get("symbol") not in live_hit_syms]
    if not extra:
        return None
    e = extra[0]  # alertHistory is newest-first
    return Priority(n=0, source="alerts", severity="warn",
                    text=f"Cảnh báo {e['symbol']} hôm nay (${e['price']:,.0f}) — đã ghi journal?")


# --------------------------------------------------------------------------- #
# Generate                                                                      #
# --------------------------------------------------------------------------- #
def _build_summary(src: reader.Sources) -> BriefSummary:
    net_worth = getattr(src.finance, "totalValue", None) if src.finance is not None else None
    # G6: surface the meaningful quota % (pct5h, else clamped pct) — never the absurd
    # used/cap ratio that can read >100%.
    claude_pct = _quota_pct(src.claude) if src.claude is not None else None
    projects_active = 0
    if src.projects:
        projects_active = sum(1 for p in src.projects if p.health in ("act", "slow"))
    alerts_today = 0
    if src.market:
        today = _today()
        alerts_today = sum(1 for e in (src.market.get("alertHistory") or [])
                           if isinstance(e.get("ts"), str) and e["ts"][:10] == today)
    return BriefSummary(netWorth=net_worth, projectsActive=projects_active,
                        claudePct=claude_pct, alertsToday=alerts_today)


def _compute_as_of(src: reader.Sources, generated_at: str) -> tuple[str, bool]:
    """asOf = oldest source freshness (claude carries a real asOf); stale = any stale."""
    as_of = generated_at
    stale = False
    if src.claude is not None:
        c_asof = getattr(src.claude, "asOf", None)
        if isinstance(c_asof, str) and c_asof and c_asof < as_of:
            as_of = c_asof
        if getattr(src.claude, "stale", False):
            stale = True
    return as_of, stale


def _build_wiki_context(src: reader.Sources, generated_at: str) -> WikiContext:
    """WIKI-CONTEXT (#36): the deterministic wiki-graph block — recent note activity
    (newest create|edit) + notable clusters. Pulled from src.wiki (reader.recent_activity
    + detect_clusters); NO model, NO recompute.

    honest-mirror: src.wiki is None ONLY when the wiki read raised in reader.pull (a warning
    was already appended to src.warnings) → return an empty-lists context tagged with a
    warning (the block is present + honest-blind, never omitted, never a fabricated note).
    Empty activity/clusters → empty lists (truthful, not None-the-section)."""
    if src.wiki is None:
        return WikiContext(recentNotes=[], clusters=[], asOf=generated_at, source="wiki",
                           warnings=["wiki source unavailable"])

    recent_notes: list[RecentNote] = []
    for op in src.wiki.get("recentOps", []):
        # recent_activity rows: {ts, op, actor, noteId, noteTitle, detail}. Only create|edit
        # have a live note to surface (delete/merge removed it). Skip a None noteId defensively.
        kind = op.get("op")
        if kind not in ("create", "edit") or op.get("noteId") is None:
            continue
        recent_notes.append(RecentNote(
            noteId=op["noteId"], title=op.get("noteTitle") or "",
            kind=kind, ts=op.get("ts") or generated_at))
        if len(recent_notes) >= WIKI_RECENT_CAP:
            break

    clusters: list[ClusterRef] = []
    for c in src.wiki.get("clusters", [])[:WIKI_CLUSTER_CAP]:
        # mirror the reader's detect_clusters shape: label = suggestedTitle, noteCount = size.
        clusters.append(ClusterRef(
            label=c.get("suggestedTitle") or "(untitled cluster)",
            noteCount=int(c.get("size") or 0)))

    return WikiContext(recentNotes=recent_notes, clusters=clusters,
                       asOf=generated_at, source="wiki", warnings=[])


def generate_brief() -> Brief:
    """Assemble the brief from live data. Fail-soft per source (a source down → warning,
    its rules skipped, brief still produced). honest-empty: no rule fires → priorities=[]."""
    generated_at = _now_iso()
    src = reader.pull()

    # Run the rules (each fail-soft — a rule raising must not abort the brief). Each
    # thunk wraps one rule so a single failure is contained + the brief still assembles.
    rules = [
        ("market", lambda: _market_priority(src.market)),
        ("projects", lambda: _project_priority(src.projects)),
        ("claude", lambda: _claude_priority(src.claude)),
        ("finance", lambda: _finance_priority(src.finance)),
        ("alerts", lambda: _alerts_priority(src.market)),
        ("reminders", lambda: _reminders_priority(src.reminders)),  # REMINDERS-4 (#30)
        ("tracing", lambda: _tracing_priority(src.tracing)),        # DAILY-TRACING-P4 (#65)
    ]
    candidates: list[Priority] = []
    for name, thunk in rules:
        try:
            p = thunk()
            if p is not None:
                candidates.append(p)
        except Exception as exc:  # one rule failing never breaks the brief
            logger.error("brief rule %s failed: %s", name, exc)
            src.warnings.append(f"quy tắc {name} lỗi")

    # DISPLAY sort: severity DESC, rule-order tiebreak. Assign n AFTER the sort.
    candidates.sort(key=lambda p: (-_SEV_RANK[p.severity], _RULE_ORDER[p.source]))
    priorities = [p.model_copy(update={"n": i + 1}) for i, p in enumerate(candidates[:PRIORITY_CAP])]

    as_of, stale = _compute_as_of(src, generated_at)
    summary = _build_summary(src)

    # All sources down → honest minimal note (still 200).
    if src.projects is None and src.finance is None and src.market is None and src.claude is None:
        src.warnings.append("không đủ dữ liệu — mọi nguồn lỗi")

    # WIKI-CONTEXT (#36): ADDITIVE — recent wiki notes + clusters, deterministic. Present
    # whenever the brief assembles (honest-empty/blind, never faked); the existing priorities/
    # summary/stale are UNCHANGED (backward-compat).
    wiki_context = _build_wiki_context(src, generated_at)

    return Brief(
        generatedAt=generated_at, asOf=as_of, source="template",
        summary=summary, priorities=priorities, stale=stale,
        warnings=src.warnings, wikiContext=wiki_context,
    )


# --------------------------------------------------------------------------- #
# Persistence (S11-T2) — write today's brief to md_store brief/<date>.md         #
# --------------------------------------------------------------------------- #
def save_brief(brief: Brief | None = None) -> str:
    """Generate (if not given) + persist the brief to ``brief/<YYYY-MM-DD>.md`` as YAML
    front-matter (one md_store commit). Re-persisting the same day OVERWRITES that day's
    file (a brief is a daily snapshot — the latest assembly wins; md_store keeps git
    history). Returns the file's md_store path. Raises only on a store write failure
    (fail-closed write — a persistence failure must be visible, not swallowed)."""
    import yaml

    if brief is None:
        brief = generate_brief()
    date = brief.generatedAt[:10] if brief.generatedAt else _today()
    rel = f"{HISTORY_DIR}/{date}.md"
    body = "---\n" + yaml.safe_dump(brief.model_dump(), sort_keys=True, allow_unicode=True).strip() + "\n---\n"
    md_store.write_file(rel, body, f"brief {date}")
    return rel


# --------------------------------------------------------------------------- #
# History — read persisted briefs or []                                         #
# --------------------------------------------------------------------------- #
def get_history(limit: int = 30) -> list[Brief]:
    """Past persisted briefs (brief/<date>.md), newest-first. [] if none persisted yet.
    Fail-open: an unreadable/old file is skipped, never raises. (T2 owns the write side;
    until then this returns [] honestly — the dispatch's 'History empty → [], 200'.)"""
    import yaml

    from core.config import settings

    briefs: list[Brief] = []
    hist_dir = settings.data_dir / HISTORY_DIR
    try:
        if not hist_dir.is_dir():
            return []
        files = sorted((p for p in hist_dir.iterdir() if p.suffix == ".md"),
                       key=lambda p: p.name, reverse=True)[:limit]
    except Exception as exc:
        logger.warning("brief history list failed: %s", exc)
        return []
    for path in files:
        try:
            content = md_store.read(f"{HISTORY_DIR}/{path.name}")
            if not content:
                continue
            text = content.lstrip("﻿")
            if not text.startswith("---"):
                continue
            block = text[len("---"):].split("\n---", 1)[0]
            data = yaml.safe_load(block)
            if isinstance(data, dict):
                briefs.append(Brief(**data))
        except Exception as exc:  # one bad file never breaks the list
            logger.warning("brief history %s skipped: %s", path.name, exc)
    # NB1+NB2: read-time sanitize of historical data — old briefs persisted bad numbers
    # before the source fixes (NG1 clamped claudePct; a finance hiccup could write a
    # netWorth spike). Clean them at READ time so the history view/agent isn't misled,
    # WITHOUT mutating the on-disk .md (the file is the historical record; we only
    # sanitize the in-memory view).
    return _sanitize_brief_history(briefs)


# --------------------------------------------------------------------------- #
# NB1+NB2 — read-time sanitize. Purely in-memory: returns sanitized COPIES of    #
# the Brief objects, never touches disk. Two independent guards:                 #
#   NB1 claudePct: a persisted pct > 100 is stale overflow (pre-NG1) — clamp to   #
#        None (honest no-data, NOT a fabricated 0 / a misleading 4500%).          #
#   NB2 netWorth: a value > 3× the median (over the non-None rows, needs ≥4 rows  #
#        to be meaningful) is a finance-hiccup outlier — null it (honest no-data). #
# --------------------------------------------------------------------------- #
_NETWORTH_OUTLIER_FACTOR = 3.0
_NETWORTH_MIN_ROWS = 4


def _sanitize_brief_history(briefs: list[Brief]) -> list[Brief]:
    """Read-time clean of historical brief numbers (NB1+NB2). Returns sanitized COPIES;
    does NOT mutate the input objects or the on-disk files (read-only).

    - claudePct > 100 → None (stale overflow persisted before the NG1 source fix).
    - netWorth > 3× median → None, but ONLY with ≥4 non-None netWorth rows (too few to
      trust a median below that — skip the guard, leave values as-is). The median is over
      the present (non-None) netWorth values; if <4 present, the netWorth guard is skipped
      entirely (claudePct clamp still applies)."""
    import statistics

    net_values = [
        b.summary.netWorth for b in briefs
        if b.summary.netWorth is not None
    ]
    net_threshold: float | None = None
    if len(net_values) >= _NETWORTH_MIN_ROWS:
        median = statistics.median(net_values)
        # A non-positive median can't define a multiplicative outlier band — skip then.
        if median > 0:
            net_threshold = _NETWORTH_OUTLIER_FACTOR * median

    cleaned: list[Brief] = []
    for b in briefs:
        new_net = b.summary.netWorth
        new_pct = b.summary.claudePct
        changed = False
        if (net_threshold is not None and new_net is not None
                and new_net > net_threshold):
            new_net, changed = None, True
        if new_pct is not None and new_pct > 100:
            new_pct, changed = None, True
        if not changed:
            cleaned.append(b)  # unchanged — no copy needed
        else:
            new_summary = b.summary.model_copy(
                update={"netWorth": new_net, "claudePct": new_pct}
            )
            cleaned.append(b.model_copy(update={"summary": new_summary}))
    return cleaned
