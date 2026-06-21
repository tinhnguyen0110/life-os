"""modules/dev_activity/service.py — local git scan + derive (DEV-TRACING-P1, #63).

PORTS the proven validate_dev_tracing.py `local_probe` logic (git --numstat, LOC_SKIP filter, the
binary-numstat guard) — zero invention — and ADDS the dispatch refinements: --no-merges --all,
author-email identity-map (you vs other), TZ→VN-day, source-tag, per-commit sha (for P2 dedup).

Raw-data-first: store the per-(date,repo,source) aggregates; derive byDay/byRepo/summary in the
reader. LOC is INFORMATIONAL (Goodhart — LOC_SKIP applied, surfaced secondary, NEVER ranked/scored).
Fail-soft per repo (a bad repo never aborts the scan); honest-empty + WARNING when roots unreachable
(NOT silent-zero, NOT crash — the host-file-source-must-mount lesson).
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import store

logger = logging.getLogger("life-os.dev_activity.service")

# VN day = UTC+7 (mirror modules/tracing — single offset, no DST). All date bucketing uses this.
VN_TZ = timezone(timedelta(hours=7))

# PORTED VERBATIM from validate_dev_tracing.py LOC_SKIP — lock/generated/vendor/dist/build/min/
# node_modules/images → no fake +5000 LOC. A path matching any substring is excluded from LOC.
LOC_SKIP = ("-lock.json", ".lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
            "/node_modules/", "/vendor/", "/dist/", "/build/", ".min.js", ".min.css",
            "/generated/", ".svg", ".png", ".jpg")

_DEFAULT_DAYS = 90  # P1 local backfill (P2 → 1yr with remote)
# git log format: one C-line per commit with email + ISO date + sha, then --numstat file lines.
_LOG_FORMAT = "C|%ae|%cI|%H"


def _now() -> datetime:
    return datetime.now(VN_TZ)


def _vn_day(iso_ts: str) -> str:
    """The VN calendar day (YYYY-MM-DD) of an ISO-8601 commit timestamp. git %cI is offset-aware;
    convert to VN. A 23:30+07:00 commit → that VN day; a 23:30Z commit → the next VN day."""
    dt = datetime.fromisoformat(iso_ts.strip())
    if dt.tzinfo is None:  # defensive: a naive ts → assume UTC (git %cI is always offset-aware)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(VN_TZ).strftime("%Y-%m-%d")


def _vn_hhmm(iso_ts: str) -> str:
    dt = datetime.fromisoformat(iso_ts.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(VN_TZ).strftime("%H:%M")


def _is_skip(path: str) -> bool:
    """PORTED from validate's is_skip — a file path matching any LOC_SKIP substring is excluded."""
    p = path.lower()
    return any(s in p for s in LOC_SKIP)


def scan_roots() -> list[str]:
    """The configured scan roots (colon-separated `DEV_TRACING_ROOTS`, read directly from env like
    config's TINHDEV_ROOT). Empty/unset → []."""
    raw = os.environ.get("DEV_TRACING_ROOTS", "").strip()
    return [r for r in raw.split(":") if r.strip()] if raw else []


def your_emails() -> set[str]:
    """The identity-map (colon-separated `DEV_TRACING_EMAILS`, lowercased). Empty/unset → empty set
    → every commit tags "other" + a warning (NEVER silently count all as "you")."""
    raw = os.environ.get("DEV_TRACING_EMAILS", "").strip()
    return {e.strip().lower() for e in raw.split(":") if e.strip()} if raw else set()


def _find_repos(root: str) -> list[str]:
    """Git repos under a root: the root itself if it has .git, else its 1-level children with .git.
    A non-dir / unreadable root → [] (the caller warns). Mirrors the validate multi-root approach."""
    repos: list[str] = []
    if not os.path.isdir(root):
        return repos
    if os.path.isdir(os.path.join(root, ".git")):
        repos.append(root)
        return repos
    try:
        for name in sorted(os.listdir(root)):
            child = os.path.join(root, name)
            if os.path.isdir(os.path.join(child, ".git")):
                repos.append(child)
    except OSError as exc:  # permission/IO — warn upstream, don't crash
        logger.warning("dev_activity: cannot list root %s: %s", root, exc)
    return repos


def _scan_repo(path: str, since_day: str, emails: set[str], agg: dict,
               seen_shas: set[str] | None = None) -> None:
    """PORT of validate local_probe (+ refinements): git log --no-merges --all --since --numstat for
    one repo → fold per (day, repo, source) into ``agg``. Fail-soft: a git error logs + returns
    (the repo is skipped, the scan continues). DEV-TRACING-P2 (#63): records each commit's sha into
    ``seen_shas`` so the remote pull can DEDUP (a commit seen local AND remote counts ONCE)."""
    repo = os.path.basename(path.rstrip("/"))
    try:
        out = subprocess.run(
            ["git", "-C", path, "log", "--no-merges", "--all", f"--since={since_day}",
             "--numstat", f"--pretty=format:{_LOG_FORMAT}", "--date=iso-strict"],
            capture_output=True, text=True, timeout=60,
        ).stdout
    except Exception as exc:  # noqa: BLE001 — any git failure → skip this repo, continue the scan
        logger.warning("dev_activity: git log failed for %s: %s", path, exc)
        agg.setdefault("_warnings", []).append(f"repo {repo} skipped (git error)")
        return

    cur_day: str | None = None
    cur_src: str | None = None
    for line in out.splitlines():
        if line.startswith("C|"):
            _, email, cdate, sha = line.split("|", 3)
            if seen_shas is not None:
                seen_shas.add(sha.strip())  # P2 dedup: remember this commit so remote won't re-count it
            cur_day = _vn_day(cdate)
            cur_src = "you" if email.strip().lower() in emails else "other"
            hhmm = _vn_hhmm(cdate)
            key = (cur_day, repo, cur_src)
            a = agg[key]
            a["commits"] += 1
            a["first"] = min(a["first"] or hhmm, hhmm)
            a["last"] = max(a["last"] or hhmm, hhmm)
        elif line.strip() and cur_day and "\t" in line:
            parts = line.split("\t")
            if len(parts) >= 3 and not _is_skip(parts[2]):
                try:  # binary files show "-\t-\t" → ValueError → 0 LOC (the validate guard)
                    add, dele = int(parts[0]), int(parts[1])
                except ValueError:
                    continue
                a = agg[(cur_day, repo, cur_src)]
                a["loc_add"] += add
                a["loc_del"] += dele


def _span(first: str | None, last: str | None) -> str:
    """Active-span 'Hh Mm' from first/last HH:MM (same VN day). Single/none commit → ''."""
    if not first or not last or first == last:
        return ""
    fh, fm = (int(x) for x in first.split(":"))
    lh, lm = (int(x) for x in last.split(":"))
    mins = (lh * 60 + lm) - (fh * 60 + fm)
    if mins <= 0:
        return ""
    h, m = divmod(mins, 60)
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m}m")


def scan(days: int = _DEFAULT_DAYS) -> dict:
    """Scan all configured roots → UPSERT per (date, repo, source). Returns a result summary
    {scannedRepos, days, rowsUpserted, yourCommits, warnings}. Idempotent (upsert overwrites each
    day's aggregate). honest-empty + warnings when roots are unreachable / identity unset."""
    roots = scan_roots()
    emails = your_emails()
    warnings: list[str] = []
    if not roots:
        warnings.append("DEV_TRACING_ROOTS not set — no repos to scan (honest-empty)")
    if not emails:
        warnings.append("DEV_TRACING_EMAILS not set — all commits tagged 'other' (set your git "
                        "emails to attribute 'you'); your totals will be 0 until configured")

    since_day = (_now() - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    agg: dict = defaultdict(lambda: {"commits": 0, "loc_add": 0, "loc_del": 0,
                                     "first": None, "last": None})
    scanned = 0
    for root in roots:
        repos = _find_repos(root)
        if not repos and not os.path.isdir(root):
            warnings.append(f"root {root} unreachable (not mounted?) — skipped")
            continue
        for repo_path in repos:
            _scan_repo(repo_path, since_day, emails, agg)
            scanned += 1
    warnings.extend(agg.pop("_warnings", []))

    rows = 0
    your_commits = 0
    for (date, repo, source), a in agg.items():
        store.upsert_day(
            date=date, repo=repo, source=source, commits=a["commits"],
            loc_added=a["loc_add"], loc_deleted=a["loc_del"],
            first_ts=a["first"], last_ts=a["last"],
        )
        rows += 1
        if source == "you":
            your_commits += a["commits"]

    return {"scannedRepos": scanned, "days": max(1, days), "rowsUpserted": rows,
            "yourCommits": your_commits, "warnings": warnings}
