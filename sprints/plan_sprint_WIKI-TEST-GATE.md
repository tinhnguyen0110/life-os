# Sprint WIKI-TEST-GATE — codify REST≡MCP byte-identical across the wiki surface (Cairn #24)

> Created 2026-06-21 by architect. LANE B (backend-only; runs while #31 FE held for the user). The standing #24 invariant — referenced by the whole wiki batch (#19-23,26) — CODIFIED as a guard test so the REST≡MCP drift class can NEVER ship silently again. The wiki surface is now stable at 11 MCP read tools (post-fc99e5c) → the right time.

## Objective
This session we shipped the wiki_tree `{tree:}` wrapper drift (#19) — a REST≡MCP divergence a self-report MISSED; only team-lead's live byte-compare caught it. #24 = a standing parametrized test-gate asserting every wiki capability's REST endpoint output == its MCP tool output (modulo the DOCUMENTED MCP conventions). Then that drift class FAILS RED in CI/local — impossible to ship silently.

## The invariant (precise — this is the whole point)
For each wiki capability with BOTH a REST endpoint + an MCP tool: **the REST `data` payload == the MCP tool result PAYLOAD, byte-identical** (json.dumps sort_keys=True equal) — AFTER normalizing the DOCUMENTED, intended per-surface conventions:
- **MCP `{found}` existence wrapper** — wiki_get_note (full → `{found, note}`; outline/section → `{found, **view}`), wiki_context (`{found, note_id, ...}`). REST omits `found` (404s instead). NORMALIZE: strip the MCP `found` flag, then compare the PAYLOAD (the byte-identical-payload check — NOT a naive top-level dict-equal, which the #19 self-report wrongly did and missed the wrapper).
- **inline `warning` / `warnings`** — the house convention (some surfaces add a warning key). Accept/normalize per the documented convention.
This is the lesson from #19 (the self-report compared the inner tree, missed the wrapper) + #21+#22 (the `{found}` is intended, payload matches) — encode BOTH: strip the intended wrapper, then the payloads MUST be byte-identical.

## The pairing map (backend resolves exact REST paths — these are the pairs)
| MCP tool | REST | convention to normalize |
|---|---|---|
| wiki_search | GET /wiki/search | — (both {results}) |
| wiki_overview | GET /wiki/overview | warning |
| wiki_inbox | GET /wiki/inbox | — |
| wiki_tree | GET /wiki/tree | NO wrapper (the #19 case — must stay bare) |
| wiki_get_note (full/outline/section) | GET /wiki/notes/{id}?mode= | strip {found}; section: sectionFound stays |
| wiki_context | GET /wiki/notes/{id}/context | strip {found} |
| wiki_recent_ops | (backend: confirm the REST pair) | — |
| wiki_clusters | GET /wiki/clusters | — |
| wiki_proposal_status | GET /wiki/proposals/{id} | — |
| wiki_list_proposals | GET /wiki/proposals | — |
- wiki_verify_citations is POST (not a GET pair) — include if it has a REST POST mirror; else document as MCP-only (no REST pair → exempt, but ASSERT the exemption explicitly so it's intentional not forgotten).

## Logic/Algorithm
- A PARAMETRIZED test over the pairing map: for each (mcp_tool, rest_endpoint, normalize_fn), call BOTH against the SAME fixture vault → assert `json.dumps(normalize(mcp_result), sort_keys=True) == json.dumps(rest_data, sort_keys=True)`.
- **Coverage-completeness assertion:** the test ALSO asserts every MCP read tool in the TOOLS map is EITHER in the pairing map OR in an explicit MCP-ONLY exempt-list (with a reason). So adding a new wiki MCP tool WITHOUT a REST mirror (or without consciously exempting it) FAILS RED — the gate can't be silently bypassed by a future tool.
- Reuse the existing wiki test fixtures (the seeded vault).

## HARD GATE (distinguishing — the gate must PROVE it catches drift)
- Every paired capability: REST data == MCP payload byte-identical (after the documented normalize). All 11 covered or explicitly exempted.
- **THE distinguishing (mandatory — proves the gate has teeth):** a deliberately-DRIFTED fixture (e.g. wrap one MCP result in a spurious `{tree: ...}` like the #19 bug, or drop a field) MUST make the gate FAIL RED. A gate that can't fail on a planted drift is worthless. Include this as a test (xfail/expected-fail, or a unit test of the compare-helper showing it rejects a drift).
- Coverage-completeness: a new TOOLS entry without a pair/exempt → RED.
- pytest green (the gate itself passes on the current honest surface), mypy clean.

## Baseline
pytest 1812 (post-fc99e5c). Keep 0-failed (the new gate ADDS tests; the surface is honest so they pass).

## Assumptions (user-review)
- **REST≡MCP byte-identical is now a CODIFIED guard test** across the wiki surface — every paired capability's REST data == MCP payload (after stripping the documented {found} wrapper + warnings convention). A new wiki MCP tool without a REST mirror or explicit exemption FAILS the gate. **How to change:** the pairing map + the normalize conventions in the test.
- the {found} existence-wrapper + inline warnings are the INTENDED per-surface MCP conventions (normalized, not flagged as drift); wiki_tree must stay bare (no {tree} wrapper — the #19 regression guard).

## Notes
- LANE B, backend-only; separate commit `feat(sprint-WIKI-TEST-GATE)`. Runs while #31 FE held for the user.
- This codifies the #24 invariant the whole wiki batch referenced — write once, guards forever. After #24, the wiki batch (#19-24,26) is COMPLETE.
- The distinguishing (a planted drift must fail) is non-negotiable — a green gate that can't catch the #19 bug is theater.
