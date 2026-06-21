# Sprint AGENT-ERROR-P6 — read_server + agent_proposals/automation/activity + wiki conflict/proposal (Cairn #46 Phase 6, FINAL; folds #17)

> Created 2026-06-21 by architect (pre-grounded ∥). #46-family FINAL phase — completes the audit + FOLDS #17 (wiki conflict/sync/proposal 404s). Reuses agent_error_response (P3 spine). HOLD until P5 commits. backend EDITS; architect commits (§3).

## Context
After P3 (finance+market), P4 (projects+career), P5 (journal-cluster), the remaining raw errors are: the read_server feed-error free-text + agent_proposals/automation/activity routers + the wiki conflict/sync/proposal 404s (#17). ~12 sites. This phase CLOSES #46 (the parent) AND #17.

## Scope (Rule#0 pre-grounded — exact sites)
IN: mcp_servers/read_server.py (:837 feed-error) + agent_proposals/router.py + automation/router.py + activity/router.py + wiki/router.py (the conflict/sync/proposal 404s — #17 fold) + tests.
OUT: nothing left after this (the audit completes). NO helper change. NO 200-path change.

### Clean NOT_FOUND 404 (7 sites)
- agent_proposals/router.py :51/59/72/83 "proposal {id} not found" → NOT_FOUND
- automation/router.py :37/50 "routine {id} not found" → NOT_FOUND
- activity/router.py :45 "run {id} not found" → NOT_FOUND

### #67/#17 fold — wiki/router.py remaining raw errors (Rule#0 re-grounded — ~10 sites, MORE than the est. 4)
Full grep of wiki/router.py post-#61/#14:
- **:104** "wiki note {note} not found" — GET /graph?note= param (a note-404 but NOT a /notes/{id} route, so legitimately NOT in #61's scope) → NOT_FOUND.
- **:153/161** conflict "not found or already resolved" (#67) → judgment: NOT_FOUND or CONFLICT. Lean **NOT_FOUND** (message carries "or already resolved"); CONFLICT defensible. Decide at kickoff.
- **:158** "wiki note {body.noteId} not found" (note gone DURING resolve_conflict) → NOT_FOUND.
- **:257** "wiki note {exc} not found" (merge path missing-note) → NOT_FOUND.
- **:388/416** "wiki proposal {id} not found" → NOT_FOUND.
- **:255/320 :405** `raise HTTPException(422, detail=str(exc))` — validation passthroughs (the exc message). → INVALID_INPUT with str(exc) as the message (or keep if already FastAPI-validation-shaped — judge: a hand-raised 422 str(exc) → migrate; a pydantic auto-422 is FastAPI's own, untouched).
- **:403/418** `raise HTTPException(409, detail=str(exc))` (proposal conflict) → CONFLICT with str(exc).
→ ~10 wiki sites (3 NOT_FOUND note + 2 conflict + 2 proposal-NF + 3 str(exc) 422/409). Use agent_error_response (NOT the note-id _note_not_found — these are mixed entities). This is more than the est. 4 — scope confirmed at this kickoff.

### The nuances (RESOLVED at kickoff)
1. **read_server :837 — WITHDRAWN (backend's Rule#0 catch, architect-verified).** My dispatch mislabeled it "feed-error→UPSTREAM_DOWN+retryable=True". It's actually `_section()` (read_server:829) — the life_brief section-builder FAIL-SOFT (catches any exc per brief section → `{source, error}` so the brief still 200s). The `{source, error}` shape is LOAD-BEARING (test_mcp_e2e:65 asserts every section carries `source`; agent_error's `{error:{...}}` drops top-level source → breaks 4 tests). It's a degraded-section marker in a SUCCESSFUL brief, NOT an operation-error result; the exc can be deterministic → UPSTREAM_DOWN+retryable=True would mislabel. → **LEAVE _section as-is** (already agent-readable + a different contract). NOT a P6 site. **CONSEQUENCE: the retryable=True site is DISSOLVED — NO genuine retryable-upstream error exists in the current surface; ALL P6 sites are deterministic → retryable:False.** The retryable=True case appears when a real transient error (rate-limit/upstream) is added later. P6 distinguishing = "ALL deterministic → retryable:False" (none wrongly True).
2. **wiki conflict :153/161** code (NOT_FOUND vs CONFLICT) — lean NOT_FOUND (message carries the "or already resolved").

## HARD GATE (distinguishing)
- agent_proposals/automation/activity bad-id → 404 flat {error:NOT_FOUND}. wiki proposal bad-id → 404 NOT_FOUND. read_server feed-down → {error:UPSTREAM_DOWN, retryable:true} (the ONLY retryable=true in the audit — distinguishing: deterministic errors are retryable:false, this one true). All flat {error:{code}}, NO raw {detail}/free-text.
- Verify LIVE HTTP. pytest 0-failed, mypy clean.
- POST-P6: grep the WHOLE app for raw `raise HTTPException(...detail=` + free-text `{"error":` → confirm ONLY intentional-FE-only ones remain (the audit's completeness check). #46 + #17 both closeable.

## Baseline
pytest = post-P5 count. Keep 0-failed.

## Assumptions (user-review)
- **P6 closes the #46 audit + #17**: agent_proposals/automation/activity/wiki-proposal/wiki-conflict 404s → agent_error NOT_FOUND; read_server feed-error → UPSTREAM_DOWN+retryable=True (the one transient error). **How to change:** per-route calls + the 2 nuance codes.

## Notes
- #46 FINAL phase — completes the audit (P3 finance+market, P4 projects+career, P5 journal-cluster, P6 this) + folds #17. The read_server UPSTREAM_DOWN+retryable=True is the audit's one genuinely-retryable error (the retryable field finally earns its keep). Post-P6: a completeness grep confirms the audit is done → close #46 (parent) + #17. backend EDITS; architect commits fix(sprint-AGENT-ERROR-P6).
