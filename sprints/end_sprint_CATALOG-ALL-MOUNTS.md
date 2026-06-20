# end_sprint_CATALOG-ALL-MOUNTS — list_tools_catalog walks ALL 6 mounts (Cairn #32)

> Result. Backend-only (team-lead dispatched directly during the docs sprint). Commit `<hash>` `feat(sprint-CATALOG-ALL-MOUNTS)`. Status: ✅ all 3 gates pass. 🏁 The last autonomously-dispatchable item — after this the board is COMPLETE except the user-gated items.

## What shipped
| File | Change |
|---|---|
| `mcp_servers/read_server.py` | `_CATALOG_MOUNTS` (the 6 mounts mirroring main._MCP_MOUNTS) + `list_tools_catalog()` rewritten to walk EVERY mount (lazy-import per mount for metadata only — no-write gate preserved); counts gain `byMount` + `allMounts` + an honest overlap `note` while KEEPING back-compat read/write/total. |
| `mcp_servers/CATALOG.md` | hand-synced — now covers wiki / finance / reminders (+ the missing reminders section added). |
| `backend/tests/test_mcp_read.py` | +test_catalog_walks_all_mounts + test_catalog_mounts_in_sync_with_main (the teeth) + test_catalog_finance_double_listed_under_read_and_finance. |

## The shape (team-lead-confirmed live)
- catalog walks all 6: read(daily_brief) + write(propose_decision) + wiki-read(wiki_context, wiki_tree) + wiki-write(propose_note) + finance(finance_overview) + reminders(reminder_create, reminders_list).
- `{capabilityBoundary, counts, tools}`; counts = back-compat read/write/total (41/4/45) KEPT + byMount {read:41, write:4, wiki-read:11, wiki-write:6, finance:15, reminders:3} + allMounts:80 + the honest "per-mount counts overlap (reference-imports), allMounts≠distinct-total" note.

## Verification (Rule #0 — architect 4-step + team-lead container)
- **architect 4-step (full fn):** the write/wiki-write modules are imported LAZILY via importlib INSIDE list_tools_catalog (grep-confirmed ZERO write/propose/wiki-write import at the read-server module top-level) → the no-write gate stays pristine (nothing write-capable bound in the read namespace; metadata read, fns never invoked). The byMount `note` is honest (states the reference-import overlap; allMounts = listing length not distinct). Back-compat counts.read/write/total keep their historical meaning. The sync-guard `test_catalog_mounts_in_sync_with_main` asserts _CATALOG_MOUNTS modpaths == main._MCP_MOUNTS modpaths (set-equal) → a new mount not added FAILS RED. byMount counts assert == live TOOLS (not hardcoded); finance double-listing asserted as intended.
- **team-lead independent container:** all 6 mounts' signature tools present; the structure + counts exactly the agreed shape; the completeness guard has teeth (a new app mount not in the catalog FAILS RED); 1832 passed (+3), mypy clean, no-write-gate preserved (lazy imports leak nothing into rs namespace); CATALOG.md hand-synced.

## 3 Gates — ALL PASS
- **Gate 1 (API):** list_tools_catalog now complete across all 6 mounts; envelope/structure agreed; the catalog reads-only (grants nothing). ✅
- **Gate 2 (Function):** lazy-import preserves the no-write gate (AST test still passes); sync-guard teeth (new mount → RED); byMount == live counts; honest overlap note; 0 errors. ✅
- **Gate 3 (Sprint):** end-doc; full-fn spot-check (no-write gate + honest note verified); architect 4-step + team-lead container; commit format; staged ONLY #32 files — the held #31 FE + data/template EXCLUDED. ✅

## Assumptions (user-review)
- **list_tools_catalog walks ALL 6 mounts** (read/write/wiki-read/wiki-write/finance/reminders) via _CATALOG_MOUNTS mirroring main._MCP_MOUNTS (kept in sync by the test-gate); counts keep back-compat read/write/total + add byMount/allMounts with an honest overlap note. **How to change:** _CATALOG_MOUNTS.
- per-mount counts OVERLAP by design (reference-imported domain tools); allMounts ≠ distinct total — the honest "what each agent sees per mount" view (not inflation).

## Notes
- Backend-only; separate commit. CATALOG.md (synced here, NOT the earlier team-lead-owned exclusion — this commit's CATALOG.md change is the #32 hand-sync, part of the sprint). The held #31 FE files EXCLUDED (clean directory split, still user-held).
- 🏁 The LAST autonomously-dispatchable item. Board now COMPLETE except the user-gated items: #31 (FE, user's UI look) + the next-direction gaps (G-HABIT / G-ACCOMPLISH, surfaced by dogfood). #11/#6/#7 deferred/iceboxed. The session's substantive arc is done — the team can go quiet + await the user.
