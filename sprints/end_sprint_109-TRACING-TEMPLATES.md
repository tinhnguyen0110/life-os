# end_sprint_109-TRACING-TEMPLATES — task template list (seed⊕override + reset + bulk) (Cairn #109, TRACING-UX T1)

> Result. /daily-tracing required typing 6 fields per new habit. Added a template list: 8 immutable SEED habits ⊕ a USER OVERRIDE table (edit/add/delete own + reset-to-default + bulk-delete), each item source-tagged. Commit `<hash>` `feat(sprint-109-tracing-templates): seed⊕override template list + reset + bulk-delete (#109)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT live teeth — merge + 🔴 SCOPED-reset proven activities-untouched). Cairn #109 TRACING-UX T1 (gates #110). user-CHỐT.

## What shipped (tracing module + MCP + tests)
| File | Change |
|---|---|
| `tracing/service.py` | `_SEED_TEMPLATES` (8 immutable habits) + `list_templates` (SEED⊕OVERRIDE merge: override-wins-on-seed-id / tombstone-hides-seed / user-only-appears / un-overridden-seed-appears, source-tagged) + upsert/delete/reset/bulk-delete. |
| `tracing/store.py` | new `tracing_template` table (idempotent CREATE TABLE IF NOT EXISTS, `hidden` tombstone col) + CRUD; 🔴 reset/delete/bulk DELETE FROM tracing_template ONLY (never tracing_activities — #72). |
| `tracing/{schema,reader,router}.py` | Template/TemplateInput; GET /templates · PUT /{id} · DELETE /{id} · POST /reset · POST /bulk-delete {ids}. |
| `mcp_servers/{read_server,tracing_server}.py` + CATALOG.md | `tracing_templates` (read, lean, parity #24); TOOLS 46→47, tracing_server 2→3. |
| tests (+22) | merge/override/tombstone/reset/bulk + scoped-activities-intact + migration-idempotent + MCP≡REST. |

## Design (LOCKED — seed⊕override, scoped-reset, bulk-action, prefill-only)
- **SEED (immutable in code) ⊕ OVERRIDE (SQLite):** seed = 8 hard-coded Vietnamese-habit prefills; override = the `tracing_template` table. Merge rules in `list_templates` (override wins on seed-id, tombstone hides a seed, user-only id appears, source-tagged). Seed not editable (user "edits a seed" = an override with the same id).
- **🔴 SCOPED reset/delete/bulk (the #72 load-bearing):** reset = `DELETE FROM tracing_template` ONLY → back to pure seed; NEVER touches tracing_activities/tracing_logs (the user's real habits + history). Proven LIVE: activities 9→9 unchanged across a reset.
- **bulk-action (admin-lead fold-in, user "có bulk edit nữa chứ"):** `POST /tracing/templates/bulk-delete {ids}` (one-call, agent-first — backend's choice over FE-loop); idempotent (empty→no-op, missing-id→skip). YAGNI-bounded: bulk-ACTION only (delete/reset), NOT bulk-field-edit, NOT bulk-on-real-activities.
- **prefill-only:** templates don't create activities — they prefill the form → the existing POST add() unchanged (ActivityInput untouched). No versioning/audit (single-user).

## Verification (Rule#0 — architect INDEPENDENT, restarted container)
- **architect 4-step (read FULL):** the merge logic (override/tombstone/user-only/seed cases); separate tables (tracing_template vs tracing_activities, store.py:45 vs :22); the count-assert reconcile (46→47, lineage comment); 🔴 read_server.py diff is PURELY #109 (tracing_templates only — NO #111/channel content; the shared-file serialization confirmed clean before commit). ✅
- **🔴 INDEPENDENT live teeth:** list→8 seed (all source=seed); upsert seed 'uong-nuoc'→source=user goal=99 (override wins); reset→8 pure-seed; 🔴 SCOPED: activities 9→9 UNTOUCHED across reset (the #72 safety holds). ✅
- **Suite:** the #109 file + count-assert files (test_tracing_templates/tracing_mcp_server/mcp_read/mcp_http/finance_mcp_shape) = 170 passed; FULL DEFAULT = **<COUNT>** forward AND reverse; live store left clean (throwaway override reset away; never staged backend/data/).

## 3 Gates
- **Gate 1 (API/MCP/agent):** 5 endpoints + MCP tracing_templates (lean, parity #24); merge source-tagged; bad upsert→422; bulk idempotent; honest. ✅
- **Gate 2 (Function):** the teeth (merge/override/tombstone/reset/bulk + SCOPED-activities-intact + migration-idempotent-on-migrated-db); independent live; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent live; staged the #109 files (tracing/* + mcp + CATALOG + tests + count-asserts) — NO #111/#112, no data/.env; read_server.py confirmed #109-only (shared-file serialization); commit format. ✅

## Assumptions (user-review)
- **8 SEED templates immutable in code; user-edit = an override (same id).** **How to change:** `_SEED_TEMPLATES`; or make seed editable (NOT recommended — the override model is cleaner).
- **reset/delete/bulk SCOPED to tracing_template** (real activities never touched). **How to change:** n/a (intentional safety — #72).
- **bulk = action-only (delete/reset), one-call endpoint.** **How to change:** add bulk-field-edit if the user asks (YAGNI now).

## Notes
- Cairn #109 TRACING-UX T1 — user-CHỐT /daily-tracing UX. backend-w3 built (incl admin-lead's bulk-edit fold-in); architect committed (§3 sole-committer). 🔴 **Shared-file serialization (the time-sensitive commit-order):** #109 touches mcp_servers/read_server.py + tracing_server.py; #111 (channels, in-flight) may also touch read_server.py → committed #109 FIRST (its read_server state final, confirmed #109-only via git diff --cached) so #111's edits layer cleanly on top (the content-diff-not-just-filenames lesson). GATES #110 (the FE form needs the picker — frontend-w3-2). Committed in arrival order (serial committer); #111/#112 still building.
