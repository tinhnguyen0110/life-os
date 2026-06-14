# Sprint A5 — Refactor + Security audit · PLAN

> DISPATCH A5 (the last A1→A5 item). Refactor: files >500 LOC → cohesive splits (NO behavior change).
> Security: secret/injection/path-traversal/MCP-least-privilege audit. Refactor scope needs team-lead approval.

## Kickoff — 2026-06-15

### Refactor candidates (files >500 LOC) — with my split/SKIP recommendation
```
752  modules/wiki/store.py     → SPLIT (recommend)
601  modules/wiki/service.py   → SKIP (cohesive)
531  modules/wiki/reader.py    → BORDERLINE → SKIP (recommend)
442  modules/projects/service.py → under 500, skip
418  modules/finance/service.py  → under 500, skip
```

**`store.py` (752) — SPLIT (the one genuine win).** It's a data-access layer holding SIX distinct concerns
on one connection: (1) note-cache CRUD + id-gen, (2) op_log, (3) alias resolver, (4) typed-edge graph, (5) D6
redirect tombstones, (6) FTS5 + graph-aggregate queries. These are cohesive *as data-access* but it's a 752-LOC
grab-bag. **Proposed split (behavior-preserving — pure move, same functions, same shared connection):**
- `store.py` → keep schema registration (`WIKI_SCHEMA`, `init_wiki_tables`, `_migrate`) + note-cache CRUD + id-gen + the md-file pass-throughs (the core).
- `store_links.py` → the typed-edge graph + alias resolver + ghost/redirect logic (links/aliases/redirects — one concern: the link graph).
- `store_search.py` → FTS5 (`fts_*`) + the graph-aggregate read queries (`degree`/`neighbors`/`edges_among`/`all_resolved_edges`/`count_*`).
- All keep the same `_lock` + `db.get_conn()` pattern; callers' imports update. NO logic change → every wiki test stays green = the gate.

**`service.py` (601) — SKIP.** It's ONE cohesive thing: the single-writer queue + the apply-per-op-kind state
machine. Splitting the queue from the apply logic would SEPARATE tightly-coupled code (the worker calls `_apply`
which calls `_apply_create/update/delete/merge/refine` — they share the Op dataclass + the commit helper). A split
here would hurt cohesion, not help. 601 LOC of one coherent concern is fine (north-star: don't refactor for its own sake).

**`reader.py` (531) — SKIP (borderline).** Read-aggregation for the wiki screens (backlinks/search/ego-graph/
overview/inbox/clusters/mocs). Cohesive (all read-path, all return view-shaped dicts), just past 500. Splitting
"reader" into sub-readers adds import churn for marginal gain. Recommend SKIP unless it grows.

→ **NET: one conservative split (`store.py`), two SKIPs with rationale.** This honors the north-star — split only
where it genuinely improves cohesion; a coherent 600-LOC file stays.

### Security audit — findings (read-only scan, all CLEAN)
1. **Secret hardcode** — grep for api_key/secret/token/password literals in `modules/core/store`: **NONE**. (No-auth single-user app; no secrets to leak.)
2. **SQL injection** — only two f-string SQLs (`store.py:611` `all_notes`, `:697` `edges_among`). Both safe: `{col}`
   is whitelisted to `id`/`created` (not user input); `edges_among` builds `{placeholders}` as `?` marks with
   `int()`-coerced ids bound separately. All value-bearing queries use `?` parameters. FTS user-`q` goes through
   `_sanitize_fts_query` (tokenizes + quotes, never raw). **CLEAN.**
3. **Path traversal** — `note_rel_path` coerces `int(note_id)` (a `../` payload can't survive int()). AND md_store
   has an explicit containment guard: `_resolve_under_root` resolves the path + raises `MdStoreError` if it escapes
   DATA_DIR. Defense-in-depth. **CLEAN.**
4. **MCP least-privilege** — read/write capability split proven by the AST tests (15 read + 14 write) AND
   re-asserted at runtime by the A3 reliability harness (`run_fail_closed_check`). Read server has no write symbol;
   write server is enqueue-only. **HOLDS.**

→ **NET: security audit CLEAN. No vulnerabilities.** (Expected for a no-auth single-user localhost app, but verified, not assumed.)

### Final task list (A5)
- **A5-refactor [backend]** — ~~split `store.py`~~ → **DEFERRED** (see Scope reversal below).
- **A5-security** — DONE in kickoff (audit clean, documented above). No code change needed; the finding IS the deliverable.

### Scope reversal — 2026-06-15 (decide-and-log)
The store.py refactor was approved, then **DEFERRED on the merits**. Backend raised: the split is pure cleanup
(zero feature value) + the highest-regression-risk change of the backlog (store.py is load-bearing). architect +
team-lead agreed — north-star "don't refactor for its own sake" applied to the refactor approval itself. A5 ships
as **security-audit-only** (a complete, legitimate A5). The refactor analysis + a trip-wire are preserved in
`end_sprint_A5.md` §Refactor-Deferred. Backend stood down (no code touched).

## Assumptions (user-review)
- Refactor scope = ONLY `store.py` split (conservative); service.py/reader.py kept (cohesive, splitting would hurt). — to change: split them too if they grow past comfort.
- Security audit clean (no-auth single-user app, but verified: no secrets, parameterized SQL, path-containment, MCP gates hold).
