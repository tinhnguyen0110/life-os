# end_sprint_84-DEV-TRACING-YOU-FIX — dev_activity yourCommits=0 bug FIXED (Cairn #84)

> Result. The dev-activity scan reported `yourCommits=0` for every repo — because `your_emails()` split `DEV_TRACING_EMAILS` on `":"` (like ROOTS/paths) when the env value is a COMMA list of author emails → the whole list collapsed into ONE element → no commit author matched → all commits tagged "other". Fix: emails `split(",")` (ROOTS stays `split(":")` — paths). + docker-compose passes the GitHub/Bitbucket creds through (`${VAR:-}` interpolation, from the gitignored root .env) so the remote contribution counts fire. Commit `<hash>` `fix(sprint-84-dev-tracing): dev_activity emails comma-split + compose env pass-through (#84)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT teeth + HARD secret-check + suite). BUG-HIGH (admin-lead raised). LIVE: yourCommits 0→1688 (14 repos, 605 real rows).

## What shipped (1 prod line + compose env + 5 tests)
| File | Change |
|---|---|
| `modules/dev_activity/service.py` | `your_emails()`: `raw.split(":")` → `raw.split(",")` (emails are a COMMA list; `:` collapsed the list into one element → no match → you=0). Docstring corrected ("colon"→"COMMA") with the bug explanation. `scan_roots()` (DEV_TRACING_ROOTS) UNCHANGED at `split(":")` — ROOTS are filesystem paths (colon-separated, correct). |
| `docker-compose.yml` | backend `environment:` += `GITHUB_PAT/GITHUB_USER/BITBUCKET_HOST/BITBUCKET_USER/BITBUCKET_PASS: ${VAR:-}` — INTERPOLATION ONLY (real values from the gitignored root .env, injected at compose-up). Unset → the scan honest-skips the remote count + warns. **NO hardcoded secret value** (HARD-checked). |
| `tests/test_dev_activity.py` (+5) | comma-split (3-elem) + colon-regression-guard (old colon value → 1 element, proves the switch) + single/empty + ROOTS-stay-colon (proves the fix touched ONLY emails) + e2e (comma list → yourCommits==1, was 0 with the bug). |

## Design (LOCKED — minimal fix, correct separator per env)
- **Root cause:** `DEV_TRACING_EMAILS` is a COMMA list of git author emails/names; `DEV_TRACING_ROOTS` is a COLON list of filesystem paths. `your_emails()` wrongly used the ROOTS separator (`:`) → 1 collapsed element → no author matched → every commit "other" → yourCommits=0.
- **Fix:** emails `split(",")`; ROOTS stays `split(":")` (paths). One-line change, separator-correct per env. Guarded by `test_roots_stay_colon_separated` so a future edit can't accidentally unify them.
- **Creds (Fix-2):** the remote contribution scan (GitHub/Bitbucket) reads `GITHUB_PAT/USER` + `BITBUCKET_HOST/USER/PASS`; docker-compose now passes them via `${VAR:-}` from the root .env (gitignored). Honest-skip + warn when unset (no silent fail, no fabricated count). No hardcoded secret in the tracked compose file.

## Verification (Rule#0 — architect INDEPENDENT)
- **🔴 HARD secret-check (docker-compose):** the staged diff is EXACTLY the 5 cred env lines + their comment, ALL `${VAR:-}` interpolation; a secret-value scan (ghp_/gho_/github_pat_/ATBB/32+char strings/password-literals) found ZERO. No other compose change swept in. SAFE to commit. ✅
- **architect 4-step (read FULL functions):** the email-split fix correct (emails comma, ROOTS colon-kept); docstring honest; the 5 tests cover the distinguishing cases (comma-split + colon-regression + ROOTS-stay-colon + e2e you>0). ✅
- **architect INDEPENDENT teeth-proof:** reverted `split(",")`→`split(":")` → `test_your_emails_comma_separated` + `test_comma_emails_tag_you_end_to_end` BOTH went RED; restored → green. Real fix, real distinguishing power. (Did NOT trust backend's teeth report — re-ran it.)
- **backend LIVE evidence (compose env needs `docker compose up -d`, not hot-reload):** `POST /dev_activity/scan?days=90` → yourCommits **1688** (was 0!) + warnings **[]** (no "GITHUB_PAT not set") + 14 repos / 605 rows, HTTP 200. (The route mount is `/dev_activity` — underscore = module name.)
- **Suite:** dev_activity 31 passed (5 new + existing); DEFAULT (`-m 'not slow'` deterministic) = **2126 passed / 6 skipped / 3 deselected / 0 failed** (the +5 #84 tests were already in the 2126 — they were on the tree when #35/#36 were measured); mypy clean.

## 3 Gates
- **Gate 1 (config):** docker-compose env-pass is `${VAR:-}` interpolation only, no secret value, honest-skip+warn when unset. ✅
- **Gate 2 (Function):** the comma-split fix + 5 distinguishing tests (incl. the e2e you>0 + the colon-regression + ROOTS-stay-colon guards); independent teeth (revert→RED); 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent teeth + HARD secret-check + backend live evidence; counts 2126 (0 failed); staged set EXACTLY service.py + docker-compose.yml + test_dev_activity.py (no other compose change, no secret, no data/.env/template/wiki/brief leak); commit format. ✅

## Assumptions (user-review)
- **DEV_TRACING_EMAILS = COMMA-separated; DEV_TRACING_ROOTS = COLON-separated.** **Why:** emails/names can't contain commas (paths can't contain colons on Linux either, but the env value IS comma-joined). **How to change:** the `split()` delimiters in `your_emails()` / `scan_roots()`.
- **5 cred vars passed (GITHUB_PAT/USER + BITBUCKET_HOST/USER/PASS); the optional GITHUB_PAT2/USER2 multi-account NOT added** (not requested — no over-engineering). **How to change:** add them to compose + service if a 2nd GitHub account is needed.
- **The live scan wrote 605 real commit rows to the dev store** — this is the FEATURE working (idempotent upsert of real data), NOT test pollution (no cleanup needed).

## Notes
- Cairn #84 BUG-HIGH (admin-lead raised; backend-w3 built in parallel with #35/#36, committed serially AFTER them). Disjoint surface (dev_activity + compose, no overlap with wiki/brief). The dev-tracing feature now correctly attributes the user's commits (0→1688). After #84 → only #78 remains on the doable board (architect risk-assesses first).
