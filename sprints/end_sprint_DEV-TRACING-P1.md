# end_sprint_DEV-TRACING-P1 — local-scan dev-activity (Cairn #63 Phase 1 of 3)

> Result. NEW `modules/dev_activity/` — track dev-activity FROM local git (commits/LOC/active-span per VN-date × repo × source) with ZERO credentials. Commit `<hash>` `fix(sprint-DEV-TRACING-P1)`. Status: ✅ all gates pass. backend-w3 BUILT (module + compose mount + MCP + tests); architect 4-step + committed (§3, sole serialized committer). Phase 1 of 3 (**P1 local-scan** → P2 remote+cred → P3 FE+brief). The dev-git-tracing P1 milestone: local-scan works end-to-end on real repos.

## What shipped (NEW module 6 files + compose mount + MCP wire + tests — 8 staged paths)
| File | Change |
|---|---|
| `modules/dev_activity/schema.py` (FROZEN) | RepoDay/DayView/RepoSummary/DevActivitySummary/DevActivityOverview/ScanResult. source open-str (you/other; P2-forward-compat). LOC informational. |
| `modules/dev_activity/store.py` | SQLite `dev_activity` table, `PRIMARY KEY (date,repo,source)` + `ON CONFLICT...DO UPDATE` → idempotent UPSERT (re-scan replaces, no double-count). |
| `modules/dev_activity/service.py` | PORTS validate_dev_tracing.py local_probe (git --numstat, LOC_SKIP verbatim, binary-numstat→0 guard) + dispatch refinements: `git log --no-merges --all --since --numstat`, %ae identity-map (you/other), TZ→VN-day, source-tag, per-commit sha (P2 dedup). honest warnings (ROOTS/EMAILS unset). |
| `modules/dev_activity/reader.py` | derive byDay/byRepo/summary/otherRepos (raw-data-first — store aggregates, derive in reader). |
| `modules/dev_activity/router.py` | GET /dev_activity + POST /dev_activity/scan + daily `dev-activity-scan` routine (05:00 UTC) + `MODULE=BaseModule(name="dev_activity", routines=[...])` — registry auto-discover, NO core/main.py edit. |
| `docker-compose.yml` | +`:ro` mounts `/devscan/PSA` + `/devscan/inmobi` (company repos, siblings of the existing `/tinhdev`) + `DEV_TRACING_ROOTS`/`DEV_TRACING_EMAILS` env (`${VAR:-default}`, honest-skip a missing host dir). Reader never writes (:ro enforced). |
| `mcp_servers/read_server.py` + CATALOG.md | +`dev_activity(days)` (reference-import the reader, byte-identical to GET /dev_activity, #24). Read count 43→44 (count-gotcha: test_mcp_http/test_mcp_read/test_finance_mcp_shape all 43→44 + CATALOG, same commit). |
| `tests/test_dev_activity.py` (NEW, 13) | the distinguishing set via a REAL temp git-repo fixture. |

## Design (LOCKED — port the validated reference, raw-data-first, honest)
- PORTS the admin-lead-validated `validate_dev_tracing.py` logic (the 9 traps pre-solved) — zero invention.
- source-tag (you/other) = 2 honest fields (count-in-totals-but-tagged, never merged/dropped; identity unset → all "other"+warning, NEVER silently "you").
- LOC informational w/ LOC_SKIP filter (Goodhart — never ranked/scored; commits + active-span + by-repo distribution are primary).
- idempotent scan (UPSERT per date×repo×source); daily routine + manual POST /scan. honest-empty + warnings on unreachable roots (not silent-zero, not crash — host-file-source-must-mount).

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full settled files):** service ports validate faithfully — LOC_SKIP verbatim ✅, binary-numstat `int()`→ValueError→continue (0 LOC) ✅, identity-map %ae you/other ✅, TZ→VN-day ✅, --no-merges --all ✅; store UPSERT idempotent (PK date,repo,source + ON CONFLICT DO UPDATE) ✅; router MODULE registry (NO core edit) + daily routine ✅; read_server dev_activity byte-identical to REST (#24) ✅; **shared-risk files content-diffed**: read_server.py = dev_activity-only, docker-compose.yml = mount-only, the 3 count files = 43→44-only (no cross-lane leak from the intermixed tree). ✅
- **backend-w3 evidence:** 13 EXERCISE tests via a REAL temp git repo (identity you-vs-other, EMAILS-unset→all-other+warning, LOC_SKIP, binary→0, --no-merges, idempotent-rescan, no-roots/unreachable→warning-no-crash, non-git-skip, TZ-VN, active-span, registry-discovered, MCP byte-identical). run-the-red caught 2 test bugs pre-report. mypy clean (7 files). pytest INCLUSIVE 2039/0 (= 2026 + 13).
- **LIVE on real repos (the #1 P1 risk — the mount — RESOLVED):** `docker compose up -d --build` re-up → /devscan/PSA + /devscan/inmobi + /tinhdev visible; POST /dev_activity/scan?days=30 → 14 repos / 34 rows (cairn 83c/10057LOC, life-os 49c/15456LOC); honest yourCommits=0 + warning (EMAILS unset → all "other"); LOC filtered+sane (no fake +5000). Registry: 24 modules, ZERO core/main.py edit (git-clean confirmed).

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** GET /dev_activity + POST /scan; registry mount (no core edit); MCP dev_activity byte-identical (#24); honest-empty + warnings; locked envelope. ✅
- **Gate 2 (Function):** the distinguishing set (identity/LOC_SKIP/binary/--no-merges/idempotent/honest-empty/TZ-VN) via real temp-git fixture; INCLUSIVE 2039/0; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend evidence + LIVE real-repo scan; surgical stage (8 explicit paths, content-diffed vs the intermixed tree — no leak); commit format; the compose change explicit-staged (tracked, not template/data). ✅

## Assumptions (user-review)
- **dev_activity = LOCAL git (P1, no-cred)** per VN-date × repo × source(you/other). source-tag = 2 honest fields (count-in-totals-but-tagged). LOC informational w/ LOC_SKIP (Goodhart, never ranked). 90d backfill (P2→1yr). identity-map = DEV_TRACING_EMAILS (unset → all "other"+warn, never silently "you"). **How to change:** the env config / the derive.
- **mount (authorized):** `:ro` mounts of the dev tree incl. company repos (/tinhdev + /devscan/PSA + /devscan/inmobi), DEV_TRACING_ROOTS env. Reversible, read-only, user-owned, localhost — consistent with the user-CHỐT "count company / life-os local". **Surfaced to the user** (team-lead) for transparency; override via *_HOST_DIR / the envs. Secrets/cred OUT (P1 no-token; cred = P2, user-only per #50).
- **idempotent scan** (UPSERT) + daily routine 05:00 UTC. (On-record, no code: tracing goal=0 = valid no-target, KEEP accepting.)

## Notes
- #63 Phase 1 of 3 — the local-scan milestone (proves value, no cred). PORTS the validated reference (zero invention). backend BUILT; architect committed (§3, sole serialized committer). Committed from an INTERMIXED tree (#72-BE just before, #63-P3 FE building) — surgical-staged 8 P1 paths, content-diffed (no leak). The :ro company-repo mounts are surfaced to the user (team-lead). Route for the FE phase = `/dev-activity` (NOT /activity — that's the existing Run-Log feed; collision caught at 4-step). Next: P2 (remote GitHub/Bitbucket + cred + dedup-SHA + 1yr) → P3 (FE /dev-activity + brief-wire, dispatched). #73 (suite-refactor) sequences after P1. Arrival-order commits: P1 → #76/P3/P2.
