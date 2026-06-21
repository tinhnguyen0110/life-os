# end_sprint_REPO-MEMORY-P1 — code_insight on-demand repo-read (Cairn #64 Phase 1)

> Result. NEW `modules/code_insight/` — an ON-DEMAND fresh read of a repo (structure + README + recent git-log + stack-detect + asOf) so a cold session-agent gets instant "what's here NOW" context. NOT indexed (always-current; an index would go stale). Commit `<hash>` `fix(sprint-REPO-MEMORY-P1)`. Status: ✅ all gates pass. backend-w3 BUILT; architect 4-step + committed (§3). The last user-CHỐT feature epic, P1 (P2 = the durable Repos/<name> wiki note).

## What shipped (NEW module 5 files + MCP wire + count-consumers)
| File | Change |
|---|---|
| `modules/code_insight/schema.py` (FROZEN) | `CodeInsight {repo, root, found, structure:str[] (bounded), readme:str|null (excerpt, bounded), recentCommits:[{sha,msg,date}] (bounded), stack:str[], asOf:ISO, warnings:str[]}`. |
| `service.py` | the on-demand read: resolve repo (name under DEV_TRACING_ROOTS OR a path UNDER a root — NO arbitrary traversal) · bounded structure (cap 80, skip .git/node_modules/vendor/dist) · bounded README (cap 4000 chars) · recent git-log via the READ-ONLY git whitelist · stack-detect · asOf (live ts). Fail-soft per sub-read; honest found:false + honest-empty on missing. |
| `reader.py` (thin) + `router.py` | GET /code_insight?repo= + `MODULE=BaseModule(name="code_insight")` (registry auto-discover, NO core edit). |
| `mcp_servers/read_server.py` + CATALOG.md | +`code_insight` (reference-import, byte-identical to GET, #24). Read count 44→45. |
| count-consumers (same commit) | test_mcp_http/test_mcp_read/test_finance_mcp_shape all 44→45 + CATALOG (the count-gotcha, multi-file). |
| `tests/test_code_insight.py` (NEW, 12) | the temp-git-repo distinguishing set. |

## Design (LOCKED — on-demand fresh, read-only, bounded, traversal-guarded)
- **on-demand, NEVER indexed** — re-read each call → always-current (an index would go stale on a code change). asOf carries the live read-ts (honest freshness).
- **read-only git whitelist** (`_READ_ONLY_GIT = {log, rev-parse, rev-list, status, ls-files, show-ref}`) — mutating git structurally refused (mirrors projects/reader). NO write git.
- **path-traversal guard** — a path must be UNDER a configured root (`cand.startswith(root_abs + os.sep)`) + a git repo; NAME-match only among repos found under roots. Can't read outside the mounted :ro dev tree (security-sound).
- **bounded everything** (structure 80 / README 4000 chars / commits 15 — caps noted in warnings; agent-first lean, no wall-of-dump).
- **reuses** dev_activity's :ro mounts + repo-resolve (scan_roots/_find_repos, DRY) — NO new mount.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full):** the read-only git whitelist (mutating refused) ✅; the path-traversal guard (under-root-only, no arbitrary ..) ✅; bounded structure/README/commits (caps + warnings) ✅; on-demand (asOf live, not cached) ✅; count-consumers 44→45 consistent (3 files + CATALOG) ✅; registry MODULE (no core edit) ✅; surface = code_insight/* + test + read_server + CATALOG + 3 counts (NO core/compose/FE).
- **backend-w3 evidence:** 12 temp-repo EXERCISE tests (found:true full, resolve-by-name, missing→found:false, no-roots→warning, no-README→null, structure/README bounded, skip-noise-dirs, LIVE-read-reflects-change, git-whitelist-refuses-mutating, registry, MCP≡REST). mypy clean. DEFAULT 2061/0 (2046 + 3 #73-committed + 12). registry 25 modules, ZERO core edit, no new mount. LIVE on the container: GET /code_insight?repo=cairn → found:true, real structure + 15 commits + stack["docker"] + asOf; missing→found:false+warning; README null for cairn (honest — it has CLAUDE.md, no README*).
- **architect re-run:** code_insight + 3 MCP count tests 132/0.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** GET /code_insight + MCP code_insight (≡REST #24); registry mount (no core edit); honest found:false; read-only + traversal-guarded. ✅
- **Gate 2 (Function):** the distinguishing set (found/missing/no-README/bounded/live-read/whitelist-refuses) via temp-repo fixture; DEFAULT 2061/0; mypy clean. ✅
- **Gate 3 (Sprint):** plan(dispatch)+end docs; architect 4-step + backend evidence + LIVE container read; surgical stage (code_insight-only, no core/compose/FE); commit format. ✅

## Assumptions (user-review)
- code_insight = on-demand (never indexed → always-current). Bounded (structure 80 / README 4000 / commits 15 — caps in warnings). Read-only git whitelist. Repo resolve = name|path UNDER the :ro roots (no arbitrary traversal). Reuses dev_activity's mounts + resolve. **How to change:** the caps / the stack-detect set / the whitelist.

## Notes
- #64 Phase 1 of 3 — the last user-CHỐT feature's first phase. code_insight (fresh read) is the VOLATILE half; P2 = the durable Repos/<name> wiki memory NOTE (the curated half). A new session-agent for repo X = code_insight(X) [now] + Repos/X [learned]. backend BUILT; architect committed (§3). ⚠️ **#64-P2 ↔ #80 soft-dep** (its note-WRITE uses the MCP write-through broken by #80 — flag at P2 dispatch; P1 read-only is unaffected). Next: #64-P2 (Repos/ note) → #78/#79 → #64-P3 (FE, after nav-IA).
