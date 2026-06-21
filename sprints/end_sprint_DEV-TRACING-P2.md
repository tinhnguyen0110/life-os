# end_sprint_DEV-TRACING-P2 — remote dev-activity (Cairn #63 Phase 2 of 3, FINAL)

> Result. The dev_activity module now pulls REMOTE commits (GitHub API + Bitbucket Server) + DEDUPS by sha against the local scan (local⊕remote → ONE row) + 1yr backfill. Commit `<hash>` `fix(sprint-DEV-TRACING-P2)`. Status: ✅ all gates pass. backend-w3 BUILT (service.py remote-fetch + dedup + test); architect 4-step + committed (§3). **#63 dev-git-tracing MODULE DONE** (P1 local-scan + P2 remote + P3 FE). Cred = [USER-PROVIDES] gate (honest-skip when unset).

## What shipped (2 tracked files — clean follow-on to P1 7f9c0ef)
| File | Change |
|---|---|
| `modules/dev_activity/service.py` (+~196) | PORTS validate_dev_tracing.py remote half via a mockable `_http_get_json` boundary: `_github_commits` (GitHub API — user repos owner+collaborator+org → commits → sha/email/date + LOC via per-commit detail, LOC_SKIP-filtered, 10-commit/repo probe-budget); `_bitbucket_commits` (Bitbucket Server REST 1.0 — projects→repos→commits, newest-first break-past-since); `github_creds()` (PAT/USER + PAT2/USER2 multi-account) + `bitbucket_cred()` — **env ONLY (#50), unset → skip-source + honest warning**; `_fold_remote` + `seen_shas` threaded through `_scan_repo` → **DEDUP BY SHA** (local⊕remote → ONE row, THE P2 invariant); 1yr backfill (_DEFAULT_DAYS 90→365); scan() pulls remote AFTER local, per-source fail-soft. |
| `tests/test_dev_activity.py` (+8) | the remote distinguishing set, HTTP mocked (no live network). |
| schema/store/reader/router | UNCHANGED — P2 is additive DATA + dedup, no shape churn (the frozen schema held; no re-announce). |

## Design (LOCKED — dedup-by-sha, cred env-only, per-source fail-soft)
- **DEDUP by sha** (`_fold_remote`): a commit whose sha is already in `seen_shas` (seen locally or a prior remote) is SKIPPED — counted ONCE. The local scan seeds `seen_shas`; remote folds skip dupes. The invariant: a local repo that's also a GitHub remote does NOT double-count.
- **cred env-only** (#50): GITHUB_PAT/USER (+PAT2/USER2) + BITBUCKET_* from env; NEVER committed/printed. Unset → that source skipped + honest warning, scan completes with the rest (per-source fail-soft, like the brief). Remote-down/403/rate-limit → honest warning, no crash, no fabricated data (honest-mirror).
- **Remote LOC coarser** than local (per-commit detail, 10/repo probe-budget) — surfaced honestly, not presented as exact.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full settled files):** `_fold_remote` dedup correct (`if sha in seen_shas: continue` + add-new) ✅; `_scan_repo` seeds seen_shas ✅; cred env-only (grep for hardcoded token = EMPTY) ✅; `_http_get_json` mockable boundary ✅; the no-cred-leak test asserts the fake token ABSENT from the output blob (real teeth) ✅; 2-file surface, schema unchanged ✅.
- **backend-w3 evidence:** 8 MOCK-HTTP tests (remote-counted, dedup local⊕remote-same-sha→1, different-sha→2, GitHub-unset→skip+warn, 403/rate-limit→warn-no-crash, TZ-VN remote, no-cred-leak, remote LOC_SKIP). mypy clean. LIVE honest-skip on :8686 (cred unset → "GITHUB_PAT not set — GitHub source skipped" + "BITBUCKET_* not set", local 14 repos scan, NO crash, NO fabricated remote).
- **the inclusive "4 failures" are NOT a P2 regression** (Rule#0, confirmed both sides): they're the #58 test_activity live-:8686 slow-flake (all `@pytest.mark.slow`, requests-timeout under suite+live-scan contention) — they PASS in isolation. **DEFAULT suite (slow-excluded, the real dev gate): 0 FAILED** (architect's own run corroborates backend's 2029/0). Reconciles: 2029 + 18 deselected = 2047 = 2026 origin + 13 P1 + 8 P2.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** remote sources additive; cred env-only; honest-skip + warnings; schema unchanged. ✅
- **Gate 2 (Function):** dedup-by-sha + per-source fail-soft + no-cred-leak + TZ-VN (MOCK HTTP); DEFAULT suite 0-failed; mypy clean. ✅
- **Gate 3 (Sprint):** plan+end docs; architect 4-step + backend evidence + LIVE honest-skip; 2-file surgical stage (no cred/schema/FE leak); the inclusive-4 reconciled as the #58 slow-flake (not P2); commit format. ✅

## Assumptions (user-review)
- Remote = GitHub API + Bitbucket Server; cred env-only (#50 user-provides; unset → honest-skip + warn). DEDUP by sha (local⊕remote → 1). 1yr backfill. Remote LOC coarser (per-commit detail, 10/repo probe) — surfaced honestly. Per-source fail-soft (unauthed/rate-limit/unreachable → warn + skip, scan completes). **How to change:** the cred env / the probe-budget.
- **[USER-PROVIDES] gate:** remote-fetch activates ONLY when the user sets GITHUB_PAT/USER (+PAT2/USER2) + BITBUCKET_* in the container env. Until then dev_activity is local-only (honest-skip + warning). Surface to the user.

## Notes
- #63 Phase 2 of 3 — the remote+dedup phase. **#63 dev-git-tracing MODULE DONE** (P1 local-scan 7f9c0ef + P2 remote + P3 FE c4ea885). backend BUILT; architect committed (§3). The 4 inclusive-failures = the pre-existing #58 slow-flake (not P2 — confirmed isolation-pass + slow-marked). Live remote = [USER-PROVIDES cred] gate (flag to user: set GITHUB_PAT/USER etc. in container env to activate remotes). #77 (cold-scan→serve-from-store) still open — sequences next (matters for the agent surface). Next: #75-BE (after this) → #73 → #77 → #64.
