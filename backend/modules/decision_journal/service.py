"""modules/decision_journal/service.py — decision CRUD + calibration stats (W7 A2).

Mirrors the trade-journal pattern: ``decision_journal/<id>.md`` (YAML front-matter +
body), slug-id, 1 md_store commit/write, fail-open list parse, fail-CLOSED write.

Logic (architect block, verbatim — team-lead-tightened):
  - id = slug(decision)-<6hex>.
  - resolved set = status=="resolved" AND outcome in (right,wrong). Open excluded from ALL stats.
  - Brier = mean((p-o)^2) over resolved; p = predicted if not None else confidence/100;
    o = 1.0 if outcome=="right" else 0.0. 0 resolved → None. (locked fixture → 0.325.)
  - Calibration bands = journal's _BANDS (50-59..90-100; confidence<50/None dropped). Per band:
    predicted=midpoint, actual=%(outcome=="right") in band, n=count; omit empty. THESIS/outcome
    axis — NOT confidence axis (a high-confidence-WRONG band scores actual LOW, not ~95).
  - Bias = group resolved by domain; for domains with n>=4, wrongRate=count(wrong)/n; flag if >0.60.
    min-n gate → no false-positive on sparse data (a 3-all-wrong domain is NOT flagged).
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timezone

import yaml

from core.config import settings
from store import md_store

from .schema import (
    BiasFlag,
    CalibrationBand,
    DecisionEntry,
    DecisionInput,
    DecisionStats,
    DecisionUpdate,
)

logger = logging.getLogger("life-os.decision_journal.service")

# Reuse the trade-journal calibration bands VERBATIM (the prior-art thesis-axis
# approach). confidence < 50 or None is DROPPED (not a confidence claim to score).
_BANDS: list[tuple[int, int, str, float]] = [
    (50, 59, "50-59", 54.5),
    (60, 69, "60-69", 64.5),
    (70, 79, "70-79", 74.5),
    (80, 89, "80-89", 84.5),
    (90, 100, "90-100", 95.0),
]

# Bias-cluster gates (LOCKED, team-lead): flag a domain when resolved-wrong-rate
# exceeds this over at least the min sample (no sparse-data false positives).
_BIAS_MIN_N = 4
_BIAS_WRONG_RATE = 0.60


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "decision"


def _new_id(decision: str) -> str:
    return f"{_slug(decision)}-{secrets.token_hex(3)}"


def _rel(entry_id: str) -> str:
    return f"decision_journal/{entry_id}.md"


# --------------------------------------------------------------------------- #
# Serialize / parse (Notes/journal pattern)                                     #
# --------------------------------------------------------------------------- #
def _render(e: DecisionEntry) -> str:
    """Entry → ``---<front-matter>---<body>``. Front-matter = machine source of
    truth (round-trips exactly); body = human-readable prose."""
    fm = {
        "id": e.id, "decision": e.decision, "thesis": e.thesis,
        "falsificationCondition": e.falsificationCondition, "confidence": e.confidence,
        "predicted": e.predicted, "date": e.date, "domain": e.domain,
        "status": e.status, "outcome": e.outcome, "lesson": e.lesson,
        "createdAt": e.createdAt, "updatedAt": e.updatedAt,
    }
    body_parts = [f"## Decision\n{e.decision}"]
    if e.thesis:
        body_parts.append(f"## Thesis\n{e.thesis}")
    if e.falsificationCondition:
        body_parts.append(f"## Falsification\n{e.falsificationCondition}")
    if e.lesson:
        body_parts.append(f"## Lesson\n{e.lesson}")
    block = yaml.safe_dump(fm, sort_keys=True, allow_unicode=True).strip()
    return f"---\n{block}\n---\n" + "\n\n".join(body_parts) + "\n"


def _parse(content: str) -> DecisionEntry | None:
    """Parse a decision doc → DecisionEntry, or None if malformed (caller skips+warns)."""
    text = content.lstrip("﻿")
    if not text.startswith("---"):
        return None
    parts = text[len("---"):].split("\n---", 1)
    if len(parts) < 2:
        return None
    try:
        fm = yaml.safe_load(parts[0])
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    try:
        return DecisionEntry(
            id=fm["id"], decision=fm["decision"], thesis=fm.get("thesis"),
            falsificationCondition=fm.get("falsificationCondition"),
            confidence=fm["confidence"], predicted=fm.get("predicted"),
            date=fm["date"], domain=fm["domain"], status=fm.get("status", "open"),
            outcome=fm.get("outcome"), lesson=fm.get("lesson"),
            createdAt=fm["createdAt"], updatedAt=fm["updatedAt"],
        )
    except Exception:
        return None


def _entry_ids() -> list[str]:
    d = settings.decision_journal_dir
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.md"))


# --------------------------------------------------------------------------- #
# CRUD — writes fail-CLOSED (md_store errors propagate)                         #
# --------------------------------------------------------------------------- #
def get_entry(entry_id: str) -> DecisionEntry | None:
    content = md_store.read(_rel(entry_id))
    if content is None:
        return None
    return _parse(content)


def create_entry(body: DecisionInput) -> DecisionEntry:
    """Create a decision (server id + timestamps). One git commit. Fail-CLOSED."""
    now = _now_iso()
    entry = DecisionEntry(
        id=_new_id(body.decision), decision=body.decision, thesis=body.thesis,
        falsificationCondition=body.falsificationCondition, confidence=body.confidence,
        predicted=body.predicted, date=body.date or now, domain=body.domain,
        status=body.status or "open", outcome=body.outcome, lesson=body.lesson,
        createdAt=now, updatedAt=now,
    )
    md_store.write_file(_rel(entry.id), _render(entry), f"create decision {entry.id}")
    return entry


def update_entry(entry_id: str, body: DecisionUpdate) -> DecisionEntry | None:
    """PARTIAL update / resolve (PATCH-semantics): a field left None KEEPS the
    existing value; a present field overrides (W7-A2-fix). So the natural resolve
    ``PUT {status:"resolved", outcome:"right"}`` works without resending the core
    fields. createdAt is preserved; updatedAt bumped. None if absent.

    Note: every DecisionUpdate field is None-means-unchanged. ``outcome``/``lesson``
    are themselves nullable, so a partial PUT can SET but not CLEAR them — clearing
    isn't a workflow we need (a resolve only ever sets outcome). The dominant path
    (resolve) supplies status+outcome; everything else inherits from ``existing``."""
    existing = get_entry(entry_id)
    if existing is None:
        return None

    def _merge(field: str):
        v = getattr(body, field)
        return v if v is not None else getattr(existing, field)

    entry = DecisionEntry(
        id=entry_id,
        decision=_merge("decision"),
        thesis=_merge("thesis"),
        falsificationCondition=_merge("falsificationCondition"),
        confidence=_merge("confidence"),
        predicted=_merge("predicted"),
        date=_merge("date"),
        domain=_merge("domain"),
        status=_merge("status"),
        outcome=_merge("outcome"),
        lesson=_merge("lesson"),
        createdAt=existing.createdAt,
        updatedAt=_now_iso(),
    )
    md_store.write_file(_rel(entry_id), _render(entry), f"update decision {entry_id}")
    return entry


def delete_entry(entry_id: str) -> bool:
    if md_store.read(_rel(entry_id)) is None:
        return False
    md_store.delete_file(_rel(entry_id), f"delete decision {entry_id}")
    return True


# --------------------------------------------------------------------------- #
# List + stats                                                                  #
# --------------------------------------------------------------------------- #
def _all_entries() -> tuple[list[DecisionEntry], list[str]]:
    entries: list[DecisionEntry] = []
    warnings: list[str] = []
    for eid in _entry_ids():
        content = md_store.read(_rel(eid))
        if content is None:
            continue
        e = _parse(content)
        if e is None:
            warnings.append(f"decision entry {eid!r} malformed — skipped")
            continue
        entries.append(e)
    return entries, warnings


def _is_resolved(e: DecisionEntry) -> bool:
    """The resolved set: status=='resolved' AND a real outcome. Open/unresolved are
    excluded from ALL stats (Brier/calibration/bias)."""
    return e.status == "resolved" and e.outcome in ("right", "wrong")


def compute_stats(entries: list[DecisionEntry]) -> dict:
    """All derived stats per the Logic block. PURE (testable without HTTP)."""
    total = len(entries)
    resolved = [e for e in entries if _is_resolved(e)]
    n_resolved = len(resolved)

    # Brier = mean((p-o)^2); p = predicted if set else confidence/100; o = 1 right/0 wrong.
    brier: float | None = None
    if resolved:
        sq = 0.0
        for e in resolved:
            p = e.predicted if e.predicted is not None else e.confidence / 100.0
            o = 1.0 if e.outcome == "right" else 0.0
            sq += (p - o) ** 2
        brier = round(sq / n_resolved, 4)

    # Calibration bands — resolved entries grouped by confidence band; actual = %right
    # (the THESIS/outcome axis, NOT confidence). confidence<50/None dropped.
    calibration: list[CalibrationBand] = []
    confident = [(e.confidence, e.outcome == "right") for e in resolved
                 if isinstance(e.confidence, int)]
    for lo, hi, label, midpoint in _BANDS:
        in_band = [won for conf, won in confident if lo <= conf <= hi]
        if not in_band:
            continue
        band_right = sum(1 for won in in_band if won)
        calibration.append(CalibrationBand(
            band=label, predicted=midpoint,
            actual=round(band_right / len(in_band) * 100, 1), n=len(in_band),
        ))

    # Bias — group resolved by domain; flag domains with n>=min AND wrongRate>threshold.
    by_domain: dict[str, list[DecisionEntry]] = {}
    for e in resolved:
        by_domain.setdefault(e.domain, []).append(e)
    bias_flags: list[BiasFlag] = []
    for domain in sorted(by_domain):
        group = by_domain[domain]
        n = len(group)
        if n < _BIAS_MIN_N:  # min-sample gate — no sparse-data false positives
            continue
        wrong = sum(1 for e in group if e.outcome == "wrong")
        wrong_rate = wrong / n
        if wrong_rate > _BIAS_WRONG_RATE:
            bias_flags.append(BiasFlag(domain=domain, wrongRate=round(wrong_rate, 3), n=n))

    return {
        "count": total, "resolvedCount": n_resolved, "brier": brier,
        "calibration": calibration, "biasFlags": bias_flags,
    }


def list_entries(domain: str | None = None,
                 status: str | None = None) -> tuple[DecisionStats, list[str]]:
    """All entries matching filters (newest date first) + derived stats + warnings.
    Stats are computed over the FILTERED set. Fail-open on malformed entries."""
    entries, warnings = _all_entries()
    if domain:
        entries = [e for e in entries if e.domain.lower() == domain.lower()]
    if status:
        entries = [e for e in entries if e.status == status]
    entries.sort(key=lambda e: e.date, reverse=True)
    stats = compute_stats(entries)
    return DecisionStats(entries=entries, **stats), warnings
