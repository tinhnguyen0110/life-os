# end_sprint_REPO-MEMORY-P2 — durable Repos/<name> memory note (Cairn #64 Phase 2)

> Result. The DURABLE per-repo memory: a wiki `Repos/<name>` note a session-agent READS for curated context (summary/stack/decisions/lessons/in-progress) + PROPOSES to update (via the wiki propose path). Commit `<hash>` `fix(sprint-REPO-MEMORY-P2)`. Status: ✅ all gates pass. backend-w3 BUILT (extend code_insight — the repo-memory pair); architect 4-step + committed (§3). **Completes #64's backend** (P1 code_insight fresh-read + P2 repo_memory curated-note). The last user-CHỐT feature epic. ⚠ the live agent-WRITE auto-land is #80-gated (read + propose-enqueue ship).

## What shipped (extend code_insight — the repo-memory pair)
| File | Change |
|---|---|
| `modules/code_insight/repo_memory.py` (NEW) | `get_memory(repo)` — find the Repos/<name> wiki note (folder=="Repos" + title==repo, deterministic match over wiki_store.all_notes → full body via wiki_service.get_note) → RepoMemory{note|null, found}. honest found:false. NEVER scans the repo (that's code_insight). `propose_memory(repo, body)` — REUSE the wiki propose (note_edit if exists else note_create, folder=Repos, title=<name>) — does NOT fork the wiki engine. |
| `schema.py` | +RepoMemoryNote + RepoMemory (FROZEN). |
| `reader.py` | +get_memory. |
| `router.py` | +GET /code_insight/memory?repo=. |
| `mcp_servers/read_server.py` + CATALOG.md | +MCP repo_memory (read, ≡REST #24). Read count 45→46 (count-consumers: 3 files + CATALOG). |
| `tests/test_code_insight.py` (+6, 18 total) | the read + propose distinguishing set. |

## Design (LOCKED — read folder-match, write reuse-propose, the cold-agent pair)
- repo_memory = a wiki `Repos/<name>` note (curated, durable). READ = deterministic folder+title match (reuse the wiki store). WRITE = the wiki propose (kind=note, folder=Repos) — human-apply-gated by design (+#80 auto-land block for the MCP non-root caller). NO new wiki engine (reuse the propose/store).
- **the cold-agent pair**: code_insight (P1, fresh-now — structure/README/git-log, never persisted) + repo_memory (P2, curated-learned — the durable note). A new session-agent for repo X = code_insight(X) [what's there NOW] + repo_memory(X) [what we've learned]. Two complementary layers, the #64 design realized.

## Verification (Rule#0 — architect 4-step + backend evidence)
- **architect 4-step (read full):** get_memory folder+title deterministic match (reuse wiki_store.all_notes; full body via get_note; honest found:false; NEVER scans — separation from code_insight) ✅; propose_memory reuses the wiki propose (note_create/note_edit, no fork) ✅; the #80 land-gate documented in-code ✅; count 45→46 (3 files + CATALOG) ✅; P2-only additions on top of the COMMITTED P1 (f9ed777 — verified the CodeInsight class is committed, not re-added; the diff is RepoMemory additions only) ✅.
- **backend-w3 evidence:** 6 EXERCISE tests (read-found, not-found→found:false, only-Repos-folder-matches [a same-title note elsewhere ≠ memory], propose-create-enqueues, propose-edit-when-exists [no dup], MCP≡REST). mypy clean. DEFAULT 2067/0 (= 2061 + 6). LIVE on :8686: seeded Repos/p2verify (root-write #80-workaround) → GET memory found:true; missing→found:false; propose_memory enqueued a note_edit proposal. SCOPED cleanup (by name, the #72 discipline).
- **architect re-run:** code_insight + 3 MCP count tests 138/0.

## ⚠️ #80 SOFT-DEP (flagged, NOT fixed here — its own task)
The live agent-WRITE round-trip (MCP non-root caller proposing → auto-apply) is BLOCKED by #80 (Errno-13, root-owned data dir): a P2 agent-write ENQUEUES the proposal (recorded pending) but won't AUTO-LAND until #80. The READ + the propose-ENQUEUE both work + are tested; the auto-LAND waits on #80. (The live read-verify used a root-write seed as the workaround.) → #80 is the unblock for the full agent-write round-trip.

## 3 Gates — ALL PASS
- **Gate 1 (API/MCP):** GET /code_insight/memory + MCP repo_memory (≡REST #24); reuse the wiki propose (no fork); honest found:false. ✅
- **Gate 2 (Function):** the read/propose distinguishing (found/not-found/only-Repos-folder/create-enqueue/edit-no-dup); DEFAULT 2067/0; mypy clean. ✅
- **Gate 3 (Sprint):** plan(dispatch)+end docs; architect 4-step + backend evidence + LIVE (root-seed workaround for the #80-gated write); surgical stage (code_insight P2-additions, no core/compose/FE leak); the #80 land-gate flagged; commit format. ✅

## Assumptions (user-review)
- repo memory = a wiki Repos/<name> note (curated). Read = folder+title match (reuse wiki store). Write = wiki propose (kind=note, folder=Repos), human-apply-gated (+#80 auto-land block until fixed). code_insight (fresh-now) + repo_memory (curated-learned) = the cold-agent pair. **How to change:** the Repos/ convention / the note shape.

## Notes
- #64 Phase 2 of 3 — **completes the #64 BACKEND** (P1 code_insight + P2 repo_memory). The last user-CHỐT feature's backend done. backend BUILT (extend code_insight, reuse the wiki propose); architect committed (§3) as a P2-only follow-on to the committed P1 (f9ed777). ⚠ #80 unblocks the live agent-write auto-land (read + propose-enqueue ship now). #64 is at a MODULE-MILESTONE (functionally most-of-the-way: P1 fresh-read + P2 read+propose; remaining = the #80 auto-land + P3 FE) — team-lead assesses surface-now-vs-P3-first. Next: #79 → #78 → #80 → #64-P3 (FE, nav-IA resolved).
