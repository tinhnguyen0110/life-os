"""modules/code_insight/service.py — the on-demand repo read (REPO-MEMORY-P1, #64).

Reads a local repo FRESH on every call (never indexed → never stale): structure + README + recent
git-log + stack-detect + asOf. Reuses dev_activity's repo-resolve (the DEV_TRACING_ROOTS :ro mounts)
+ the projects read-only git whitelist (read-only HARD invariant — NO mutating git). Everything is
BOUNDED (caps + the cap noted in a warning — never a 10k-file/line dump). Fail-soft per sub-read (a
README/git/dir failure → that field empty + a warning; the rest still returns). honest: a missing
repo → found:false + honest-empty (never a crash, never fabricated).
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timezone

from .schema import CodeInsight, RepoCommit

logger = logging.getLogger("life-os.code_insight.service")

# Bounds (agent-first: lean, never a wall-of-text dump). Each cap is surfaced in a warning when hit.
_MAX_STRUCTURE = 80        # top-level entries
_MAX_README_CHARS = 4000   # README excerpt
_MAX_COMMITS = 15          # recent git-log
# Dirs skipped in the structure listing (the LOC_SKIP-style ignore — noise an agent doesn't want).
_SKIP_DIRS = frozenset({".git", "node_modules", "vendor", "dist", "build", "__pycache__",
                        ".next", ".venv", "venv", ".mypy_cache", ".pytest_cache", "target"})
# READ-ONLY git whitelist (mirrors projects/reader._READ_ONLY_GIT — mutating ops structurally refused).
_READ_ONLY_GIT = frozenset({"log", "rev-parse", "rev-list", "status", "ls-files", "show-ref"})
# Manifest file → stack name (presence-detect).
_STACK_MARKERS: list[tuple[str, str]] = [
    ("package.json", "node"), ("requirements.txt", "python"), ("pyproject.toml", "python"),
    ("setup.py", "python"), ("go.mod", "go"), ("Cargo.toml", "rust"), ("pom.xml", "java"),
    ("build.gradle", "java"), ("Gemfile", "ruby"), ("composer.json", "php"),
    ("Dockerfile", "docker"), ("docker-compose.yml", "docker"),
]
_README_NAMES = ("README.md", "README.MD", "README", "README.txt", "README.rst", "readme.md")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_git_roots() -> list[str]:
    """Reuse dev_activity's configured roots (the :ro mounts). Lazy import avoids a hard dep."""
    from modules.dev_activity import service as dev
    return dev.scan_roots()


def resolve_repo(repo: str) -> str | None:
    """Resolve a ``repo`` (a NAME matched against the repos under the roots, or a PATH under a root)
    to an absolute git-repo path, or None. Security: a path must be UNDER a configured root + be a
    git repo (no arbitrary-path traversal — only the mounted dev tree is readable)."""
    from modules.dev_activity import service as dev
    roots = _read_git_roots()
    req = (repo or "").strip()
    if not req:
        return None
    # 1) exact path under a root (must be inside a root + a git repo)
    for root in roots:
        cand = os.path.abspath(os.path.join(root, req)) if not os.path.isabs(req) else req
        root_abs = os.path.abspath(root)
        if cand == root_abs or cand.startswith(root_abs + os.sep):
            if os.path.isdir(os.path.join(cand, ".git")):
                return cand
    # 2) NAME match: a repo whose basename == req, among the repos found under each root
    for root in roots:
        for repo_path in dev._find_repos(root):
            if os.path.basename(repo_path.rstrip("/")) == req:
                return repo_path
    return None


def _git(repo_path: str, args: list[str], *, timeout: float = 10.0) -> str:
    """Run ONE read-only git command (whitelist-enforced). Raises on non-zero/timeout/missing-git
    (the caller fail-softs that sub-read). NEVER a mutating subcommand."""
    if not args or args[0] not in _READ_ONLY_GIT:
        raise ValueError(f"refusing non-read-only git op: {args[:1]}")
    proc = subprocess.run(["git", "-C", repo_path, *args], capture_output=True, text=True,
                          check=False, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _structure(root: str, warnings: list[str]) -> list[str]:
    """Top-level entries (dirs end with /), skipping noise dirs, bounded at _MAX_STRUCTURE."""
    try:
        names = sorted(os.listdir(root))
    except OSError as exc:
        warnings.append(f"structure unreadable ({type(exc).__name__})")
        return []
    out: list[str] = []
    for name in names:
        if name in _SKIP_DIRS:
            continue
        full = os.path.join(root, name)
        out.append(name + "/" if os.path.isdir(full) else name)
    if len(out) > _MAX_STRUCTURE:
        warnings.append(f"structure truncated to {_MAX_STRUCTURE} of {len(out)} entries")
        out = out[:_MAX_STRUCTURE]
    return out


def _readme(root: str, warnings: list[str]) -> str | None:
    """First README* found → a bounded excerpt (cap _MAX_README_CHARS, note if truncated). None if
    no README. Fail-soft on a read error."""
    for name in _README_NAMES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read(_MAX_README_CHARS + 1)
            except OSError as exc:
                warnings.append(f"README unreadable ({type(exc).__name__})")
                return None
            if len(text) > _MAX_README_CHARS:
                warnings.append(f"README truncated to {_MAX_README_CHARS} chars")
                return text[:_MAX_README_CHARS]
            return text
    return None


def _recent_commits(root: str, warnings: list[str]) -> list[RepoCommit]:
    """Recent commits (newest-first, bounded) via the read-only git whitelist. Fail-soft."""
    try:
        out = _git(root, ["log", f"-n{_MAX_COMMITS}", "--no-merges",
                          "--pretty=format:%h\x1f%s\x1f%cs"])
    except Exception as exc:  # noqa: BLE001 — git failure → empty + warning, the rest returns
        warnings.append(f"git log failed ({type(exc).__name__})")
        return []
    commits: list[RepoCommit] = []
    for line in out.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 3:
            commits.append(RepoCommit(sha=parts[0], msg=parts[1], date=parts[2]))
    return commits


def _stack(root: str) -> list[str]:
    """Detected stack from manifest-file presence (deduped, order-stable)."""
    found: list[str] = []
    for fname, stack in _STACK_MARKERS:
        if os.path.isfile(os.path.join(root, fname)) and stack not in found:
            found.append(stack)
    return found


def code_insight(repo: str) -> CodeInsight:
    """The on-demand repo read. Resolves ``repo`` (name or path under the :ro roots), then reads
    structure + README + recent git-log + stack FRESH. honest-empty + found:false + warning when the
    repo doesn't resolve; each sub-read fail-soft; asOf always set (live read)."""
    warnings: list[str] = []
    root = resolve_repo(repo)
    if root is None:
        if not _read_git_roots():
            warnings.append("DEV_TRACING_ROOTS not set — no repos resolvable (honest-empty)")
        else:
            warnings.append(f"repo {repo!r} not found under the configured roots")
        return CodeInsight(repo=repo, root="", found=False, asOf=_now_iso(), warnings=warnings)

    structure = _structure(root, warnings)
    readme = _readme(root, warnings)
    commits = _recent_commits(root, warnings)
    stack = _stack(root)
    return CodeInsight(
        repo=repo, root=root, found=True, structure=structure, readme=readme,
        recentCommits=commits, stack=stack, asOf=_now_iso(), warnings=warnings,
    )
