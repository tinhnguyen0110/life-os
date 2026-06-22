# end_sprint_105-PROJECTS-CASE-INSENSITIVE — name-or-id-any-case lookup, 4 surfaces (Cairn #105, dogfood)

> Result. `projects_list` returns `{name:"ClaudeManager", id:"claudemanager"}` — but `GET /projects/ClaudeManager` (the name, or any case) → 404; only the exact lowercase slug → 200. An agent naturally using the `name` got a dead 404. Fixed at the ONE lookup chokepoint (`service.get_project` slugs the input) → name-or-id, any case, resolves across all 4 surfaces (REST /{id} + /{id}/context, MCP project_get + project_context). Commit `<hash>` `fix(sprint-105-projects-case-insensitive): name-or-id-any-case lookup, 4 surfaces (#105)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth on the container). Cairn #105 NORMAL — agent-facing dogfood (team-lead Rule#0-confirmed).

## What shipped (1 chokepoint → 4 surfaces + test)
| File | Change |
|---|---|
| `projects/service.py` (`get_project`) | `key = slug(project_id)` (the SAME `reader.slug` the keys are built with) before the dict lookup → "ClaudeManager"/"CLAUDEMANAGER"/"Claude Manager" all resolve to the canonical lowercase slug; `read_one(key, ...)` returns the canonical `status.id`. The single lookup chokepoint. |
| `projects/service.py` (`get_context`) | use `status.id` (canonical slug), NOT the raw input, for the `project_notes` tag lookup → a mixed-case query resolves BOTH the metadata AND the `project:<slug>`-tagged notes (the recheck-all-consumers — notes are tagged with the lowercase slug). |
| `projects/router.py` (`/{id}` + `/{id}/context`) | sharpened the not-found agent-error hint: "use the .id field from GET /projects (not .name); ids are matched case-insensitively". retryable:false. |
| `mcp_servers/read_server.py` (`project_get` docstring) | documents case-insensitive name-or-id; unknown → `{found:False, project_id}` (honest lean wrapper kept). |
| `tests/test_projects.py` (+N) | both-case→same-canonical · name-form→resolves · nonexistent→None/404+hint · MCP found:False · context-mixed-case→metadata+notes. |

## Design (LOCKED — one chokepoint, slug-the-input, canonical-id-returned, id-scheme-unchanged)
- **ONE chokepoint fixes 4 surfaces:** REST /{id} + /{id}/context + MCP project_get + project_context ALL route through `service.get_project` (and `get_context` which calls it). Slug the input there → all inherit case-insensitive name-or-id. No per-surface patching.
- **slug the INPUT, not a new dict:** the tracked keys are already lowercase slugs (`reader.slug(folder_name)`). Applying the SAME `slug()` to the INPUT (not lowercase-only) means "ClaudeManager", "CLAUDEMANAGER", AND a spaced/punctuated "Claude Manager" all match — using the existing slug fn so it can't drift from the key-building.
- **canonical id returned:** `read_one(key, ...)` → `status.id` is the canonical lowercase slug, regardless of the input's case. The id-scheme is UNCHANGED (slugs stay lowercase); only the MATCH is case-insensitive.
- **recheck-all-consumers (the subtle catch):** `get_context` uses `status.id` (canonical) for the notes tag-filter, NOT the raw mixed-case input → otherwise it'd resolve the metadata but MISS the `project:<slug>` notes (which are tagged lowercase). Both metadata + notes now resolve from any-case.
- **honest not-found:** a genuinely-missing id → REST 404 + the sharpened hint (use .id, case-insensitive); MCP {found:False} (lean wrapper #24). Not a silent null.

## Verification (Rule#0 — architect INDEPENDENT, restarted container, read-only)
- **architect 4-step (read FULL):** the chokepoint slug-the-input (same `from .reader import slug` — no drift); get_context uses canonical status.id for notes; both router hints sharpened; MCP docstring + lean {found:False}. ✅
- **🔴 INDEPENDENT live teeth (read-only, no writes):**
  - `claudemanager` / `CLAUDEMANAGER` / `ClaudeManager` (name) → all → canonical `id=claudemanager`. ✅
  - nonexistent → None (router 404s). ✅
  - MCP project_get(name)→found:True canonical; UPPER→found:True; bad→found:False (honest lean). ✅
  - get_context(name UPPER)→resolved, canonical id, notes via the canonical slug (metadata+notes). ✅
- **Suite:** `test_projects.py` = **81 passed** (#105's own file, all green). The full DEFAULT suite showed **3 failures — ALL #106-WIP** (backend was mid-#106 in the tree: `test_market_fng_honest` asOf-None→"" ×2 + `test_finance_mcp_shape` warning-count ×1 — its CODE changed, its TESTS not yet updated). Those 3 are on DISJOINT files (market/finance) from #105 (projects) → **#105 is independently committable** (surgical stage = the 5 #105 files only, NO #106 market/finance). The full-suite 0-failed holds once #106 lands its own test updates (flagged to backend). #105 itself introduces 0 failures. Never staged backend/data/; read-only verify (no live-store writes).

## 3 Gates
- **Gate 1 (API/MCP/agent):** case-insensitive name-or-id (4 surfaces); sharpened not-found hint (agent-actionable, retryable:false); MCP honest {found:False}; return shape + id-scheme unchanged. ✅
- **Gate 2 (Function):** the distinguishing teeth (both-case→canonical / name-form / bad→hint / MCP found:False / context-metadata+notes); independent live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged EXACTLY service.py + router.py + read_server.py + test_projects.py + end doc (NO #106/market-finance, no data/.env); commit format. ✅

## Assumptions (user-review)
- **the lookup slugs the input** (full `slug()`, not just lowercase) → name-in-any-form (spaces/punct/case) resolves. **How to change:** the `key = slug(project_id)` line in get_project.
- **canonical lowercase slug returned** (id-scheme unchanged; only MATCH is case-insensitive). **How to change:** n/a (intentional — stable canonical ids).
- **not-found hint names .id + case-insensitive, retryable:false.** **How to change:** the router agent-error hints.

## Notes
- Cairn #105 NORMAL — admin-lead dogfood (an agent using the human-readable `name` from projects_list → 404). backend-w3 built; architect committed (§3 sole-committer). The ONE-chokepoint fix (slug-the-input in get_project) covering 4 surfaces is the clean design — and the get_context canonical-slug catch (notes resolve too, not just metadata) is the recheck-all-consumers discipline. The architect pre-traced the chokepoint pre-dispatch so the fix landed minimal. Committed separately from #106 (market/finance, in flight). Read-only verify (no live-store seed/cleanup needed — a lookup fix).
