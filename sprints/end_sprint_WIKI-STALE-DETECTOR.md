# end_sprint_WIKI-STALE-DETECTOR — read-only wiki staleness flags (Cairn #41, SPEC A6)

> Result. A read-only staleness + contradiction-candidate detector, designed+validated by architect (ref_41/) → folded+committed by backend (sole wiki-tree implementer/committer, post the parallel-build tangle). Commit `<hash>` `feat(sprint-WIKI-STALE-DETECTOR)`. Status: ✅ all 3 gates pass.

## Objective (met)
The wiki had no stale/contradiction detection. #41 = a READ-ONLY detector (NO auto-fix) that flags (1) STALE notes (evergreen + idle > threshold + load-bearing) + (2) contradiction-candidates (v1 deterministic, no AI) for human/agent review.

## What shipped
| File | Change |
|---|---|
| `modules/wiki/reader/stale.py` (NEW) | `stale_notes(threshold_days, now=injectable)` — STALE = evergreen + updated>N days + ≥1 inbound; contradiction-candidate v1 = mutually-linked verified↔candidate pair. Honest-empty; never crashes on a bad timestamp; `now` injectable for testable days-since. |
| `modules/wiki/store/queries.py` | `inbound_counts()` (ONE GROUP BY — the bulk inbound-degree, NOT per-note backlinks; the perf-correct path) + `mutual_link_pairs()` (self-join, a<b deduped) + exports. |
| `modules/settings/schema.py` | `staleThresholdDays` (default 90, ge=1) on AppConfig + AppConfigPatch (the `idleThresholdDays` precedent — a config knob, user-tunable). |
| `modules/wiki/reader/__init__.py` | export `stale_notes`. |
| `modules/wiki/router.py` + `mcp/read_server.py` | REST `GET /wiki/stale` + MCP `wiki_stale` — BOTH call `reader.stale_notes(threshold_days=get_config().staleThresholdDays)` → byte-identical (#24). wiki-read MCP count 12→13. |
| tests + gate | test_wiki_stale.py (12 — the 4 staleness axes + contradiction v1) + test_settings_api (defaults +staleThresholdDays, kept #33's alertMailThreshold) + test_wiki_mcp_read (tools-key-set +wiki_stale) + test_mcp_http/test_mcp_read (count→13) + test_wiki_rest_mcp_parity_gate (+wiki_stale pair, wiki-read 13) + CATALOG.md (wiki-read 13 + the wiki_stale row). |

## The detector (DESIGN LOCKED — decide-and-log)
- **STALE = status=='evergreen' AND daysSince(updated) > staleThresholdDays AND inboundCount ≥ 1.** fleeting/developing NOT flagged (expected churn / in-progress); orphan-evergreen (0 inbound) NOT flagged (that's overview.orphans' concern). 4 distinguishing axes: age / recency / status / inbound.
- **Contradiction-candidate v1 (deterministic, NO AI):** a mutually-linked pair with divergent trust tier (verified↔candidate) → a human-review FLAG, NOT an AI contradiction claim (honest-mirror — no AI judges content).
- **PERF:** uses `inbound_counts()` (one GROUP BY) joined in-memory against `all_notes()` — NOT per-note `backlinks()` (which builds wasted snippets → O(n) queries). 2 queries, not n×backlinks.
- "pain open too long" is OUT — no pain concept in the wiki schema (pains are projects/career, a different module); #41 scopes to NOTE staleness (verify-the-schema-before-building).

## Process note (the parallel-build tangle → clean recovery)
architect built+validated #41 IN PARALLEL with backend's #34 on the SAME wiki-reader tree → a shared-tree co-mingle (architect's misjudgment: NEVER implement in a tree backend is editing). Caught before any tangled commit; architect reverted #41 (zero residue, #34 intact, verified) + preserved the validated code in `sprints/ref_41/`. team-lead's call: backend = sole wiki-tree implementer/committer → backend folded the ref byte-faithful + added the held REST/MCP/gate. The validated work was NOT wasted (restored from ref, 12 tests green) + the one-editor-per-shared-tree principle held.

## Verification (Rule #0 — backend fold + architect 4-step)
- **backend fold:** ref restored byte-for-byte (diff -q vs ref → IDENTICAL); the 7-step checklist complete; 1877 passed / 0 failed (baseline 1864 + 12 + 1); mypy clean; LIVE /wiki/stale == MCP wiki_stale byte-identical, wiki-read TOOLS=13, thresholdDays:90 from the live config knob.
- **architect 4-step:** ref byte-faithful (diff -q IDENTICAL); the 14-file dirty set is #41-only (no #33/#34 residue — the apparent residue was already-committed context lines); settings-test has BOTH knobs (the reconcile); REST `/wiki/stale` + MCP `wiki_stale` BOTH call reader.stale_notes with the SAME config knob (byte-identical by construction); inbound_counts is the bulk GROUP BY (perf-correct); git-status-after-stage = ZERO left-dirty (the #34 lesson); exactly 14 staged, no FE/template/data/.env leak.

## 3 Gates — ALL PASS
- **Gate 1 (API):** REST /wiki/stale == MCP wiki_stale byte-identical (#24, added to the parity gate); envelope; read-only (no mutation). ✅
- **Gate 2 (Function):** the 12 distinguishing tests (4 staleness axes + contradiction v1 mutual/same-tier/one-way + threshold + sorted + honest-empty + malformed-ts-safe); the perf bulk-count; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; backend fold + architect 4-step; commit format; git-status-clean (#34-lesson); staged #41-only (post #33/#34, one-lane-at-a-time); the parity-gate + key-set + count reconciles all included (no broken-intermediate). ✅

## Assumptions (user-review)
- **wiki stale = evergreen + updated>staleThresholdDays(default 90) + ≥1 inbound** — a load-bearing note gone quiet. fleeting/developing NOT flagged; orphan-evergreen is overview.orphans. **How to change:** the `staleThresholdDays` knob + the predicate in stale_notes.
- **contradiction-candidate v1 = mutually-linked verified↔candidate** (deterministic human-review FLAG, NOT an AI claim). **How to change:** the heuristic in stale_notes (richer detection = later iteration).
- read-only detector, NO auto-fix, on-demand (no routine v1); "pain open too long" OUT (not in wiki schema).

## Notes
- backend = sole wiki-tree implementer/committer (the principle after the parallel-build tangle); architect designed+validated+reviewed (ref_41/ + 4-step). architect committed per CLAUDE.md §3 (architect owns commit+push).
- Wiki-read MCP surface now 13 tools (12 post-#34 + wiki_stale). Pipeline after: #45 (trustTier) → #42 (project-memory).
