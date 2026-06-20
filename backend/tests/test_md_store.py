"""tests/test_md_store.py — unit tests for store/md_store.py.

Sprint 0 Gate 2. API:
  write(rel_path: str, content: str, message: str | None) -> str  (40-char sha)
  read(rel_path: str) -> str | None
  exists(rel_path: str) -> bool

Each write must produce exactly ONE git commit and return the sha.
DATA_DIR may start non-git — init on first write.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import store.md_store as md_store


# ---------------------------------------------------------------------------
# Fixtures — redirect DATA_DIR to a tmp path per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch):
    """Each test gets a fresh tmp DATA_DIR to avoid git history pollution."""
    # Close any stale state from store.db (md_store doesn't share connections,
    # but reset settings so the repo inits fresh)
    from core import config
    monkeypatch.setattr(config.settings, "data_dir", tmp_path, raising=False)
    yield tmp_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_commit_count(repo: Path) -> int:
    res = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0:
        return 0
    return int(res.stdout.strip())


def _git_head_sha(repo: Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return res.stdout.strip()


# ---------------------------------------------------------------------------
# First write initialises git repo
# ---------------------------------------------------------------------------

class TestMdStoreInit:
    def test_first_write_creates_git_repo(self, tmp_path):
        md_store.write("notes/hello.md", "# Hello\n", "init note")
        assert (tmp_path / ".git").is_dir(), "data_dir must be a git repo after first write"

    def test_first_write_returns_40char_sha(self, tmp_path):
        sha = md_store.write("test.md", "content", "first")
        assert isinstance(sha, str), f"Expected str sha, got {type(sha)}"
        assert len(sha) == 40, f"Expected 40-char sha, got {sha!r}"

    def test_returned_sha_matches_git_head(self, tmp_path):
        sha = md_store.write("a.md", "body", "a")
        head = _git_head_sha(tmp_path)
        assert sha == head, f"Returned sha {sha} != HEAD {head}"

    def test_first_write_produces_exactly_one_commit(self, tmp_path):
        md_store.write("test.md", "content", "first")
        assert _git_commit_count(tmp_path) == 1


# ---------------------------------------------------------------------------
# Each write → exactly one new commit
# ---------------------------------------------------------------------------

class TestMdStoreOneCommitPerWrite:
    def test_second_write_adds_one_commit(self, tmp_path):
        md_store.write("a.md", "v1", "first")
        before = _git_commit_count(tmp_path)
        md_store.write("a.md", "v2", "second")
        after = _git_commit_count(tmp_path)
        assert after == before + 1

    def test_each_sha_unique(self, tmp_path):
        sha1 = md_store.write("x.md", "content-a", "a")
        sha2 = md_store.write("x.md", "content-b", "b")
        assert sha1 != sha2

    def test_identical_content_no_new_commit(self, tmp_path):
        """Writing identical content twice: second write must not fail."""
        md_store.write("same.md", "identical", "first")
        before = _git_commit_count(tmp_path)
        # Should not raise even if no-op
        sha = md_store.write("same.md", "identical", "second")
        assert isinstance(sha, str) and len(sha) == 40
        # Commit count same (git has nothing to commit)
        assert _git_commit_count(tmp_path) == before

    def test_creates_intermediate_dirs(self, tmp_path):
        md_store.write("projects/alpha/status.md", "# Alpha\n", "alpha")
        assert (tmp_path / "projects" / "alpha" / "status.md").exists()


# ---------------------------------------------------------------------------
# Read roundtrip
# ---------------------------------------------------------------------------

class TestMdStoreRead:
    def test_read_returns_written_content(self, tmp_path):
        content = "# Title\n\nBody text.\n"
        md_store.write("note.md", content, "write note")
        result = md_store.read("note.md")
        assert result == content

    def test_read_missing_returns_none(self, tmp_path):
        result = md_store.read("nonexistent.md")
        assert result is None

    def test_exists_true_after_write(self, tmp_path):
        md_store.write("check.md", "data", "write")
        assert md_store.exists("check.md") is True

    def test_exists_false_for_missing(self, tmp_path):
        assert md_store.exists("ghost.md") is False


# ---------------------------------------------------------------------------
# Edge cases / defensive
# ---------------------------------------------------------------------------

class TestMdStoreEdgeCases:
    def test_empty_rel_path_raises(self, tmp_path):
        with pytest.raises(ValueError):
            md_store.write("", "content", "msg")

    def test_path_traversal_blocked(self, tmp_path):
        """../escape attempts must be rejected."""
        with pytest.raises(Exception):
            md_store.write("../escape.md", "evil", "escape")

    def test_empty_content(self, tmp_path):
        sha = md_store.write("empty.md", "", "empty")
        assert isinstance(sha, str) and len(sha) == 40

    def test_unicode_content(self, tmp_path):
        content = "# Tiếng Việt\n\n日本語テスト\n"
        md_store.write("unicode.md", content, "unicode")
        assert md_store.read("unicode.md") == content

    def test_large_content(self, tmp_path):
        content = "x" * 100_000
        sha = md_store.write("large.md", content, "large")
        assert isinstance(sha, str) and len(sha) == 40
        assert md_store.read("large.md") == content

    def test_default_commit_message(self, tmp_path):
        """Passing message=None should work (defaults gracefully)."""
        sha = md_store.write("default_msg.md", "hi", None)
        assert isinstance(sha, str) and len(sha) == 40


# ---------------------------------------------------------------------------
# #25 hardening — a STALE leftover .<name>.tmp must not block the next write
# ---------------------------------------------------------------------------
class TestStaleTmpCleanup:
    def test_stale_tmp_does_not_block_write(self, tmp_path):
        """A prior crashed/interrupted write can leave a stale ``.<name>.tmp``. The next write
        must SUCCEED (clear the stale tmp + write the note) — the Permission/conflict the live
        arc hit on .22.md.tmp. Pre-seed a stale tmp, then write the real file → it lands."""
        # first write so the repo + dir exist
        md_store.write("notes/n.md", "v1", "init")
        # simulate a stale leftover tmp from a crashed prior write
        stale = tmp_path / "notes" / ".n.md.tmp"
        stale.write_text("garbage from a crashed write")
        assert stale.exists()
        # the next write must succeed (clears the stale tmp, writes the fresh content)
        sha = md_store.write("notes/n.md", "v2", "second write over a stale tmp")
        assert isinstance(sha, str) and len(sha) == 40
        assert md_store.read("notes/n.md") == "v2", "the fresh content landed"
        # the stale tmp is gone (consumed by the atomic write→rename)
        assert not stale.exists(), "the stale tmp must be cleared, not left behind"

    def test_atomicity_preserved_no_tmp_after_write(self, tmp_path):
        """After a successful write, NO .tmp lingers (the os.replace consumed it) — a concurrent
        reader of the note never sees a partial file (the rename is what's visible)."""
        md_store.write("notes/atomic.md", "final content", "atomic write")
        tmp = tmp_path / "notes" / ".atomic.md.tmp"
        assert not tmp.exists(), "no .tmp may linger after a successful atomic write"
        assert md_store.read("notes/atomic.md") == "final content"

    def test_stale_tmp_for_a_brand_new_file(self, tmp_path):
        """A stale tmp for a file that doesn't exist yet (a crashed FIRST write) → the create
        still succeeds (clears the stale tmp + creates the note)."""
        md_store.write("seed.md", "x", "seed")  # init the repo
        stale = tmp_path / "notes" / ".brand_new.md.tmp"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("stale from a crashed create")
        sha = md_store.write("notes/brand_new.md", "created", "create over stale tmp")
        assert isinstance(sha, str) and len(sha) == 40
        assert md_store.read("notes/brand_new.md") == "created"
        assert not stale.exists()
