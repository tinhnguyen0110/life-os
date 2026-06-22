# end_sprint_118-CODE-INSIGHT-GIT — migrate code_insight's 3rd git-helper copy to core.git (Cairn #118)

> Result. #115 made core/git.py the shared read-only git-exec layer for projects + dev_activity, but code_insight/service.py carried a THIRD copy of `_READ_ONLY_GIT` + `_git`. Migrated it to thin core.git aliases — core.git is now the SINGLE git-read source across all 3 modules. Commit `<hash>` `refactor(sprint-118-code-insight-git)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT contract-check + mypy --no-incremental + suite). Cairn #118 — be-only low-pri cleanup, CLOSES on this commit. Pure refactor (byte-identical FOR THE CALLER). The #115-pattern, 3rd site.

## What shipped
| File | Change |
|---|---|
| `code_insight/service.py` (−13) | `_READ_ONLY_GIT = core_git.READ_ONLY_GIT`; `_git = core_git.run_read_git`. Old inline `_git` + local whitelist deleted. Zero caller change. |
| `tests/test_core_git.py` (+2) | `test_code_insight_reexports_are_the_shared_symbols` (are-identity) + `test_code_insight_log_byte_identical_to_inline` (deterministic: code_insight's exact `git log -n15` via the new shared `_git` == the old inline `subprocess.run().stdout.strip()` on a FIXED repo). |

## Design (LOCKED — single git-read source; the contract-DIFFERENCE handled)
- **core.git = THE single read-only git-exec** across projects + dev_activity + code_insight. No more duplicate whitelists/exec.
- **🔴 the contract DIFFERENCE (the real risk, verified safe):** code_insight's old `_git` raised `RuntimeError` on failure + did NOT catch `FileNotFoundError`/`TimeoutExpired` (they propagated raw). The shared `core_git.run_read_git` raises `RepoUnreadable` + catches FileNotFound/Timeout (re-raised as RepoUnreadable). So the exception TYPE on a git-failure path changed. **BYTE-IDENTICAL FOR THE CALLER:** the lone caller `_recent_commits` wraps the call in `except Exception` (line 132) → catches BOTH old and new types identically → warning + return []. The whitelist test asserts `ValueError` on a mutating op → preserved (core raises ValueError too). core's 7-item whitelist ⊇ code_insight's 6; code_insight only runs `log`.
- **The only observable delta** = the warning STRING `f"git log failed ({type(exc).__name__})"` reports `RepoUnreadable` instead of `RuntimeError` on an actual git failure — and NO test pins that string (verified). Unobservable in practice.

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL):** the diff (aliases, old impl deleted); **🔴 the contract-change safety verified by READING `_recent_commits` myself** — confirmed it's `except Exception` (broad, absorbs the type change) + it's the LONE `_git` caller (grep). Confirmed NO test pins the warning string / exception type (the only observable delta). Whitelist superset (code_insight runs only `log` ∈ the 7-set). ✅
- **🔴 mypy --no-incremental (cache off, #113 lesson):** code_insight + core/git → ZERO non-yaml errors. ✅
- **INDEPENDENT suite:** 44 passed (code_insight + core/git, forward); backend code_insight 18 + FORWARD 2358/0 == REVERSE; LIVE /code_insight?repo=cairn recentCommits=15 via the shared helper stable. ✅
- **DETERMINISTIC byte-identical proof (the #115-pattern, +2 tests):** code_insight's exact `git log` via old-inline AND the shared helper on a FIXED repo → byte-identical + the re-exports are-identity. NOT a live snapshot. ✅

## 3 Gates
- **Gate 1 (n/a — no endpoint change):** internal helper migration.
- **Gate 2 (Function):** the deterministic byte-identical proof + are-identity + the contract-difference verified caller-safe + 44 passed + mypy --no-incremental clean. NOT self-confirming. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent; staged EXACTLY #118 (code_insight + test_core_git, NO FE/projects/dev_activity/data leak); commit format. ✅

## Assumptions (user-review)
- **code_insight._git is now core.git.run_read_git** (shared). **How to change:** the alias in code_insight/service.py. The exception type on a git failure is now RepoUnreadable (was RuntimeError) — caller-invisible (except Exception).

## Notes
- Cairn #118 — be-only low-pri cleanup (backend-w3 flagged it during #115; team-lead dispatched per architect recommendation). backend-w3 built; architect committed (§3 sole-committer). 🔴 **The standout lesson (backend logged + worth carrying):** a "3rd duplicate" is NOT guaranteed identical — code_insight's `_git` had a DIFFERENT failure contract (RuntimeError + no FileNotFound/Timeout catch) than projects'/the shared one. Before aliasing a "duplicate" to a shared helper, READ its code AND its callers' `except` clauses to confirm the difference is caller-invisible. Here it was (the lone caller's `except Exception` absorbs the type change; no test pins the warning string) — so the alias is safe. Had the caller caught `RuntimeError` specifically, the new `RepoUnreadable` would have escaped — a real bug the contract-check prevents. core.git is now the single git-read source (projects + dev_activity + code_insight). PROJECTS-UNIFY arc + its cleanups complete (#112/#113/#114/#115/#118). Disjoint, no restart.
