"""modules/journal/service.py — journal CRUD + stats over md_store (Sprint 9, SPEC §S7).

Mirrors the Notes pattern: `journal/<id>.md` (YAML front-matter + body), slug-id,
1 md_store commit/write, fail-open list parse. WRITE module → writes fail-CLOSED
(md_store errors propagate; a lost entry must NOT look successful). Self-contained
store (pnl user-entered, no price tie-back this sprint).

Logic (architect block, verbatim):
  - id = slug(asset)-<6hex>, else entry-<6hex>.
  - pnl parse: strip '%', leading sign+number → float; unparseable/None → open (excluded) + warn.
  - winRate = closed(pnl>0)/total closed; None if 0 closed. avgPnl = mean parsed closed; None if 0.
  - ladderDiscipline = count(tag=='ladder')/total; None if 0. LABEL "% ladder-tagged" (NOT plan-adherence).
  - thisMonth = current-month entries split total/buy/sell/ladder.
  - calibration = closed+confident entries grouped by band (50-59..90-100): predicted=midpoint,
    actual=%(outcome=="right") in band — the THESIS axis, NOT pnl (a lucky profit on a wrong
    thesis is a calibration miss); n=count; confidence<50/None dropped; omit n=0; [] if none.
  - outcome default open; on close (pnl set) default right if pnl>0 else wrong, user can override.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone

import yaml

from core.config import settings
from store import md_store

from .schema import CalibrationBand, JournalEntry, JournalInput, JournalStats, Outcome

logger = logging.getLogger("life-os.journal.service")

_SCALAR_FIELDS = (
    "id", "date", "action", "asset", "size", "px", "tag", "reason", "channel",
    "thesis", "negationCondition", "confidence", "pnl", "outcome", "createdAt", "updatedAt",
)
# Calibration bands (LOCKED): (lo_inclusive, hi_inclusive, label, midpoint). confidence
# < 50 or None is DROPPED (not a confidence claim to score). Last band is 90-100 inclusive.
_BANDS: list[tuple[int, int, str, float]] = [
    (50, 59, "50-59", 54.5),
    (60, 69, "60-69", 64.5),
    (70, 79, "70-79", 74.5),
    (80, 89, "80-89", 84.5),
    (90, 100, "90-100", 95.0),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(asset: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", asset.lower()).strip("-")
    return s or "entry"


def _new_id(asset: str) -> str:
    return f"{_slug(asset)}-{secrets.token_hex(3)}"


def _rel(entry_id: str) -> str:
    return f"journal/{entry_id}.md"


def parse_pnl(pnl: str | None) -> float | None:
    """Parse a free-form percent string → float. None/unparseable → None (open).

    '+5.5%'→5.5, '-4.1%'→-4.1, '18%'→18.0. NEVER raises (fail-soft).
    """
    if not isinstance(pnl, str):
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", pnl)
    if m is None:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Serialize / parse (Notes pattern)                                             #
# --------------------------------------------------------------------------- #
def _render(e: JournalEntry) -> str:
    """Entry → `---<front-matter>---<body>`. Front-matter is the machine source of
    truth (all scalar + prose fields, round-trips exactly); the body is a
    human-readable rendering of the prose fields (reason/thesis/lesson)."""
    fm = {
        "id": e.id, "date": e.date, "action": e.action, "asset": e.asset,
        "size": e.size, "px": e.px, "tag": e.tag, "channel": e.channel,
        "confidence": e.confidence, "pnl": e.pnl, "outcome": e.outcome,
        "negationCondition": e.negationCondition, "reason": e.reason,
        "thesis": e.thesis, "lesson": e.lesson,
        "createdAt": e.createdAt, "updatedAt": e.updatedAt,
    }
    body_parts = [f"## Reason\n{e.reason}"]
    if e.thesis:
        body_parts.append(f"## Thesis\n{e.thesis}")
    if e.lesson:
        body_parts.append(f"## Lesson\n{e.lesson}")
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n" + "\n\n".join(body_parts) + "\n"


def _parse(content: str) -> JournalEntry | None:
    """Parse a journal doc → JournalEntry, or None if malformed (caller skips+warns)."""
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return None
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_block = parts[0]
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    try:
        return JournalEntry(
            id=fm["id"], date=fm["date"], action=fm["action"], asset=fm["asset"],
            size=fm.get("size") or "", px=fm.get("px") or "", tag=fm.get("tag") or "",
            reason=fm["reason"], channel=fm.get("channel"), thesis=fm.get("thesis"),
            negationCondition=fm.get("negationCondition"), confidence=fm.get("confidence"),
            pnl=fm.get("pnl"), outcome=fm.get("outcome", "open"), lesson=fm.get("lesson"),
            createdAt=fm["createdAt"], updatedAt=fm["updatedAt"],
        )
    except Exception:
        return None


def _entry_ids() -> list[str]:
    d = settings.journal_dir
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


# --------------------------------------------------------------------------- #
# CRUD — writes fail-CLOSED (md_store errors propagate)                         #
# --------------------------------------------------------------------------- #
def get_entry(entry_id: str) -> JournalEntry | None:
    content = md_store.read(_rel(entry_id))
    if content is None:
        return None
    return _parse(content)


def _resolve_outcome(body: JournalInput) -> Outcome:
    """outcome: explicit if given; else 'open', or right/wrong by pnl sign when closing."""
    if body.outcome is not None:
        return body.outcome
    pct = parse_pnl(body.pnl)
    if pct is None:
        return "open"
    return "right" if pct > 0 else "wrong"


def create_entry(body: JournalInput) -> JournalEntry:
    """Create an entry (server-set id + timestamps). One git commit. Fail-CLOSED:
    if md_store.write_file raises, it propagates (no silent loss)."""
    now = _now_iso()
    entry = JournalEntry(
        id=_new_id(body.asset), date=body.date or now, action=body.action, asset=body.asset,
        size=body.size, px=body.px, tag=body.tag, reason=body.reason, channel=body.channel,
        thesis=body.thesis, negationCondition=body.negationCondition, confidence=body.confidence,
        pnl=body.pnl, outcome=_resolve_outcome(body), lesson=body.lesson,
        createdAt=now, updatedAt=now,
    )
    md_store.write_file(_rel(entry.id), _render(entry), f"create journal {entry.id}")
    return entry


def update_entry(entry_id: str, body: JournalInput) -> JournalEntry | None:
    """Update/close an entry (preserve createdAt+date, bump updatedAt). None if absent."""
    existing = get_entry(entry_id)
    if existing is None:
        return None
    entry = JournalEntry(
        id=entry_id, date=body.date or existing.date, action=body.action, asset=body.asset,
        size=body.size, px=body.px, tag=body.tag, reason=body.reason, channel=body.channel,
        thesis=body.thesis, negationCondition=body.negationCondition, confidence=body.confidence,
        pnl=body.pnl, outcome=_resolve_outcome(body), lesson=body.lesson,
        createdAt=existing.createdAt, updatedAt=_now_iso(),
    )
    md_store.write_file(_rel(entry_id), _render(entry), f"update journal {entry_id}")
    return entry


def delete_entry(entry_id: str) -> bool:
    if md_store.read(_rel(entry_id)) is None:
        return False
    md_store.delete_file(_rel(entry_id), f"delete journal {entry_id}")
    return True


# --------------------------------------------------------------------------- #
# List + stats                                                                  #
# --------------------------------------------------------------------------- #
def _all_entries() -> tuple[list[JournalEntry], list[str]]:
    entries: list[JournalEntry] = []
    warnings: list[str] = []
    for eid in _entry_ids():
        content = md_store.read(_rel(eid))
        if content is None:
            continue
        e = _parse(content)
        if e is None:
            warnings.append(f"journal entry {eid!r} malformed — skipped")
            continue
        entries.append(e)
    return entries, warnings


def _compute_stats(entries: list[JournalEntry]) -> dict:
    """All derived stats per the Logic block. pnl-parse fail-soft; closed = pnl parses."""
    total = len(entries)

    # closed = entries whose pnl parses to a number.
    closed_pcts = [(e, parse_pnl(e.pnl)) for e in entries]
    closed = [(e, p) for e, p in closed_pcts if p is not None]
    n_closed = len(closed)

    wins = sum(1 for _e, p in closed if p > 0)
    win_rate = round(wins / n_closed * 100, 1) if n_closed else None
    avg_pnl = round(sum(p for _e, p in closed) / n_closed, 2) if n_closed else None

    ladder_count = sum(1 for e in entries if e.tag == "ladder")
    ladder_disc = round(ladder_count / total * 100, 1) if total else None

    # thisMonth
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    tm_entries = [e for e in entries if isinstance(e.date, str) and e.date[:7] == month]
    this_month = {
        "total": len(tm_entries),
        "buy": sum(1 for e in tm_entries if e.action == "BUY"),
        "sell": sum(1 for e in tm_entries if e.action == "SELL"),
        "ladder": sum(1 for e in tm_entries if e.tag == "ladder"),
    }

    # calibration: closed entries WITH a confidence, grouped by band.
    calibration: list[CalibrationBand] = []
    # (confidence:int, thesis_right:bool) for closed entries that HAVE a confidence.
    # actual = %(outcome=="right") — the THESIS axis, NOT pnl sign. A lucky profit on
    # a wrong thesis (pnl>0, outcome="wrong") is a calibration MISS (SPEC §S7 "process
    # tách P&L"). winRate/avgPnl use pnl (money axis); calibration uses outcome (thesis).
    confident_closed: list[tuple[int, bool]] = [
        (e.confidence, e.outcome == "right") for e, _p in closed if isinstance(e.confidence, int)
    ]
    for lo, hi, label, midpoint in _BANDS:
        in_band = [won for conf, won in confident_closed if lo <= conf <= hi]
        if not in_band:
            continue
        band_wins = sum(1 for won in in_band if won)
        calibration.append(CalibrationBand(
            band=label, predicted=midpoint,
            actual=round(band_wins / len(in_band) * 100, 1), n=len(in_band),
        ))

    return {
        "count": total, "winRate": win_rate, "avgPnl": avg_pnl,
        "ladderDiscipline": ladder_disc, "thisMonth": this_month, "calibration": calibration,
    }


def list_entries(
    action: str | None = None,
    tag: str | None = None,
    channel: str | None = None,
    asset: str | None = None,
) -> tuple[JournalStats, list[str]]:
    """All entries matching filters (newest date first) + derived stats + warnings.

    Stats are computed over the FILTERED set. Fail-open: a malformed entry is
    skipped + warned, never crashes the list.
    """
    entries, warnings = _all_entries()
    if action:
        entries = [e for e in entries if e.action == action]
    if tag:
        entries = [e for e in entries if e.tag == tag]
    if channel:
        entries = [e for e in entries if e.channel == channel]
    if asset:
        entries = [e for e in entries if e.asset.lower() == asset.lower()]

    entries.sort(key=lambda e: e.date, reverse=True)
    stats = _compute_stats(entries)
    return JournalStats(entries=entries, **stats), warnings
