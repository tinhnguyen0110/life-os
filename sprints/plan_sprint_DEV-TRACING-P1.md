# Sprint DEV-TRACING-P1 — local-scan dev-activity (Cairn #63 Phase 1 of 3)

> Kickoff'd 2026-06-21 by architect (§3.3a). #63 = dev-activity tracing FROM git (per date×repo: commits/LOC/active-span). P1 = LOCAL-SCAN (no-cred — proves value before the remote complexity). admin-lead VALIDATED feasibility (validate_dev_tracing.py ran 6 days correct + 9 traps documented). team-lead greenlit (priority: #72-BE → #63 → #73 → #64). backend BUILDS; architect commits (§3).

## Kickoff — 2026-06-21
### Spot-checks done
- Read the breakdown (plan_sprint_FEATURE-DIRECTIONS-BREAKDOWN.md): #63 = 3 phases, theme-sibling of #65 (auto-dev vs manual-habit).
- Read the reference `/home/watercry/Disk_C/Data/Tinhdev/validate_dev_tracing.py`: the PROVEN approach — multi-root `git log`, LOC_SKIP filter (lock/generated/vendor/min/images → no fake +5000 LOC), identity-map (GITHUB_USER filter), TZ-VN, env-cred (P2 only). P1 = the LOCAL subset (the `--local` path + multi-root scan, NO cred).
- Existing module pattern: modules/<name>/{router,schema,service,reader,store}.py + MODULE=BaseModule (registry auto-discover, NO core/main.py edit). store = SQLite for time-series (mirror tracing/reminders — dev_activity is time-series per date×repo).
- Repo inventory: memory `trackable-repos-inventory` lists real git repos under ~/Disk_C/Data/Tinhdev/ (the scan roots). Host-dir source MUST be mounted into the container (memory `host-file-source-must-mount`) — the scan roots + git need to be reachable from :8686, or P1 fail-opens to empty. ⚠️ This is the #1 P1 infra risk — flag at dispatch.

### Decisions (decide-and-log — team-lead-confirmed defaults)
- **team-AI-commits vs hand-typed = 2 SEPARATE honest fields** (count together in totals but TAG source) — not merged, not dropped. (admin-lead + team-lead lean.)
- **LOC = informational, NOT a target** (Goodhart) — surface commits + active-span + by-repo distribution as the PRIMARY signals; LOC is a secondary informational field with the LOC_SKIP filter applied. Never rank/score on LOC.
- **backfill 90d** for P1 (the local scan is cheap; P2 extends to 1yr with remote).
- **identity-map** = a configurable email→you set (P1: a simple list of the user's git emails; default from `git config user.email` + the known set). Commits NOT matching = excluded (or tagged "other").

## Context
P1 proves the value locally with ZERO credentials: scan the local git repos under the configured roots, attribute commits to the user by email, count commits + LOC(filtered) + active-span per (date × repo), store in a dev_activity SQLite table, expose via REST + MCP. The user + agent can immediately see "what did I code, which project, when" for the local repos. P2 adds remote (GitHub/Bitbucket) for repos not cloned locally + unpushed-vs-pushed; P3 adds the FE /activity screen + brief-wire.

## Scope
IN: NEW `backend/modules/dev_activity/` (store.py SQLite + service.py git-scan+derive + reader.py + schema.py + router.py MODULE=BaseModule) + a scan routine (APScheduler daily, like the other routines) + `tests/test_dev_activity.py` + the MCP `dev_activity` read tool (read_server + optionally a per-domain later). Mount config for the scan roots (env DEV_TRACING_ROOTS, default the trackable-repos set).
OUT: P2 (remote GitHub/Bitbucket API + dedup-SHA + cred). P3 (FE /activity + brief-wire). NO cred/network in P1 (local git only).

## Logic/Algorithm (local-scan — port the validate script's PROVEN logic, zero invention)
1. **Roots:** `DEV_TRACING_ROOTS` env (colon-sep paths; default = the trackable repos under ~/Disk_C/Data/Tinhdev/). For each root, find git repos (the root itself if it has .git, or 1-level children with .git). MUST be mounted :ro into the container (the host-file-source-must-mount lesson — verify on the CONTAINER, not bare-metal).
2. **Identity-map:** `DEV_TRACING_EMAILS` env (colon-sep) = the user's git emails. Default = a sensible set (configurable). A commit's author-email ∈ the set → "you"; else → tagged "other" (NOT counted in the user's totals, but stored with a source tag so P2/UI can show team context).
3. **Scan per repo** (`git log` — port the validate script): `git log --no-merges --all --since=<90d> --pretty=...` capturing per-commit: sha (for P2 dedup), author-email, author-date (→ TZ-VN normalized day), and `--numstat` for LOC (added/deleted).
   - **LOC_SKIP filter** (the validate script's LOC_SKIP tuple): skip lock/generated/vendor/dist/build/min/node_modules/images → no fake +5000 LOC. Apply per-file before summing.
   - `--no-merges` (merge commits aren't dev-work). dedup by sha within a repo (P2 dedups ACROSS remotes; P1 single-source so per-repo sha is enough).
4. **Aggregate per (date-VN × repo):** `{date, repo, commits, locAdded, locDeleted, firstTs, lastTs, activeSpan (lastTs−firstTs "Hh Mm"), source: "you"|"other"}`. TZ: author-date → VN day (UTC+7, mirror the tracing vn_day_of helper — reuse the pattern).
5. **Store:** a `dev_activity` SQLite table (date, repo, source, commits, loc_added, loc_deleted, first_ts, last_ts), upsert per (date,repo,source) on re-scan (idempotent). index(date, repo).
6. **Derive (reader/service):** an overview `{rangeDays, byDay: [{date, repos:[{repo, commits, loc±, activeSpan, source}], totalCommits, activeRepos}], byRepo: [{repo, commits, lastActive, ...}], summary: {totalCommits, activeDays, topRepos, ...}}`. LOC surfaced as informational (NOT a score). honest-empty: no repos/commits → []+0.
7. **Scan routine:** APScheduler daily job (`dev-activity-scan`) re-scans the roots → upserts. Manual trigger via POST /dev_activity/scan (re-scan now). Idempotent.
8. **MCP:** `dev_activity()` read tool on read_server (reference-import the reader, is-identity) — agent reads "my dev activity". (A per-domain server is a later option, not P1.)

## REST / agent-readable (agent-first)
- GET /dev_activity → the overview (lean, agent-readable: each field self-describing, LOC tagged informational, source tagged). honest-empty. The MCP dev_activity == GET /dev_activity (REST≡MCP, #24).
- POST /dev_activity/scan → trigger a re-scan (returns {scanned: N repos, days, commits}).

## Defensive cases (the 9 traps — P1-relevant subset)
- a root with no .git / not a dir → skip (don't crash). a repo with 0 commits in range → omit (honest-empty).
- `git log` fails (not a repo, permission) → log + skip that repo, continue (fail-soft per repo, never abort the scan).
- LOC binary files (`-`/`-` in numstat) → treat as 0 LOC (not a crash on int()).
- TZ: author-date in any offset → normalize to VN day (the tracing vn_day_of pattern).
- container can't see the roots (not mounted) → honest-empty + a warning (NOT a crash, NOT silent) — the host-file-source-must-mount lesson; surface "roots not reachable" so it's not misread as "no activity".
- identity-map empty/unconfigured → default to `git config user.email` per repo OR tag all as "other" with a warning (don't silently count everything as "you").

## HARD GATE (distinguishing)
- a local repo with 3 commits today (2 yours, 1 other) → byDay[today][repo] commits=2 source=you (+ the other tagged separately), LOC filtered (a lockfile-only commit → 0 LOC).
- a commit touching package-lock.json + 1 real file → LOC counts ONLY the real file (LOC_SKIP applied).
- merge commit → excluded (--no-merges).
- re-scan (run twice) → idempotent (no double-count — upsert per date×repo×source).
- roots unmounted/unreachable → honest-empty + warning (not crash, not silent-zero).
- TZ: a commit at 23:30+07:00 → today-VN; 23:30Z → next VN day.
- pytest inclusive 0-failed; mypy clean; registry auto-discovered (no core edit).

## Baseline
pytest INCLUSIVE 2018/0/0. Keep 0-failed. Default `-m 'not slow'`; gate `-m ""`.

## Runtime / infra (mount AUTHORIZED — in-scope for P1, team-lead 2026-06-21)
BE container :8686. The scan roots MUST be mounted :ro into the container + `DEV_TRACING_ROOTS` env-pointed, or the scan fail-opens to empty (host-file-source-must-mount — 3rd instance). **team-lead AUTHORIZED the mount as PART of P1** (reversible read-only mount of user-owned repos, localhost single-user, consistent with the user-CHỐT "count company repos, life-os stays LOCAL" — it's data-access not a credential; secrets stay user-only per #50). So P1 SHIPS:
- docker-compose.yml `:ro` bind-mounts of the dev tree (~/Disk_C/Data/Tinhdev/ + company roots /Data/PSA, /Data/inmobi per the validate script's ENV_INMOBI) + `DEV_TRACING_ROOTS` env (`${VAR:-<container default>}`, NOT `~`).
- compose change ⇒ `docker compose up -d --build`/re-up (NOT hot-reload) → verify on the CONTAINER (curl /dev_activity = real local data; bare-metal-green ≠ container-correct).
- backend REPORTS the EXACT mounted root paths in the P1 DONE → team-lead surfaces to the user for transparency (async, non-blocking; mounting the full dev tree incl. company repos → user sees the list, can object after).
- the temp-repo fixture verifies the LOGIC mount-independently; the live curl verifies the MOUNT. Both needed.
- docker-compose.yml is tracked → explicit-staged in the P1 commit (NOT template/data).

## Test ownership split
backend: the scan/derive logic (commit-count, LOC-filter, identity-map, TZ-VN, idempotent re-scan, fail-soft per repo, honest-empty-on-unmounted) — EXERCISE with a temp git repo fixture (git init + commits in the test, scan it, assert). tester: live GET /dev_activity on the container (real local repos, if mounted) + the scan trigger.

## Assumptions (user-review — log in end-doc)
- dev_activity tracks LOCAL git (P1) per date×repo×source(you/other). team-AI vs hand-typed = the source tag (2 honest fields). LOC = informational w/ LOC_SKIP filter (Goodhart — never a score). 90d backfill. identity-map = configurable emails. roots = DEV_TRACING_ROOTS (mounted :ro). **How to change:** the env config / the derive.
- the scan is idempotent (upsert per date×repo×source); daily routine + manual trigger.

## Notes
- #63 Phase 1 of 3 (local-scan, no-cred → proves value). Port the validate_dev_tracing.py PROVEN logic (LOC_SKIP, --no-merges, identity-map, TZ-VN) — zero invention. backend BUILDS; architect commits fix(sprint-DEV-TRACING-P1). The mount is the integration risk (flag if not wired). Next: P2 (remote GitHub/Bitbucket + dedup-SHA + cred + 1yr) → P3 (FE /activity heatmap + brief-wire). theme-sibling of #65 (the tracing pair: manual-habit + auto-dev). #73 (suite-refactor) sequences AFTER P1 (don't run 2 BE epics at once — 1 committer).
