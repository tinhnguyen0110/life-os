# Sprint A5 — END · Security audit (clean) + refactor consciously DEFERRED

> Scope revised mid-sprint (decide-and-log): the store.py refactor was APPROVED then DEFERRED on the merits
> (backend raised the risk/value point, architect + team-lead agreed). A5 ships as security-audit-only — a
> complete, legitimate A5. No production code change.

## Security audit — ✅ COMPLETE, all CLEAN (verified, not assumed)

Read-only scan of `modules/`, `core/`, `store/`. life-os is single-user / no-auth / localhost — fewer attack
surfaces by design, but each was verified rather than assumed:

1. **Secret hardcode** — grep for `api_key`/`secret`/`token`/`password` literals in source: **NONE**. No credentials
   in code (no-auth app; nothing to leak). ✅
2. **SQL injection** — only TWO f-string SQLs in the codebase (`store.py:611` `all_notes`, `:697` `edges_among`),
   both safe: `{col}` is whitelisted to `id`/`created` (not user input); `edges_among` builds `{placeholders}` as
   `?` marks with `int()`-coerced ids bound separately. ALL value-bearing queries use `?` parameters. The FTS
   user-`q` goes through `_sanitize_fts_query` (tokenize + quote, never raw). **CLEAN.** ✅
3. **Path traversal** — `note_rel_path` coerces `int(note_id)` (a `../` payload can't survive int()). AND md_store
   has an explicit containment guard: `_resolve_under_root` resolves the path + raises `MdStoreError` if it escapes
   DATA_DIR. Defense-in-depth. **CLEAN.** ✅
4. **MCP least-privilege** — the read/write capability split is proven by the AST tests (15 read + 14 write) AND
   re-asserted at runtime by the A3 reliability harness (`run_fail_closed_check`): read server has no write/mutate/
   enqueue symbol; write server is enqueue-only (`create_proposal`, no accept/mutate). **HOLDS.** ✅

→ **No vulnerabilities found.** The audit finding IS the deliverable; no code change.

## Refactor — consciously DEFERRED (documented, not lost)

Kickoff found 3 files >500 LOC: `wiki/store.py` (752), `service.py` (601), `reader.py` (531). Recommendation
was a single conservative split of `store.py` (skip the other two as cohesive). team-lead initially approved,
then **reversed on the merits** after backend raised the risk/value point:

- **Why deferred:** the split is pure cleanup (ZERO feature value) and the HIGHEST-regression-risk change of the
  whole A1→A5 run — `store.py` is load-bearing (imported by service / reader / proposals_service / sync_store /
  both MCP servers). Risk/value is poor for a 1-dev app. North-star "don't refactor for its own sake": a working,
  tested, broad-but-COHERENT 752-LOC data layer is SIMPLER to leave than to split into 3 cross-importing files.
- **The analysis is preserved** (the split design, if ever needed): `store.py` → `store.py` (core: schema +
  cache CRUD + id-gen + op_log + md pass-throughs) + `store_links.py` (edge-graph + aliases + D6 redirects) +
  `store_search.py` (FTS5 + graph-aggregate queries). Same connection + `_lock`, pure move, count-identity gate (257 wiki tests).

### TRIP-WIRE to revisit the deferral
Split `store.py` when EITHER:
- it exceeds **~1000 LOC** (the broad-but-coherent argument weakens as it grows), OR
- a real cohesion problem bites (e.g. a change to the link-graph keeps forcing edits to unrelated FTS code).
The natural seams are **links** (edge-graph/aliases/redirects) and **FTS/search** — split those out first.

## Assumptions (user-review) — A5
1. **A5 = security-audit-only; store.py refactor DEFERRED** (decide-and-log scope reversal). — why: cleanup with
   zero feature value + highest regression risk in the backlog; poor risk/value for 1-dev. — to revisit: the
   trip-wire above (store.py >1000 LOC OR a cohesion pain).
2. **Security audit CLEAN** — no secrets, parameterized+whitelisted SQL, path-containment, MCP least-privilege.
   Re-run the audit if auth / multi-user / any external input surface is ever added (none planned this build).

## Backlog status
**A1 (a/b/c) ✅ · A2 ✅ · A3 ✅ · A4 ✅ · A5 ✅ (audit; refactor deferred).** The DISPATCH A1→A5 backlog is
functionally COMPLETE — every feature shipped + verified, the one refactor consciously deferred with a trip-wire,
security clean.
