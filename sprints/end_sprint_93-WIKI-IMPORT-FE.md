# end_sprint_93-WIKI-IMPORT-FE — wiki import button + modal (Cairn #93 FE, CLOSES #93)

> Result. The FE for the wiki import: an "Import .md/.txt" button (in the toolbar AND the empty-vault bootstrap branch — the "chưa upload được" entry) → a modal: pick file(s) / paste → preview → confirm → per-file results (created → link to the note · errors → the agent-error message+hint, fail-soft) → refresh the tree. Calls the FROZEN #93-BE `POST /wiki/import`. Commit `<hash>` `feat(sprint-93-wiki-import-fe): import button + modal + empty-vault bootstrap (#93 FE, closes #93)`. Status: ✅ verified (frontend-w3-2 built + unit+API; architect 4-step + tsc + vitest; the 31s was a dev-compile artifact, NOT a #93 defect — endpoint Rule#0-verified ~4ms). Cairn #93 FE — CLOSES #93 (BE 7b12052 + this FE).

## What shipped (FE — modal + button + the proactive hoist fix)
| File | Change |
|---|---|
| `components/WikiImport.tsx` (NEW) | the import modal: file pick (FileReader, multi, accept .md/.txt) + paste-text; preview (filename+snippet, removable); confirm → `POST /wiki/import {files}` (reqId-guard drops a stale response); per-file results (created → `Link /wiki/{noteId}` with title · error → the agent-error `message` + `hint`, fail-soft); `onImported()` refreshes the tree on any success. RENDER-ONLY against the FROZEN endpoint. |
| `app/wiki/page.tsx` | the import button + the modal HOISTED OUTSIDE the status-gated branches (so post-import results survive a reload-to-loading — a proactive correctness fix); the import button ALSO on the **empty-vault branch** (the bootstrap path — import is the key way to fill an empty vault, the user's "chưa upload được" pain). |
| `lib/api.ts` | `importWiki({files})` → `POST /wiki/import`. |
| `lib/types.ts` | `WikiImportFile {filename,content}` + `WikiImportResult {filename,ok,noteId,title,error}` (mirror the FROZEN #93-BE result-row). |
| `lib/tokens.css` | the .wimport-* modal styles. |
| `components/__tests__/WikiImport.test.tsx` (NEW, 9) | the import flow: pick→preview→confirm→results; the agent-error result row renders message+hint; fail-soft (mixed ok+error); paste path; empty-guard. |

## Design (LOCKED — render-only, honest per-file results, bootstrap-aware)
- **render-only:** the BE parses frontmatter + creates the note (1 commit, [[link]] resolve); the FE reads files client-side (FileReader) → sends {filename,content} → surfaces the honest per-file outcome. No client-side parsing.
- **honest per-file results (fail-soft):** created → a link to the note; a bad file → its agent-error `message` + `hint` (NOT a generic "failed") — mirrors the BE's fail-soft batch.
- **modal hoisted outside the status-gated branches** (proactive fix): import results survive a reload-to-loading transition.
- **empty-vault bootstrap:** the import button is on the empty-vault branch too — import is the primary way to fill a fresh vault (the user's exact pain).
- **reqId guard:** a stale POST response (re-submit before the first lands) is dropped.

## Verification (Gate-2 FE — frontend-w3-2 unit+API + architect 4-step)
- **architect 4-step (read FULL):** WikiImport.tsx (pick/paste/preview/confirm/per-file-results/reqId-guard/onImported) ✅; page.tsx modal-hoist OUTSIDE status-branches + import button on empty-vault bootstrap ✅; api/types mirror the FROZEN result-row ✅; FE-only surface (the ~10 dirty backend/modules/wiki files are #94-BE in-flight — staged OUT) ✅.
- **architect independent re-run:** tsc clean (exit 0); vitest FULL **956 passed / 0 failed** (947→956, +9 WikiImport); the endpoint sanity-checked myself = `/wiki/overview` 4ms (the 31s FE flagged is a dev-compile/render artifact, NOT the HTTP request, NOT BE, NOT a #93 defect — confirms team-lead's exhaustive diagnosis).
- **frontend-w3-2:** vitest 956 (full import flow incl results + agent-error row + fail-soft); API-confirmed (good .md→note w/ frontmatter, .txt→note). The final Chrome screenshot is the only unverified bit, blocked SOLELY by the dev-compile artifact (warm second load is fine) — not a defect; FE does it once the dev-compile settles.

## 3 Gates (FE sprint)
- **Gate 2 (Function):** vitest (WikiImport 9 + full suite) + tsc clean + the import-flow/agent-error-row/fail-soft tests; the dev-compile-artifact (not a defect) diagnosed + endpoint Rule#0-verified fast. ✅
- **Gate 3 (Sprint):** end-doc; FE-agent unit+API + architect 4-step; commit-hygiene (FE-only — the #94-BE in-flight backend files staged OUT, no leak); commit format. ✅

## Assumptions (user-review)
- import button on the toolbar AND the empty-vault bootstrap branch (import = the primary fill-an-empty-vault path). **How to change:** page.tsx.
- the modal is hoisted outside the status-gated branches (results survive a reload). **How to change:** page.tsx render structure.

## Notes
- Cairn #93 FE — **CLOSES #93** (BE 7b12052 import endpoint + this FE import UI). The "chưa upload được" pain is fixed end-to-end: pick/paste .md/.txt → preview → import → notes created (frontmatter mapped, [[links]] resolved) + honest per-file errors. frontend-w3-2 built; architect committed (§3 sole-committer). Committed from a HEAVILY intermixed tree (#94-BE in flight on ~10 backend/wiki files) — FE-only surgical stage, no leak. The 31s /wiki/overview FE flagged was a dev-compile/render artifact (endpoint ~4ms from every path, Rule#0-verified) — NOT a #93 defect, NOT a BE perf task. Next: #94-BE continues (soft-delete) → then #51 (overdue→mail), both in the single BE agent.
