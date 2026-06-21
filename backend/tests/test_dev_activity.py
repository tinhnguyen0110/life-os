"""tests/test_dev_activity.py — DEV-TRACING-P1 (#63) local git-scan tests.

EXERCISE the scan against a REAL temp git repo (git init + commits in the test, scan it, assert) —
NOT a field-read (behavior-test-not-field-read). Each test is a DIVERGENT distinguishing case from
the HARD GATE: identity-map (you vs other), LOC_SKIP (lockfile excluded), --no-merges, idempotent
re-scan, honest-empty-on-unconfigured-roots, TZ→VN-day. Mount-independent (the temp repo is the
scan root); the live-container curl (tester) verifies the real mount.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from modules.dev_activity import reader, service, store


def _git(repo: str, *args: str, env: dict | None = None):
    """Run a git command in `repo`, raising on failure (test setup must succeed)."""
    full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True, env=full_env)


def _commit(repo: str, *, email: str, name: str, files: dict[str, str], msg: str,
            date: str | None = None):
    """Write `files` (path→content) + commit as (name<email>). `date` (ISO) sets author+committer
    date for TZ tests. Returns nothing — exercises the real git history the scan reads."""
    for path, content in files.items():
        full = os.path.join(repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True) if os.path.dirname(path) else None
        with open(full, "w") as f:
            f.write(content)
    _git(repo, "add", "-A")
    env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
           "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    _git(repo, "commit", "-m", msg, env=env)


@pytest.fixture
def temp_repo(tmp_path, isolated_paths, monkeypatch):
    """A real git repo under a tmp scan root + DEV_TRACING_ROOTS/EMAILS pointed at it. isolated_paths
    gives a fresh dev_activity db. Returns the repo path."""
    root = tmp_path / "scan_root"
    repo = root / "myrepo"
    repo.mkdir(parents=True)
    _git(str(repo), "init", "-b", "main")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    return str(repo)


# --- identity-map: you vs other (the HARD GATE: 2 you / 1 other → commits=2 source=you) ----- #
def test_identity_map_you_vs_other(temp_repo):
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="mine 1")
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=2\ny=3\n"}, msg="mine 2")
    _commit(temp_repo, email="other@team.com", name="Teammate", files={"b.py": "z=1\n"}, msg="theirs")
    result = service.scan(days=30)
    assert result["yourCommits"] == 2  # only the 2 me@ commits count as "you"
    ov = reader.get_overview(30)
    assert ov.summary.totalCommits == 2  # your totals exclude "other"
    # the 'other' commit is STORED + surfaced separately (team context, tagged, not in your totals)
    assert any(r.source == "other" and r.commits == 1 for r in ov.otherRepos)


def test_unconfigured_emails_tags_all_other_with_warning(tmp_path, isolated_paths, monkeypatch):
    """DEV_TRACING_EMAILS unset → every commit tags 'other' + a warning (NEVER silently 'you')."""
    root = tmp_path / "r"
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(str(repo), "init", "-b", "main")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.delenv("DEV_TRACING_EMAILS", raising=False)
    store.init_dev_activity_tables()
    _commit(str(repo), email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    result = service.scan(days=30)
    assert result["yourCommits"] == 0  # nothing attributed to "you"
    assert any("DEV_TRACING_EMAILS not set" in w for w in result["warnings"])


# --- #84: DEV_TRACING_EMAILS is COMMA-separated (the "you=0" bug — was split(":")) ---------- #
def test_your_emails_comma_separated(monkeypatch):
    """#84 CORE: a comma-separated DEV_TRACING_EMAILS parses into N elements (not 1).
    DISTINGUISHING: split(":") on a comma list = 1 huge element → no match → you=0 (the bug).
    split(",") = the real set → matches → you>0."""
    monkeypatch.setenv("DEV_TRACING_EMAILS", "a@b.com,c@d.com,nick3")
    assert service.your_emails() == {"a@b.com", "c@d.com", "nick3"}  # 3 elements, lowercased


def test_your_emails_colon_in_value_is_one_element_not_split(monkeypatch):
    """REGRESSION GUARD: a value with a colon (the OLD separator) is NOT split on ':' anymore —
    a single colon-joined string is ONE element (proves we switched to comma, the real format)."""
    monkeypatch.setenv("DEV_TRACING_EMAILS", "a@b.com:c@d.com")  # old colon format = now 1 elem
    assert service.your_emails() == {"a@b.com:c@d.com"}  # NOT {a@b.com, c@d.com}


def test_your_emails_single_and_empty(monkeypatch):
    """Single email (no comma) → 1-element set; unset → empty set."""
    monkeypatch.setenv("DEV_TRACING_EMAILS", "solo@x.com")
    assert service.your_emails() == {"solo@x.com"}
    monkeypatch.delenv("DEV_TRACING_EMAILS", raising=False)
    assert service.your_emails() == set()


def test_roots_stay_colon_separated(monkeypatch):
    """#84 GUARD: ROOTS are still COLON-separated (paths) — the fix touched ONLY emails."""
    monkeypatch.setenv("DEV_TRACING_ROOTS", "/a:/b:/c")
    assert service.scan_roots() == ["/a", "/b", "/c"]  # colon split unchanged


def test_comma_emails_tag_you_end_to_end(tmp_path, isolated_paths, monkeypatch):
    """#84 e2e: a COMMA-list DEV_TRACING_EMAILS → the matching commit tags 'you' (yourCommits>0),
    proving the fix lights up the feature. With the OLD split(':') this would be 0 (the bug)."""
    root = tmp_path / "r"
    repo = root / "repo"
    repo.mkdir(parents=True)
    _git(str(repo), "init", "-b", "main")
    # a real multi-email comma list — the 2nd entry matches the commit author
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "first@x.com,me@example.com,third@y.com")
    store.init_dev_activity_tables()
    _commit(str(repo), email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="mine")
    _commit(str(repo), email="other@team.com", name="T", files={"b.py": "z=1\n"}, msg="theirs")
    result = service.scan(days=30)
    assert result["yourCommits"] == 1, "the comma-list email must match → tag 'you' (was 0 with split ':')"


# --- #85: authoritative-window delete — stale rows from an attribution change are cleared ---- #
def test_scan_clears_stale_other_row_after_attribution_flip(temp_repo, monkeypatch):
    """#85 THE TEETH: the (date,repo) had a stale 'other' row (pre-#84 artifact); a re-scan that
    re-derives it as 'you' (now that the email matches) DELETES the stale 'other' row — no orphan,
    no double-count. Revert delete_window → the stale 'other' survives (RED)."""
    import datetime
    today = datetime.date.today().strftime("%Y-%m-%d")
    repo_name = "myrepo"  # temp_repo's basename (root/myrepo)
    # SEED the stale 'other' row (simulate the pre-#84 colon-split artifact)
    store.upsert_day(date=today, repo=repo_name, source="other", commits=5, loc_added=5,
                     loc_deleted=0, first_ts="09:00", last_ts="09:00")
    # a real commit by the identity-email → re-derives as 'you'
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="mine")

    service.scan(days=30)
    rows = store.rows_since("2000-01-01")
    others = [r for r in rows if r["source"] == "other" and r["repo"] == repo_name]
    yous = [r for r in rows if r["source"] == "you" and r["repo"] == repo_name]
    assert others == [], "the stale 'other' row must be DELETED by the authoritative-window scan"
    assert yous and yous[0]["commits"] == 1, "the commit is now attributed to 'you' (real count)"


def test_scan_no_date_repo_has_both_sources(temp_repo, monkeypatch):
    """#85: after a scan, no (date,repo) pair carries BOTH 'you' AND 'other' from a single
    identity's commits (the double-count signature). Here all commits are mine → only 'you'."""
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=2\n"}, msg="c2")
    service.scan(days=30)
    rows = store.rows_since("2000-01-01")
    by_date_repo: dict = {}
    for r in rows:
        by_date_repo.setdefault((r["date"], r["repo"]), set()).add(r["source"])
    both = {k: v for k, v in by_date_repo.items() if v == {"you", "other"}}
    assert not both, f"no (date,repo) should have BOTH sources for a single-identity repo: {both}"


def test_delete_window_scoped_does_not_wipe_unscanned_repos(isolated_paths):
    """#85 SCOPED-DELETE SAFETY (snapshot-wipe guard): delete_window only touches the named repos
    + date-window. A row for a DIFFERENT repo (not in the scanned set) SURVIVES."""
    store.init_dev_activity_tables()
    store.upsert_day(date="2026-06-20", repo="scanned-repo", source="other", commits=3,
                     loc_added=3, loc_deleted=0, first_ts="09:00", last_ts="10:00")
    store.upsert_day(date="2026-06-20", repo="OTHER-repo", source="you", commits=2,
                     loc_added=2, loc_deleted=0, first_ts="09:00", last_ts="10:00")
    deleted = store.delete_window("2026-06-01", {"scanned-repo"})
    assert deleted == 1
    survivors = {(r["repo"], r["source"]) for r in store.rows_since("2000-01-01")}
    assert survivors == {("OTHER-repo", "you")}, "only the scanned repo's rows deleted; others survive"


def test_delete_window_empty_repos_deletes_nothing(isolated_paths):
    """#85 SCOPED-DELETE SAFETY: an EMPTY scanned set (0-commit / unreachable-root scan) deletes
    NOTHING — never a blanket wipe of the whole store."""
    store.init_dev_activity_tables()
    store.upsert_day(date="2026-06-20", repo="r", source="you", commits=1, loc_added=1,
                     loc_deleted=0, first_ts="09:00", last_ts="10:00")
    deleted = store.delete_window("2026-06-01", set())
    assert deleted == 0
    assert len(store.rows_since("2000-01-01")) == 1, "an empty-set delete must NOT wipe rows"


def test_scan_unreachable_root_does_not_wipe_existing(tmp_path, isolated_paths, monkeypatch):
    """#85 SCOPED-DELETE SAFETY e2e: a scan whose root is unreachable (nothing scanned) must NOT
    delete pre-existing rows — scanned_repos is empty → delete_window is a no-op."""
    store.init_dev_activity_tables()
    store.upsert_day(date="2026-06-20", repo="old-repo", source="you", commits=9, loc_added=9,
                     loc_deleted=0, first_ts="09:00", last_ts="10:00")
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    service.scan(days=30)
    rows = store.rows_since("2000-01-01")
    assert any(r["repo"] == "old-repo" and r["commits"] == 9 for r in rows), \
        "an unreachable-root scan must NOT wipe pre-existing rows (snapshot-wipe guard)"


def test_replace_window_atomic_rollback_leaves_store_untouched(isolated_paths):
    """#85 shape-(a) ATOMICITY (the #72-level guard): if the upsert phase RAISES mid-replace, the
    WHOLE transaction ROLLS BACK — the pre-existing rows are UNTOUCHED (never wiped-not-refilled).
    Feed a malformed aggregate (missing key) → KeyError mid-loop → assert the old rows survive."""
    store.init_dev_activity_tables()
    store.upsert_day(date="2026-06-20", repo="r1", source="you", commits=7, loc_added=7,
                     loc_deleted=0, first_ts="09:00", last_ts="10:00")
    bad_aggregates = [{"date": "2026-06-21", "repo": "r1", "source": "you"}]  # missing commits/loc → KeyError
    import pytest as _pt
    with _pt.raises(KeyError):
        store.replace_window("2026-06-01", {"r1"}, bad_aggregates)
    # the DELETE was in the same txn as the failing upsert → rolled back → r1's old row SURVIVES
    rows = store.rows_since("2000-01-01")
    assert any(r["repo"] == "r1" and r["commits"] == 7 for r in rows), \
        "a failed replace must roll back the delete — the store stays untouched (no wipe)"


def test_replace_window_empty_repos_deletes_nothing_but_upserts(isolated_paths):
    """#85 shape-(a): empty scanned set → NO delete (no wipe), but the aggregates still upsert."""
    store.init_dev_activity_tables()
    store.upsert_day(date="2026-06-20", repo="keep", source="you", commits=1, loc_added=1,
                     loc_deleted=0, first_ts="09:00", last_ts="10:00")
    store.replace_window("2026-06-01", set(), [])  # nothing scanned, nothing to write
    assert len(store.rows_since("2000-01-01")) == 1, "empty-repo replace must NOT wipe existing rows"


def test_replace_window_clears_stale_then_writes_fresh(isolated_paths):
    """#85 shape-(a) happy path: a stale 'other' row for (date,repo) + a fresh 'you' aggregate for
    the same (date,repo) → after replace, ONLY the fresh 'you' row remains (atomic delete+upsert)."""
    store.init_dev_activity_tables()
    store.upsert_day(date="2026-06-21", repo="repoA", source="other", commits=9, loc_added=9,
                     loc_deleted=0, first_ts="08:00", last_ts="08:30")
    fresh = [{"date": "2026-06-21", "repo": "repoA", "source": "you", "commits": 3,
              "loc_added": 3, "loc_deleted": 0, "first_ts": "09:00", "last_ts": "09:30"}]
    store.replace_window("2026-06-01", {"repoA"}, fresh)
    rows = {(r["repo"], r["source"], r["commits"]) for r in store.rows_since("2000-01-01")}
    assert rows == {("repoA", "you", 3)}, "stale 'other' cleared; only the fresh 'you' row remains"


def test_scan_idempotent_no_double_count_on_rescan(temp_repo):
    """#85: scanning the SAME repo twice → counts UNCHANGED (the authoritative delete+upsert is
    idempotent — the 2nd scan re-derives + replaces, never accumulates)."""
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    r1 = service.scan(days=30)
    r2 = service.scan(days=30)
    assert r1["yourCommits"] == r2["yourCommits"] == 1, "re-scan must not double-count"


# --- LOC_SKIP: a lockfile + a real file → LOC counts ONLY the real file --------------------- #
def test_loc_skip_excludes_lockfile(temp_repo):
    _commit(temp_repo, email="me@example.com", name="Me",
            files={"package-lock.json": "{\n" + "\n".join(f'"k{i}":{i},' for i in range(50)) + "\n}\n",
                   "real.py": "a=1\nb=2\nc=3\n"},
            msg="lock + real")
    service.scan(days=30)
    ov = reader.get_overview(30)
    me = [r for r in ov.byRepo if r.repo == "myrepo"][0]
    # only real.py's 3 lines counted; the 50-line lockfile is LOC_SKIP-excluded
    assert me.locAdded == 3, f"LOC must exclude the lockfile, got {me.locAdded}"


def test_binary_numstat_is_zero_not_crash(temp_repo):
    """A binary file (numstat '-\t-') → 0 LOC, no crash (the validate guard)."""
    with open(os.path.join(temp_repo, "img.bin"), "wb") as f:
        f.write(bytes(range(256)) * 4)  # binary content
    _git(temp_repo, "add", "-A")
    _git(temp_repo, "commit", "-m", "binary",
         env={"GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "me@example.com",
              "GIT_COMMITTER_NAME": "Me", "GIT_COMMITTER_EMAIL": "me@example.com"})
    service.scan(days=30)
    ov = reader.get_overview(30)  # must not raise on the binary numstat
    me = [r for r in ov.byRepo if r.repo == "myrepo"][0]
    assert me.commits == 1 and me.locAdded == 0


# --- --no-merges: a merge commit is excluded ------------------------------------------------ #
def test_merge_commit_excluded(temp_repo):
    e = {"GIT_AUTHOR_NAME": "Me", "GIT_AUTHOR_EMAIL": "me@example.com",
         "GIT_COMMITTER_NAME": "Me", "GIT_COMMITTER_EMAIL": "me@example.com"}
    _commit(temp_repo, email="me@example.com", name="Me", files={"base.py": "x=1\n"}, msg="base")
    _git(temp_repo, "checkout", "-b", "feature")
    _commit(temp_repo, email="me@example.com", name="Me", files={"feat.py": "y=1\n"}, msg="feat")
    _git(temp_repo, "checkout", "main")
    _commit(temp_repo, email="me@example.com", name="Me", files={"main2.py": "z=1\n"}, msg="main work")
    _git(temp_repo, "merge", "--no-ff", "feature", "-m", "MERGE feature", env=e)
    service.scan(days=30)
    ov = reader.get_overview(30)
    me = [r for r in ov.byRepo if r.repo == "myrepo"][0]
    # base + feat + main work = 3 real commits; the MERGE is excluded by --no-merges
    assert me.commits == 3, f"merge must be excluded, got {me.commits}"


# --- idempotent re-scan (no double-count — upsert per date×repo×source) --------------------- #
def test_rescan_idempotent(temp_repo):
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\ny=2\n"}, msg="c1")
    service.scan(days=30)
    first = reader.get_overview(30).summary.totalCommits
    service.scan(days=30)  # re-scan
    second = reader.get_overview(30).summary.totalCommits
    assert first == second == 1, f"re-scan must be idempotent, got {first} then {second}"


# --- honest-empty + warnings (roots unconfigured / unreachable) ----------------------------- #
def test_no_roots_honest_empty_with_warning(isolated_paths, monkeypatch):
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)
    store.init_dev_activity_tables()
    result = service.scan(days=30)
    assert result["scannedRepos"] == 0 and result["rowsUpserted"] == 0
    assert any("DEV_TRACING_ROOTS not set" in w for w in result["warnings"])
    ov = reader.get_overview(30)
    assert ov.byDay == [] and ov.summary.totalCommits == 0
    assert ov.warnings  # honest: warns, NOT silent-zero


def test_unreachable_root_warns_not_crash(isolated_paths, monkeypatch, tmp_path):
    """A configured root that doesn't exist (e.g. unmounted) → warning + honest-empty, no crash."""
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    result = service.scan(days=30)
    assert result["scannedRepos"] == 0
    assert any("unreachable" in w for w in result["warnings"])


def test_non_git_dir_skipped(isolated_paths, monkeypatch, tmp_path):
    """A root that exists but has no .git (and no child repos) → 0 scanned, no crash."""
    root = tmp_path / "plain"
    (root / "subdir").mkdir(parents=True)
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    result = service.scan(days=30)
    assert result["scannedRepos"] == 0 and result["rowsUpserted"] == 0


# --- TZ → VN day (the vn_day_of helper) ----------------------------------------------------- #
def test_tz_vn_day_bucketing():
    # 23:30 +07:00 → that VN day; 23:30 Z (UTC) → next VN day (06:30 VN next day)
    assert service._vn_day("2026-06-21T23:30:00+07:00") == "2026-06-21"
    assert service._vn_day("2026-06-21T23:30:00+00:00") == "2026-06-22"


def test_active_span_format():
    assert service._span("08:00", "10:30") == "2h 30m"
    assert service._span("09:00", "09:00") == ""   # single commit → no span
    assert service._span(None, None) == ""


# --- registry auto-discovery (no core edit) ------------------------------------------------- #
def test_module_registered():
    from modules.dev_activity.router import MODULE
    assert MODULE.name == "dev_activity"
    assert any(r.id == "dev-activity-scan" for r in MODULE.routines())


# --- the MCP dev_activity tool == REST (byte-identical, #24) --------------------------------- #
def test_mcp_dev_activity_byte_identical_to_reader(temp_repo):
    import json
    import mcp_servers.read_server as rs
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    service.scan(days=30)
    mcp = rs.dev_activity(90)
    rest = reader.get_overview(90).model_dump()
    assert json.dumps(mcp, sort_keys=True) == json.dumps(rest, sort_keys=True)


# =========================================================================== #
# DEV-TRACING-P2 (#63) — REMOTE (GitHub + Bitbucket) + dedup-by-sha. HTTP is     #
# MOCKED (monkeypatch service._http_get_json) — NO live network in the suite.    #
# =========================================================================== #
def _gh_repos_response(*full_names):
    return [{"full_name": fn, "name": fn.split("/")[-1], "owner": {"login": "me"}} for fn in full_names]


def _gh_commit(sha, *, email, date_iso):
    return {"sha": sha, "commit": {"committer": {"date": date_iso},
                                   "author": {"email": email, "date": date_iso}}}


@pytest.fixture
def remote_env(isolated_paths, monkeypatch):
    """GitHub cred set + NO local roots (isolate the remote path). dev_activity db fresh."""
    monkeypatch.setenv("GITHUB_PAT", "ghp_faketoken")
    monkeypatch.setenv("GITHUB_USER", "me")
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)  # remote-only for these tests
    monkeypatch.delenv("BITBUCKET_HOST", raising=False)
    store.init_dev_activity_tables()
    return isolated_paths


def _mock_github(monkeypatch, *, repos, commits_by_repo, detail_by_sha=None):
    """Wire service._http_get_json to serve canned GitHub responses by URL (no network)."""
    detail_by_sha = detail_by_sha or {}

    def fake(url, headers, timeout=20):
        if "/user/repos" in url:
            return repos
        if "/commits/" in url:  # per-commit detail (LOC)
            sha = url.rsplit("/", 1)[-1]
            return detail_by_sha.get(sha, {"files": []})
        if "/commits?" in url:
            full = url.split("/repos/", 1)[1].split("/commits", 1)[0]
            return commits_by_repo.get(full, [])
        return []
    monkeypatch.setattr(service, "_http_get_json", fake)


def test_remote_github_commits_counted(remote_env, monkeypatch):
    """A GitHub repo with the user's commits → counted (source=you via email identity-map)."""
    _mock_github(monkeypatch,
                 repos=_gh_repos_response("me/proj"),
                 commits_by_repo={"me/proj": [
                     _gh_commit("sha1", email="me@example.com", date_iso="2026-06-21T08:00:00Z"),
                     _gh_commit("sha2", email="me@example.com", date_iso="2026-06-21T09:00:00Z")]})
    result = service.scan(days=365)
    assert result["yourCommits"] == 2
    ov = reader.get_overview(365)
    assert ov.summary.totalCommits == 2 and "proj" in ov.summary.topRepos


def test_dedup_sha_local_and_remote_counts_once(tmp_path, isolated_paths, monkeypatch):
    """THE P2 INVARIANT: a commit present in BOTH the local scan AND the GitHub response (same sha)
    is counted ONCE, not doubled. Seed a local repo, capture its real sha, return it from GitHub."""
    root = tmp_path / "root"
    repo = root / "shared"
    repo.mkdir(parents=True)
    _git(str(repo), "init", "-b", "main")
    _commit(str(repo), email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="shared commit")
    real_sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    cdate = subprocess.run(["git", "-C", str(repo), "show", "-s", "--format=%cI", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    monkeypatch.setenv("GITHUB_PAT", "ghp_fake"); monkeypatch.setenv("GITHUB_USER", "me")
    monkeypatch.delenv("BITBUCKET_HOST", raising=False)
    store.init_dev_activity_tables()
    # GitHub returns the SAME commit (same real sha) — must be deduped.
    _mock_github(monkeypatch, repos=_gh_repos_response("me/shared"),
                 commits_by_repo={"me/shared": [_gh_commit(real_sha, email="me@example.com", date_iso=cdate)]})
    result = service.scan(days=365)
    assert result["yourCommits"] == 1, f"local⊕remote same sha must count ONCE, got {result['yourCommits']}"


def test_dedup_different_sha_counts_two(remote_env, monkeypatch):
    """Two DIFFERENT shas (one local-absent, both from GitHub) → 2 (dedup only collapses same sha)."""
    _mock_github(monkeypatch, repos=_gh_repos_response("me/proj"),
                 commits_by_repo={"me/proj": [
                     _gh_commit("shaA", email="me@example.com", date_iso="2026-06-21T08:00:00Z"),
                     _gh_commit("shaB", email="me@example.com", date_iso="2026-06-21T09:00:00Z")]})
    assert service.scan(days=365)["yourCommits"] == 2


def test_github_unset_skips_with_warning(isolated_paths, monkeypatch):
    """GITHUB_PAT unset → GitHub skipped + honest warning; the scan still completes (local-only)."""
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.delenv("DEV_TRACING_ROOTS", raising=False)
    monkeypatch.delenv("BITBUCKET_HOST", raising=False)
    store.init_dev_activity_tables()
    result = service.scan(days=365)
    assert any("GITHUB_PAT" in w for w in result["warnings"])
    assert result["yourCommits"] == 0  # no crash, honest-empty


def test_github_rate_limit_403_honest_warning_no_crash(remote_env, monkeypatch):
    """A GitHub 403/rate-limit → honest warning + source skipped, NOT a crash, NOT fabricated data."""
    import urllib.error

    def boom(url, headers, timeout=20):
        raise urllib.error.HTTPError(url, 403, "rate limited", {}, None)  # type: ignore[arg-type]
    monkeypatch.setattr(service, "_http_get_json", boom)
    result = service.scan(days=365)  # must not raise
    assert any("github" in w.lower() and "403" in w for w in result["warnings"])
    assert result["yourCommits"] == 0


def test_remote_tz_normalized_to_vn_day(remote_env, monkeypatch):
    """A remote commit at 23:30Z → the NEXT VN day (UTC+7). The remote date is VN-normalized."""
    _mock_github(monkeypatch, repos=_gh_repos_response("me/proj"),
                 commits_by_repo={"me/proj": [
                     _gh_commit("shaZ", email="me@example.com", date_iso="2026-06-21T23:30:00Z")]})
    service.scan(days=365)
    ov = reader.get_overview(365)
    # 23:30Z = 06:30 VN next day → bucketed to 2026-06-22
    assert any(d.date == "2026-06-22" for d in ov.byDay), [d.date for d in ov.byDay]


def test_no_cred_leak_in_output(remote_env, monkeypatch):
    """The scan result + overview must NEVER contain the token/cred value (no-cred-leak)."""
    _mock_github(monkeypatch, repos=_gh_repos_response("me/proj"),
                 commits_by_repo={"me/proj": [_gh_commit("s1", email="me@example.com", date_iso="2026-06-21T08:00:00Z")]})
    result = service.scan(days=365)
    blob = json.dumps(result) + json.dumps(reader.get_overview(365).model_dump())
    assert "ghp_faketoken" not in blob and "ghp_fake" not in blob, "cred leaked into output!"


def test_github_loc_skip_applied_remote(remote_env, monkeypatch):
    """Remote LOC honors LOC_SKIP: a commit detail with a lockfile + a real file → only the real LOC."""
    _mock_github(monkeypatch, repos=_gh_repos_response("me/proj"),
                 commits_by_repo={"me/proj": [_gh_commit("s1", email="me@example.com", date_iso="2026-06-21T08:00:00Z")]},
                 detail_by_sha={"s1": {"files": [
                     {"filename": "package-lock.json", "additions": 500, "deletions": 0},
                     {"filename": "real.py", "additions": 7, "deletions": 2}]}})
    service.scan(days=365)
    ov = reader.get_overview(365)
    proj = [r for r in ov.byRepo if r.repo == "proj"][0]
    assert proj.locAdded == 7 and proj.locDeleted == 2  # lockfile excluded


# =========================================================================== #
# DEV-ACTIVITY-STORE (#77) — GET reads the STORE (fast), the SCAN is the write   #
# path. lastScanned (honest freshness) + no-scan-yet warning + the no-scan-on-    #
# read regression pin (the GET must NEVER trigger a 24s git scan).               #
# =========================================================================== #
def test_get_reads_store_does_NOT_scan(temp_repo, monkeypatch):
    """THE #77 INVARIANT (regression pin): get_overview reads the STORE and NEVER calls scan() / git.
    Seed via one scan, then poison service.scan + _scan_repo so a read that re-scans would BLOW UP —
    the GET must still succeed (proving it's a pure store-read, the fast agent surface)."""
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    service.scan(days=30)  # the WRITE path populates the store
    # now make ANY scan attempt during a read explode:
    monkeypatch.setattr(service, "scan", lambda *a, **k: (_ for _ in ()).throw(AssertionError("GET re-scanned!")))
    monkeypatch.setattr(service, "_scan_repo", lambda *a, **k: (_ for _ in ()).throw(AssertionError("GET ran git!")))
    ov = reader.get_overview(30)  # must NOT raise → it reads the store, not a re-scan
    assert ov.summary.totalCommits == 1  # served from the stored row


def test_last_scanned_surfaced_after_scan(temp_repo):
    """lastScanned is None before any scan, set (ISO) after — honest freshness for the agent/UI."""
    before = reader.get_overview(30)
    assert before.lastScanned is None
    service.scan(days=30)
    after = reader.get_overview(30)
    assert after.lastScanned is not None and "T" in after.lastScanned  # an ISO timestamp


def test_never_scanned_honest_empty_warning(isolated_paths, monkeypatch, tmp_path):
    """Store empty + roots CONFIGURED but never scanned → honest-empty + a 'no scan yet' warning
    (distinct from 'roots not set'), NOT an auto-scan-on-read."""
    root = tmp_path / "root"
    (root / "somerepo").mkdir(parents=True)  # a dir exists so roots are 'configured/reachable'
    monkeypatch.setenv("DEV_TRACING_ROOTS", str(root))
    monkeypatch.setenv("DEV_TRACING_EMAILS", "me@example.com")
    store.init_dev_activity_tables()
    ov = reader.get_overview(30)
    assert ov.byDay == [] and ov.summary.totalCommits == 0  # honest-empty
    assert ov.lastScanned is None
    assert any("no scan yet" in w for w in ov.warnings), ov.warnings


def test_scanned_empty_is_not_never_scanned(temp_repo, monkeypatch):
    """A scan that RAN but found nothing in the window → lastScanned SET + NO 'no scan yet' warning
    (the distinguishing: 'scanned, empty' ≠ 'never scanned')."""
    # no commits in the repo → scan runs, finds 0, but stamps last_scanned
    service.scan(days=30)
    ov = reader.get_overview(30)
    assert ov.lastScanned is not None
    assert not any("no scan yet" in w for w in ov.warnings)


def test_mcp_dev_activity_includes_lastScanned(temp_repo):
    """MCP dev_activity ≡ REST (#24) — both store-read, both carry lastScanned (byte-identical)."""
    import mcp_servers.read_server as rs
    _commit(temp_repo, email="me@example.com", name="Me", files={"a.py": "x=1\n"}, msg="c1")
    service.scan(days=30)
    mcp = rs.dev_activity(90)
    rest = reader.get_overview(90).model_dump()
    assert "lastScanned" in mcp and mcp["lastScanned"] is not None
    assert json.dumps(mcp, sort_keys=True) == json.dumps(rest, sort_keys=True)
