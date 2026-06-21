# end_sprint_36-BRIEF-WIKICONTEXT — daily_brief enriched from the wiki graph (Cairn #36)

> Result. daily_brief now carries an ADDITIVE `wikiContext` block — recent wiki note activity (create|edit) + notable clusters — pulled DETERMINISTICALLY from the existing wiki reader (recent_activity + detect_clusters), NO LLM. The existing 5-rule priorities/summary/stale are UNCHANGED (backward-compat). honest-mirror: no activity → empty lists; wiki down → empty lists + a warning (present, honest-blind, never faked). Commit `<hash>` `feat(sprint-36-brief-wikicontext): daily_brief wiki-graph section (#36)`. Status: ✅ verified (backend-w3 built; architect 4-step + INDEPENDENT fail-soft re-run + suite). Batch 2 Lane B (∥ #35, committed serially after #35 a89b4c7).

## What shipped (3 brief files + 1 new test)
| File | Change |
|---|---|
| `brief/schema.py` | NEW `RecentNote` (noteId/title/kind:Literal[create\|edit]/ts) + `ClusterRef` (label/noteCount) + `WikiContext` (recentNotes/clusters/asOf/source:Literal[wiki]/warnings). `Brief.wikiContext: WikiContext \| None = None` — ADDITIVE OPTIONAL (old consumers ignore an unknown field; the existing 5 fields unchanged). |
| `brief/reader.py` | `Sources.wiki: dict \| None`; `pull()` adds a fail-soft wiki pull → `{recentOps: wiki_reader.recent_activity(20), clusters: wiki_reader.detect_clusters()}` (REUSE — no recompute, no new read path). Wiki read raises → `src.wiki=None` + a warning (the rest of pull intact). |
| `brief/service.py` | NEW `_build_wiki_context(src, generated_at)` — deterministic: filter recentOps to create\|edit (delete/merge excluded — note gone), defensive None-noteId skip, cap WIKI_RECENT_CAP=7; clusters mirror detect_clusters (suggestedTitle→label, size→noteCount), cap WIKI_CLUSTER_CAP=5. `src.wiki is None` → empty-lists + "wiki source unavailable" warning (honest-blind). `generate_brief` builds + attaches wikiContext; the existing source/summary/priorities/stale/warnings UNCHANGED. |
| `tests/test_brief_wiki_context.py` (NEW) | populated (value-by-value) / honest-empty / fail-soft wiki-down / excludes delete+merge / caps. |

## Design (LOCKED — additive, deterministic, honest, reuse)
- **ADDITIVE + backward-compat:** `wikiContext` is a NEW optional field; the existing 5-rule priorities + summary + stale + `source="template"` are byte-identical. Old consumers ignore the field.
- **DETERMINISTIC (no LLM):** pulls the wiki reader's existing `recent_activity` (op-log feed) + `detect_clusters` (MOC candidates) — no model summary (honest-mirror).
- **honest-mirror:** no activity → empty lists (not None-the-section, not fabricated). wiki read raised → empty lists + a warning (present, honest-blind). create|edit only (delete/merge have no live note).
- **reminders-dedup (DECIDED + logged):** NO reminders block in wikiContext — the existing `_reminders_priority` rule (reader.pull already pulls `rem.list_reminders("undone")`) already covers due/overdue reminders. Adding a reminders block here would duplicate it. wikiContext = recentNotes + clusters ONLY.
- **both-consumers (DECIDED + logged):** life_brief in read_server NOT modified — its existing `_brief_wiki` already surfaces wiki recentActivity to the consumer-agent, so a second wikiContext there would be a dup. The REST/MCP daily_brief carries wikiContext; life_brief's wiki coverage is its own existing section.

## Verification (Rule#0 — architect INDEPENDENT)
- **architect 4-step (read FULL functions):** additive optional field (backward-compat — old 5 fields unchanged) ✅; reader reuses wiki surfaces + fail-soft (try/except → warning, rest of pull intact) ✅; `_build_wiki_context` honest (None→empty+warning, create|edit filter, caps, mirrors detect_clusters shape) ✅; life_brief/read_server clean (no dup) ✅; no reminders dup ✅.
- **architect INDEPENDENT fail-soft re-run (own throwaway):** forced `wiki_reader.recent_activity` to RAISE → the brief STILL builds, source=="template" (backward-compat), priorities intact, wikiContext present + honest-blind (empty lists + "wiki source unavailable" warning), the failure surfaced in brief.warnings. → fail-soft + backward-compat REAL. (Throwaway cleaned up.)
- **Suite:** the new test (populated/honest-empty/fail-soft/exclude-delete-merge/caps) green; 92 brief tests pass (new + all existing = backward-compat); DEFAULT (`-m 'not slow'` deterministic) = **2126 passed / 6 skipped / 3 deselected / 0 failed** forward AND reverse (identical → no isolation leak; 2121→2126 = +5 wiki-context tests).

## 3 Gates
- **Gate 1 (API/MCP):** wikiContext additive + agent-readable (recentNotes/clusters/asOf/source/warnings, self-describing); honest-empty + honest-blind; daily_brief envelope unchanged. ✅
- **Gate 2 (Function):** distinguishing tests (populated value-by-value / honest-empty / fail-soft / exclude-delete-merge / caps); independent fail-soft re-run; backward-compat (5-rule unchanged); 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; architect 4-step + independent fail-soft; counts 2121→2126; staged set EXACTLY brief/* + the new test (the shared reader/__init__ alias already landed in #35 a89b4c7 — NOT in #36's diff); commit format. ✅

## Assumptions (user-review)
- **wikiContext = recentNotes + clusters ONLY (no reminders block)** — the existing `_reminders_priority` rule already covers due reminders; a reminders block here would duplicate it. **How to change:** add a reminders projection in `_build_wiki_context` (reusing `src.reminders`, already pulled).
- **life_brief NOT modified** — its existing `_brief_wiki` already surfaces wiki recentActivity to the consumer-agent (no dup). **How to change:** add a wikiContext section to life_brief in read_server if a richer consumer-agent surface is wanted.
- **Caps:** recentNotes ≤ 7, clusters ≤ 5. **How to change:** WIKI_RECENT_CAP / WIKI_CLUSTER_CAP in service.py.
- **create|edit only** (delete/merge excluded — no live note to surface). **How to change:** the kind filter in `_build_wiki_context`.

## Notes
- Cairn #36 Batch 2 Lane B (∥ #35). backend-w3 built; architect 4-step + committed (§3 sole-committer, serial — AFTER #35 a89b4c7). The shared `reader/__init__.py` recent_activity alias already landed clean in #35 (b92a7bd's `_recent_activity` pre-exists → valid alias, #35 imports clean) → NOT in #36's diff. Deterministic, additive, honest, reuses the wiki reader. Next: #84 (dev_activity you=0 bug, backend implementing in parallel — lands after #36) → then #78 last (risk-assess).
