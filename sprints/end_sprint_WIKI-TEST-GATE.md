# end_sprint_WIKI-TEST-GATE — codify REST≡MCP byte-identical (Cairn #24)

> Result. LANE B (backend-only, TEST-only — ran while #31 FE held for the user). The standing #24 invariant — referenced by the whole wiki batch — CODIFIED as a parametrized guard test with REAL TEETH (a planted #19-class drift FAILS RED). Commit `<hash>` `feat(sprint-WIKI-TEST-GATE)`. Status: ✅ all 3 gates pass. 🏁 **The wiki batch (#19-24,26) is COMPLETE.**

## Objective (met)
#19 shipped the wiki_tree `{tree:}` wrapper drift — a REST≡MCP divergence a self-report MISSED (it compared the INNER payload, not the full result); only team-lead's live byte-compare caught it. #24 = a standing parametrized gate asserting every wiki capability's REST output == its MCP PAYLOAD byte-identical (after the documented conventions), so that drift class FAILS RED forever — impossible to ship silently again.

## What shipped
| File | Change |
|---|---|
| `backend/tests/test_wiki_rest_mcp_parity_gate.py` (NEW, 309 lines, 17 tests) | the parametrized REST≡MCP byte-identical gate + the planted-drift teeth + coverage-completeness + the #19 bare-tree regression guard. TEST-only — NO wiki source change. |

## The gate (what it asserts)
- **Parametrized byte-identical** over the pairing map (search, overview, inbox, tree, clusters, get_note full/outline/section, context, list_proposals, verify_citations): REST `data` == MCP PAYLOAD via `json.dumps(sort_keys=True)` equality (the FULL compare — NOT naive top-level, which is the #19 mistake), after per-pair normalize.
- **Documented conventions normalized** (each explicit): strip the MCP `{found}` existence-wrapper (REST 404s instead); unwrap MCP `{results}`/`{overview}`/`{note}` wrappers REST doesn't have; drop volatile `stats.asOf`; `warning` compared per-surface; `sectionFound` stays (payload); **wiki_context is the exception** (REST /context returns reader.context() verbatim incl `found` → no strip).
- **wiki_tree must stay BARE** — `test_tree_stays_bare_no_wrapper` (the explicit #19 regression guard: no `{tree}` wrapper on either surface).
- **Coverage-completeness** — `test_every_mcp_tool_is_paired_or_exempt`: every TOOLS read tool is PAIRED or in `EXEMPT_MCP_ONLY` (with a reason); also catches STALE entries (a removed tool left in the map). A new wiki tool without a pair/exempt → RED (the gate can't be silently bypassed).
- **Anti-shadow** — `test_pair_ids_all_collected_no_shadow`: unique pair ids + collected == pair count (duplicate-test-name-silent-shadow guard).

## THE TEETH (the most important deliverable — verified genuine, not self-confirming)
- `test_compare_helper_REJECTS_planted_wrapper_drift`: `byte_identical({"tree": honest}, honest) is False` (the exact #19 wrapper shape) + a control `byte_identical(honest, honest) is True` (so it's not trivially always-False).
- `test_compare_helper_REJECTS_dropped_field`: a dropped field AND a changed value → False.
- `test_gate_fails_red_on_a_drifted_pair`: END-TO-END — the real honest tree pair is byte-identical TODAY (precondition asserted), then the #19 `{tree:}` wrapper is planted on the MCP side and the gate is asserted to return False. Proves the GATE (not just the helper) fails on a real-pair drift.
→ These have real teeth: they assert `is False` on a KNOWN drift while controls assert `is True` on identity — if the helper were broken to always-True, they go RED.

## The exemptions (honest, reasoned — not over-exemption hiding drift)
- `wiki_recent_ops`: no REST GET pair (op-log is MCP-only; the REST activity feed is a different module/shape).
- `wiki_proposal_status`: intentional LEAN agent projection (curated camelCase subset from proposals_store) vs REST's RAW proposals_service row — a by-design surface difference, NOT a drift.

## Verification (Rule #0 — architect 4-step + team-lead container)
- **architect 4-step (full file):** the compare helper is a real FULL canonical compare (not top-level); the planted-drift tests are GENUINE teeth (assert is-False on a KNOWN #19 wrapper + dropped field + changed value, with is-True identity controls — not self-confirming); coverage-completeness is bidirectional (missing + stale); the 2 exemptions are legitimate by-design differences with reasons; normalizers match the documented conventions incl. the wiki_context REST-exception nuance; anti-shadow present. 17 passed.
- **team-lead independent container:** ran + inspected the file (309 lines, 17 passed); confirmed the teeth (planted wrapper / dropped field / drifted-pair all REJECT), the bare-tree guard, coverage-completeness, anti-shadow; green on the honest surface, rejects drift on the planted fixtures. TEST-only, no wiki source change.

## 3 Gates — ALL PASS
- **Gate 1 (API):** N/A direct (test-only) — but the gate ITSELF now asserts every wiki REST==MCP payload byte-identical (the API parity is now codified). ✅
- **Gate 2 (Function):** the gate's teeth proven (planted drift FAILS RED + honest passes); coverage-completeness; anti-shadow; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-file spot-check; architect 4-step + team-lead container; commit format; staged ONLY the gate file + 2 docs — CATALOG.md (team-lead's) + the held #31 FE files EXCLUDED; no data/template. ✅

## Assumptions (user-review)
- **REST≡MCP byte-identical is now a CODIFIED standing guard test** across the wiki surface — a future wiki MCP tool without a REST mirror or explicit exemption FAILS the gate; a wrapper/field drift on any pair FAILS RED. **How to change:** the pairing map + EXEMPT_MCP_ONLY + the normalize conventions in the test.
- 2 documented MCP-only exemptions (recent_ops no-REST-pair, proposal_status lean-vs-raw by design); wiki_context REST includes `found` (no strip — the one pair that doesn't).

## Notes
- LANE B, backend-only, TEST-only; separate commit. CATALOG.md is team-lead's (excluded). The #31 FE files (held for the user) excluded (clean directory split).
- 🏁 **The WIKI BATCH (#19, #20, #21, #22, #23, #24, #26) is COMPLETE** — write-through + link-correctness + tree-meta + get-modes + ranked-search + context-consolidation + the standing REST≡MCP gate. The wiki is now agent-first + regression-proofed.
- Remaining board: #31 (user-held UI), docs #3/#10, domain-decisions #11/#12, #32 (catalog-coverage, low), icebox.
