"""store/md_store.py — markdown + git store (C5, ARCH §6).

Persists metadata as markdown files under ``DATA_DIR`` and makes **every write one
git commit** → free history, and external Claude Code reads the raw files directly.

Atomicity contract: write file → ``git add`` → ``git commit`` is one operation. A
half-written file with no commit is a bug. We write to a temp file in the same
directory then ``os.replace`` (atomic on POSIX) before staging.

DATA_DIR is its own git repo, initialised on first use (the source repo is
separate). Reads never touch git.

Concurrency: a module-level lock serialises writes so two concurrent writes can't
interleave staging/commit. Single-user local app — a simple in-process lock is
sufficient (no Redis/queue — CLAUDE.md §2 no-infra-bloat).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path

from core.config import settings

logger = logging.getLogger("life-os.md_store")

_write_lock = threading.Lock()


class MdStoreError(RuntimeError):
    """Raised when a git-backed write cannot be completed atomically."""


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _ensure_repo(root: Path) -> None:
    """Ensure ``root`` exists and is a git repo (init + identity on first use)."""
    root.mkdir(parents=True, exist_ok=True)
    if (root / ".git").exists():
        return
    res = _run_git(["init"], root)
    if res.returncode != 0:
        raise MdStoreError(f"git init failed in {root}: {res.stderr.strip()}")
    # Local identity so commits work even if global git identity is unset.
    _run_git(["config", "user.name", "life-os"], root)
    _run_git(["config", "user.email", "life-os@localhost"], root)
    logger.info("initialised data git repo at %s", root)


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp-file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)  # atomic on POSIX


def _data_root() -> Path:
    return settings.data_dir.resolve()


def _resolve_under_root(path: str | Path) -> tuple[Path, Path]:
    """Resolve ``path`` to (root, absolute_target), enforcing it stays in DATA_DIR.

    Accepts either a DATA_DIR-relative string ("projects/x/status.md") or an
    absolute path already inside DATA_DIR (as the tester passes). Both forms map
    to the same on-disk file; anything escaping DATA_DIR raises MdStoreError.
    """
    root = _data_root()
    p = Path(path)
    target = (p if p.is_absolute() else root / p).resolve()
    if target != root and not str(target).startswith(str(root) + os.sep):
        raise MdStoreError(f"path escapes DATA_DIR: {path!r}")
    return root, target


def write_file(path: str | Path, content: str, message: str | None = None) -> str:
    """Write ``content`` to ``path`` (inside DATA_DIR) and commit. Returns 40-char sha.

    ``path`` may be DATA_DIR-relative or an absolute path inside DATA_DIR. The
    write is atomic (temp-file + os.replace) and produces exactly ONE git commit.
    Initialises the DATA_DIR git repo on first write.

    Raises:
        MdStoreError: on path escape, git failure, or commit failure.
        ValueError:   on empty path.

    Identical content (nothing staged) returns the current HEAD sha rather than
    erroring on git's "nothing to commit".
    """
    if path is None or str(path).strip() == "":
        raise ValueError("path must be non-empty")
    with _write_lock:
        root, target = _resolve_under_root(path)
        _ensure_repo(root)
        _atomic_write(target, content)
        rel = target.relative_to(root).as_posix()
        add = _run_git(["add", "--", rel], root)
        if add.returncode != 0:
            raise MdStoreError(f"git add failed for {rel}: {add.stderr.strip()}")
        # Nothing staged (identical content) → no-op commit; return current HEAD.
        staged = _run_git(["diff", "--cached", "--quiet"], root)
        if staged.returncode == 0:
            head = _run_git(["rev-parse", "HEAD"], root)
            current = head.stdout.strip() if head.returncode == 0 else ""
            logger.info("no change for %s — skipping commit (head=%s)", rel, current[:8])
            return current
        msg = message or f"update {rel}"
        commit = _run_git(["commit", "-m", msg], root)
        if commit.returncode != 0:
            raise MdStoreError(f"git commit failed for {rel}: {commit.stderr.strip()}")
        rev = _run_git(["rev-parse", "HEAD"], root)
        commit_hash = rev.stdout.strip()
        logger.info("committed %s (%s)", rel, commit_hash[:8])
        return commit_hash


def read_file(path: str | Path) -> str:
    """Read a file inside DATA_DIR. Raises FileNotFoundError if it does not exist.

    ``path`` may be DATA_DIR-relative or absolute (inside DATA_DIR).
    """
    _root, target = _resolve_under_root(path)
    if not target.is_file():
        raise FileNotFoundError(f"no such file in DATA_DIR: {path!r}")
    return target.read_text(encoding="utf-8")


def exists(path: str | Path) -> bool:
    """True if ``path`` (relative or absolute) resolves to a file inside DATA_DIR."""
    try:
        _root, target = _resolve_under_root(path)
    except MdStoreError:
        return False
    return target.is_file()


def delete_file(path: str | Path, message: str | None = None) -> str | None:
    """Delete a file inside DATA_DIR and commit the removal. Returns the sha, or
    None if the file did not exist (no-op, no commit).

    Mirrors write_file's contract: the removal is ``git rm`` + one commit, so
    history stays complete. Path-escape is rejected (MdStoreError). Idempotent:
    deleting an absent file is a no-op returning None (callers map to 404 if they
    need to distinguish — md_store stays fail-soft).
    """
    if path is None or str(path).strip() == "":
        raise ValueError("path must be non-empty")
    with _write_lock:
        root, target = _resolve_under_root(path)
        if not target.is_file():
            return None
        _ensure_repo(root)
        rel = target.relative_to(root).as_posix()
        rm = _run_git(["rm", "--", rel], root)
        if rm.returncode != 0:
            # Fall back to filesystem remove + stage (e.g. file untracked in git).
            try:
                target.unlink()
            except FileNotFoundError:
                return None
            _run_git(["add", "--", rel], root)
        staged = _run_git(["diff", "--cached", "--quiet"], root)
        if staged.returncode == 0:
            head = _run_git(["rev-parse", "HEAD"], root)
            return head.stdout.strip() if head.returncode == 0 else ""
        msg = message or f"delete {rel}"
        commit = _run_git(["commit", "-m", msg], root)
        if commit.returncode != 0:
            raise MdStoreError(f"git commit (delete) failed for {rel}: {commit.stderr.strip()}")
        rev = _run_git(["rev-parse", "HEAD"], root)
        commit_hash = rev.stdout.strip()
        logger.info("deleted %s (%s)", rel, commit_hash[:8])
        return commit_hash


# --- Back-compat aliases (DATA_DIR-relative semantics for module callers) ---
# Feature modules pass relative paths; these are the same functions. read() keeps
# the None-on-missing convenience used internally; read_file() raises (test contract).
write = write_file


def read(rel_path: str) -> str | None:
    """Read DATA_DIR-relative ``rel_path``; returns None if absent (vs read_file raise)."""
    try:
        return read_file(rel_path)
    except FileNotFoundError:
        return None
