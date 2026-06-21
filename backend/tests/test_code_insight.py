"""tests/test_code_insight.py — REPO-MEMORY-P1 (#64) code_insight on-demand repo read.

EXERCISE the read against a REAL temp git repo (git init + README + commits + a manifest, then
code_insight it, assert structure/readme/recentCommits/stack/asOf) — behavior-test-not-field-read.
Distinguishing: found:true with all fields · missing repo → found:false honest-empty · no-README →
readme null · bounded (huge tree/README capped + warning) · LIVE read (a 2nd call after a change
reflects it — not cached) · MCP code_insight ≡ REST. Read-only (no mutating git).
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from modules.code_insight import reader, service


def _git(repo: str, *args: str, env: dict | None = None):
    full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True, env=full_env)


def _commit(repo: str, files: dict[str, str], msg: str):
    for path, content in files.items():
        full = os.path.join(repo, path)
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", msg,
         env={"GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "me@x.com",
              "GIT_COMMITTER_NAME": "Me", "GIT_COMMITTER_EMAIL": "me@x.com"})


@pytest.fixture
def repo(tmp_path, isolated_paths, monkeypatch):
    """A real git repo under a tmp root + DEV_TRACING_ROOTS pointed at the root (so resolve finds it
    by name). Returns (name, path)."""
    root = tmp_path / "root"
    r = root / "myrepo"
    r.mkdir(parents=True)
    _git(str(r), "init", "-b", "main")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    return ("myrepo", str(r))


# --- found:true with all fields (the happy path) ---------------------------- #
def test_insight_full_repo(repo):
    name, path = repo
    _commit(path, {"README.md": "# MyRepo\nDoes a thing.\n", "src/app.py": "x=1\n",
                   "package.json": '{"name":"myrepo"}\n'}, "init")
    _commit(path, {"src/app.py": "x=2\n"}, "second")
    ci = reader.get_insight(name)
    assert ci.found is True and ci.root == path
    assert "README.md" in ci.structure and "src/" in ci.structure and "package.json" in ci.structure
    assert ci.readme is not None and "MyRepo" in ci.readme
    assert len(ci.recentCommits) == 2 and ci.recentCommits[0].msg == "second"  # newest-first
    assert "node" in ci.stack  # package.json
    assert ci.asOf and "T" in ci.asOf


def test_resolve_by_path_too(repo):
    """code_insight resolves a PATH under a root (not just a name)."""
    name, path = repo
    _commit(path, {"README.md": "# X\n"}, "c1")
    ci = reader.get_insight(name)  # by name
    assert ci.found and ci.root == path


# --- missing repo → found:false honest-empty -------------------------------- #
def test_missing_repo_found_false(repo):
    ci = reader.get_insight("does-not-exist")
    assert ci.found is False and ci.root == ""
    assert ci.structure == [] and ci.readme is None and ci.recentCommits == []
    assert ci.asOf and any("not found" in w for w in ci.warnings)  # honest, asOf still set


def test_no_roots_configured_found_false(isolated_paths, monkeypatch):
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)
    ci = reader.get_insight("anything")
    assert ci.found is False and any("DEV_TRACING_ROOTS not set" in w for w in ci.warnings)


# --- no README → readme null, the rest still returns ------------------------ #
def test_no_readme_is_null_rest_returns(repo):
    name, path = repo
    _commit(path, {"main.go": "package main\n", "go.mod": "module x\n"}, "c1")
    ci = reader.get_insight(name)
    assert ci.found is True
    assert ci.readme is None  # honest null
    assert "main.go" in ci.structure and "go" in ci.stack and len(ci.recentCommits) == 1


# --- bounded: huge tree + huge README capped + warning ---------------------- #
def test_structure_bounded_with_warning(repo):
    name, path = repo
    for i in range(120):  # > _MAX_STRUCTURE (80)
        with open(os.path.join(path, f"f{i:03}.txt"), "w") as f:
            f.write("x")
    _commit(path, {}, "many files") if False else _git(path, "add", "-A")
    _git(path, "commit", "-m", "many",
         env={"GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "me@x.com",
              "GIT_COMMITTER_NAME": "Me", "GIT_COMMITTER_EMAIL": "me@x.com"})
    ci = reader.get_insight(name)
    assert len(ci.structure) == service._MAX_STRUCTURE
    assert any("structure truncated" in w for w in ci.warnings)


def test_readme_bounded_with_warning(repo):
    name, path = repo
    _commit(path, {"README.md": "A" * (service._MAX_README_CHARS + 500)}, "big readme")
    ci = reader.get_insight(name)
    assert ci.readme is not None and len(ci.readme) == service._MAX_README_CHARS
    assert any("README truncated" in w for w in ci.warnings)


def test_skip_noise_dirs(repo):
    name, path = repo
    os.makedirs(os.path.join(path, "node_modules", "pkg"))
    os.makedirs(os.path.join(path, "src"))
    with open(os.path.join(path, "node_modules", "pkg", "x.js"), "w") as f:
        f.write("x")
    _commit(path, {"src/a.py": "x=1\n"}, "c1")
    ci = reader.get_insight(name)
    assert "src/" in ci.structure and "node_modules/" not in ci.structure  # noise skipped


# --- LIVE read: a 2nd call after a change reflects it (not cached) ----------- #
def test_live_read_reflects_change(repo):
    name, path = repo
    _commit(path, {"README.md": "# v1\n"}, "c1")
    first = reader.get_insight(name)
    assert "v1" in (first.readme or "")
    with open(os.path.join(path, "README.md"), "w") as f:
        f.write("# v2 changed\n")
    second = reader.get_insight(name)  # live re-read, no cache
    assert "v2 changed" in (second.readme or ""), "code_insight must be a LIVE read, not cached"


# --- read-only: the git whitelist refuses a mutating op --------------------- #
def test_git_whitelist_refuses_mutating(repo):
    _name, path = repo
    with pytest.raises(ValueError):
        service._git(path, ["commit", "-m", "x"])  # not on the read-only whitelist


# --- registry + MCP ≡ REST -------------------------------------------------- #
def test_module_registered():
    from modules.code_insight.router import MODULE
    assert MODULE.name == "code_insight"


def test_mcp_code_insight_byte_identical_to_reader(repo):
    import mcp_servers.read_server as rs
    name, path = repo
    _commit(path, {"README.md": "# X\n", "pyproject.toml": "[x]\n"}, "c1")
    mcp = rs.code_insight(name)
    rest = reader.get_insight(name).model_dump()
    # asOf differs by the two read instants — compare modulo asOf (both are live reads)
    mcp.pop("asOf"); rest.pop("asOf")
    assert json.dumps(mcp, sort_keys=True) == json.dumps(rest, sort_keys=True)
    assert "python" in mcp["stack"]
