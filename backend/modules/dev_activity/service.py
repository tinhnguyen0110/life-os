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

import json
import logging
import os
import subprocess
import urllib.error
import urllib.request
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

_DEFAULT_DAYS = 365  # DEV-TRACING-P2 (#63): 1yr backfill (was 90d local-only in P1; remote+local now)
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
    """The identity-map (COMMA-separated `DEV_TRACING_EMAILS`, lowercased). Empty/unset → empty set
    → every commit tags "other" + a warning (NEVER silently count all as "you").

    #84: emails are COMMA-separated (the env value is a comma list of git author emails/names) —
    NOT colon-separated like DEV_TRACING_ROOTS (filesystem paths, colon-separated). split(":") here
    collapsed the whole list into ONE element so no commit email matched → yourCommits=0 (the
    dev-tracing "you=0" bug). ROOTS keeps split(":") (paths); ONLY emails are comma-split."""
    raw = os.environ.get("DEV_TRACING_EMAILS", "").strip()
    return {e.strip().lower() for e in raw.split(",") if e.strip()} if raw else set()


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


# --------------------------------------------------------------------------- #
# DEV-TRACING-P2 (#63) — REMOTE sources (GitHub + Bitbucket Server) + dedup.    #
# Cred from env ONLY (#50 user-only); unset → skip-source + honest warning.     #
# A commit seen LOCAL ⊕ REMOTE counts ONCE (dedup by sha). HTTP via the          #
# mockable _http_get_json boundary (tests monkeypatch it — no live network).     #
# --------------------------------------------------------------------------- #
def _http_get_json(url: str, headers: dict[str, str], timeout: int = 20) -> object:
    """The single HTTP boundary the remote probes use (tests monkeypatch THIS). Returns parsed JSON.
    Raises urllib.error.HTTPError on a non-2xx (the caller maps 401/403/429 → honest warning)."""
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — fixed https API hosts
        return json.loads(r.read())


def _github_commits(token: str, user: str, since_iso: str, warnings: list[str]) -> list[dict]:
    """PORT of validate github_probe: list the user's repos (owner+collaborator+org) → the user's
    commits since → flat records {sha, email, dateIso, repo, locAdd, locDel}. Per-source fail-soft:
    a 401/403/429/network error → honest warning + return what we have (NOT a crash, NOT fabricated).
    LOC via the per-commit detail (additions/deletions, LOC_SKIP-filtered) for up to 10 commits/repo
    (the validate probe-budget; remote LOC is coarser than local — surfaced honestly)."""
    hdr = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
           "User-Agent": "life-os-dev-activity/1.0", "X-GitHub-Api-Version": "2022-11-28"}
    out: list[dict] = []
    try:
        repos = _http_get_json(
            "https://api.github.com/user/repos?per_page=100&sort=pushed"
            "&affiliation=owner,collaborator,organization_member", hdr)
    except urllib.error.HTTPError as e:
        warnings.append(f"github: list-repos HTTP {e.code} (token scope? rate-limit?) — source skipped")
        return out
    except Exception as e:  # noqa: BLE001 — network/parse → skip the source honestly
        warnings.append(f"github: unreachable ({type(e).__name__}) — source skipped")
        return out
    if not isinstance(repos, list):
        return out
    for repo in repos:
        full = repo.get("full_name", "")
        name = repo.get("name", full)
        try:
            commits = _http_get_json(
                f"https://api.github.com/repos/{full}/commits?author={user}"
                f"&since={since_iso}&per_page=100", hdr)
        except urllib.error.HTTPError as e:
            if e.code in (409, 404):  # empty repo / no access → skip silently (per validate)
                continue
            warnings.append(f"github: {full} commits HTTP {e.code} — repo skipped")
            continue
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(commits, list):
            continue
        # LOC detail for up to 10 recent commits/repo (probe-budget; remote LOC is coarser-honest).
        loc_by_sha: dict[str, tuple[int, int]] = {}
        for c in commits[:10]:
            sha = c.get("sha", "")
            try:
                detail = _http_get_json(f"https://api.github.com/repos/{full}/commits/{sha}", hdr)
                files = detail.get("files", []) if isinstance(detail, dict) else []
                add = sum(f.get("additions", 0) for f in files if not _is_skip(f.get("filename", "")))
                dele = sum(f.get("deletions", 0) for f in files if not _is_skip(f.get("filename", "")))
                loc_by_sha[sha] = (add, dele)
            except Exception:  # noqa: BLE001 — LOC detail is best-effort; commit still counts
                pass
        for c in commits:
            sha = c.get("sha", "")
            commit = c.get("commit", {})
            cdate = commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")
            email = (commit.get("author", {}).get("email", "") or "").lower()
            if not sha or not cdate:
                continue
            add, dele = loc_by_sha.get(sha, (0, 0))
            out.append({"sha": sha, "email": email, "dateIso": cdate, "repo": name,
                        "locAdd": add, "locDel": dele})
    return out


def _bitbucket_commits(host: str, user: str, pw: str, since_dt: datetime,
                       warnings: list[str]) -> list[dict]:
    """PORT of validate bitbucket_server_probe: REST 1.0 projects→repos→commits (newest-first, break
    past `since`). Flat records {sha, email, dateIso, repo, locAdd, locDel(0 — coarse)}. Per-source
    fail-soft (auth/VPN/network → honest warning + skip)."""
    import base64
    auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
    hdr = {"Authorization": f"Basic {auth}", "Accept": "application/json",
           "User-Agent": "life-os-dev-activity/1.0"}
    since_ms = int(since_dt.timestamp() * 1000)
    out: list[dict] = []
    try:
        projects = _http_get_json(f"{host}/rest/api/1.0/projects?limit=100", hdr, timeout=25)
    except urllib.error.HTTPError as e:
        warnings.append(f"bitbucket: HTTP {e.code} (cred/VPN?) — source skipped")
        return out
    except Exception as e:  # noqa: BLE001
        warnings.append(f"bitbucket: unreachable ({type(e).__name__}, VPN?) — source skipped")
        return out
    for proj in (projects.get("values", []) if isinstance(projects, dict) else []):
        pkey = proj.get("key", "")
        try:
            repos = _http_get_json(f"{host}/rest/api/1.0/projects/{pkey}/repos?limit=100", hdr, 25)
        except Exception:  # noqa: BLE001
            continue
        for repo in (repos.get("values", []) if isinstance(repos, dict) else []):
            slug = repo.get("slug", "")
            try:
                commits = _http_get_json(
                    f"{host}/rest/api/1.0/projects/{pkey}/repos/{slug}/commits?limit=100", hdr, 25)
            except Exception:  # noqa: BLE001
                continue
            for c in (commits.get("values", []) if isinstance(commits, dict) else []):
                ts = c.get("authorTimestamp", 0)
                if ts < since_ms:
                    break  # newest-first → past the window, stop this repo
                au = c.get("author", {}) or {}
                email = (au.get("emailAddress", "") or "").lower()
                sha = c.get("id", "")
                if not sha:
                    continue
                dt = datetime.fromtimestamp(ts / 1000, timezone.utc)
                out.append({"sha": sha, "email": email, "dateIso": dt.isoformat(),
                            "repo": f"{pkey}/{slug}", "locAdd": 0, "locDel": 0})
    return out


def github_creds() -> list[tuple[str, str]]:
    """GitHub (token, user) pairs from env: GITHUB_PAT/GITHUB_USER (+ PAT2/USER2 multi-account, per
    the validate script). Only pairs where BOTH are set. Empty → GitHub skipped + warning. Cred is
    read from env ONLY (#50 user-only) — never logged, never committed."""
    pairs: list[tuple[str, str]] = []
    for tk, uk in (("GITHUB_PAT", "GITHUB_USER"), ("GITHUB_PAT2", "GITHUB_USER2")):
        tok, usr = os.environ.get(tk, "").strip(), os.environ.get(uk, "").strip()
        if tok and usr:
            pairs.append((tok, usr))
    return pairs


def bitbucket_cred() -> tuple[str, str, str] | None:
    """Bitbucket Server (host, user, pw) from env: BITBUCKET_HOST + BITBUCKET_USER + BITBUCKET_PASS.
    All three required → returns the triple, else None (source skipped + warning). Env-only, #50."""
    host = os.environ.get("BITBUCKET_HOST", "").strip().rstrip("/")
    user = os.environ.get("BITBUCKET_USER", "").strip()
    pw = os.environ.get("BITBUCKET_PASS", "").strip()
    return (host, user, pw) if (host and user and pw) else None


def _fold_remote(records: list[dict], emails: set[str], agg: dict, seen_shas: set[str],
                 source_system: str) -> None:
    """Fold remote commit records into ``agg`` (per day×repo×source), DEDUP by sha: a commit whose
    sha is already in ``seen_shas`` (seen locally or in a prior remote) is SKIPPED — counted once.
    Adds newly-seen shas to the set. THE P2 invariant (local⊕remote → 1)."""
    for rec in records:
        sha = rec["sha"]
        if sha in seen_shas:
            continue  # dedup — already counted (local or another remote)
        seen_shas.add(sha)
        day = _vn_day(rec["dateIso"])
        hhmm = _vn_hhmm(rec["dateIso"])
        src = "you" if rec["email"] in emails else "other"
        a = agg[(day, rec["repo"], src)]
        a["commits"] += 1
        a["loc_add"] += int(rec.get("locAdd", 0))
        a["loc_del"] += int(rec.get("locDel", 0))
        a["first"] = min(a["first"] or hhmm, hhmm)
        a["last"] = max(a["last"] or hhmm, hhmm)


def scan(days: int = _DEFAULT_DAYS) -> dict:
    """Scan all configured roots → UPSERT per (date, repo, source). Returns a result summary
    {scannedRepos, days, rowsUpserted, yourCommits, warnings}. Idempotent (upsert overwrites each
    day's aggregate). honest-empty + warnings when roots are unreachable / identity unset.

    DEV-TRACING-P2 (#63): after the LOCAL scan, pull REMOTE sources (GitHub + Bitbucket, cred from
    env) and DEDUP by sha (a commit seen local AND remote counts ONCE). Per-source fail-soft — an
    unauthed/unreachable/rate-limited remote → honest warning + skip, the scan completes with the
    other sources. Cred unset → that source skipped + warned (never fabricated, never crash)."""
    roots = scan_roots()
    emails = your_emails()
    warnings: list[str] = []
    if not roots:
        warnings.append("DEV_TRACING_ROOTS not set — no repos to scan (honest-empty)")
    if not emails:
        warnings.append("DEV_TRACING_EMAILS not set — all commits tagged 'other' (set your git "
                        "emails to attribute 'you'); your totals will be 0 until configured")

    since_dt = _now() - timedelta(days=max(1, days))
    since_day = since_dt.strftime("%Y-%m-%d")
    since_iso = since_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    agg: dict = defaultdict(lambda: {"commits": 0, "loc_add": 0, "loc_del": 0,
                                     "first": None, "last": None})
    seen_shas: set[str] = set()  # P2 dedup: a commit counted (local or remote) goes here once
    scanned = 0
    # #85: the set of repo NAMES this scan actually touched (basename = the `repo` column). The
    # scan is AUTHORITATIVE for (since_day..today × these repos); we delete their stale rows before
    # re-upserting so an attribution change (e.g. #84 'other'→'you') leaves NO orphan source row.
    # Includes a LOCAL repo even if it had 0 commits this window (it was scanned → a now-empty
    # (date,repo) stale row must still be cleared); remote repo names are added from the agg keys.
    scanned_repos: set[str] = set()
    # --- LOCAL scan first (records shas into seen_shas for the remote dedup) ---
    for root in roots:
        repos = _find_repos(root)
        if not repos and not os.path.isdir(root):
            warnings.append(f"root {root} unreachable (not mounted?) — skipped")
            continue
        for repo_path in repos:
            _scan_repo(repo_path, since_day, emails, agg, seen_shas)
            scanned_repos.add(os.path.basename(repo_path.rstrip("/")))  # scanned even if 0 commits
            scanned += 1
    warnings.extend(agg.pop("_warnings", []))

    # --- REMOTE pull (P2): GitHub + Bitbucket, DEDUP by sha against local + each other. Per-source
    # fail-soft (cred unset / unreachable / rate-limit → honest warning + skip). Cred from env only. ---
    gh_pairs = github_creds()
    if not gh_pairs:
        warnings.append("GITHUB_PAT/GITHUB_USER not set — GitHub source skipped (set to include remotes)")
    for token, user in gh_pairs:
        _fold_remote(_github_commits(token, user, since_iso, warnings), emails, agg, seen_shas, "github")
    bb = bitbucket_cred()
    if bb is None:
        warnings.append("BITBUCKET_HOST/USER/PASS not set — Bitbucket source skipped")
    else:
        host, bu, bp = bb
        _fold_remote(_bitbucket_commits(host, bu, bp, since_dt, warnings), emails, agg, seen_shas,
                     "bitbucket")

    # #85: the agg keys also name every REMOTE repo this scan re-derived (GitHub/Bitbucket repo
    # names) — union them into the authoritative scanned set so their stale rows are cleared too.
    scanned_repos.update(repo for (_d, repo, _s) in agg.keys())

    # #85 shape (a) — ATOMIC authoritative-window replace: in ONE transaction, DELETE the stale
    # rows for (date >= since_day × scanned_repos) THEN upsert the fresh aggregates. So an
    # attribution change (#84 'other'→'you') leaves NO orphan source row, AND a flaky/partial scan
    # rolls back instead of leaving a wiped-not-refilled window (#72-incident-level safety; the
    # delete is SCOPED to the repos scanned this run → a 0-commit/unreachable scan wipes nothing).
    aggregates = [
        {"date": date, "repo": repo, "source": source, "commits": a["commits"],
         "loc_added": a["loc_add"], "loc_deleted": a["loc_del"],
         "first_ts": a["first"], "last_ts": a["last"]}
        for (date, repo, source), a in agg.items()
    ]
    store.replace_window(since_day, scanned_repos, aggregates)
    rows = len(aggregates)
    your_commits = sum(a["commits"] for a in aggregates if a["source"] == "you")

    # DEV-ACTIVITY-STORE (#77): stamp the scan time so the read path surfaces honest freshness.
    # Stamped even on a 0-row scan (a scan DID run — "scanned, found nothing" ≠ "never scanned").
    store.set_last_scanned(_now().isoformat())

    return {"scannedRepos": scanned, "days": max(1, days), "rowsUpserted": rows,
            "yourCommits": your_commits, "warnings": warnings}
