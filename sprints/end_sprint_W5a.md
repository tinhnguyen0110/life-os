# Sprint W5a — SYNTHESIZE substrate · END

**Status:** ✅ implemented + verified live (Rule#0, full synthesize loop). **Commit:** (pending).

## What shipped — the SYNTHESIZE substrate (the spec's "payoff", L64)
Deterministic graph cluster DETECTION (no vector/no AI) + first-class `moc` noteType + /wiki/clusters
+ /wiki/mocs + `wiki_clusters` MCP read tool. The LLM (external Claude Code) reads clusters → drafts
the MOC + surfaces contradictions → propose_moc → human ratifies. The whole loop closes.

### Files
- reader.py `detect_clusters()` (connected-components + density, D-W5.1) + `mocs()` + ego_graph.clusters
  now populated. store.py `all_resolved_edges()`. schema.py NoteType += "moc". proposals_service.py
  moc-apply sets noteType=moc. router.py GET /wiki/clusters + /wiki/mocs. mcp/read_server.py
  `wiki_clusters` tool (8 tools now). core/config.py wiki_cluster_min_size=3 / min_density=0.30.
- tests/test_wiki_clusters.py (12) + read-server parity + 1 ego_graph test updated (clusters now populated).

### Algorithm (D-W5.1, NO vector)
Connected-components over resolved edges → cluster = component size≥3 AND internal density≥0.30
(density = edges / n(n-1)/2). Ranked importance=size×density (ADVISORY). suggestedTitle = highest-degree
member (deterministic hint, NOT AI — the LLM names the real MOC).

## Verified LIVE (team-lead, Rule#0)
- pytest 933 (+13), 12 cluster def==collected no dup, mypy clean, read-server no-write gate STILL holds (8 tools).
- **Distinguishing case**: a dense triangle [1,2,3] → 1 cluster (size 3, density 1.0, importance 3.0);
  an isolated note → NOT in any cluster. (Correct impl ≠ a collapsed one.)
- moc noteType round-trips; /wiki/mocs lists ONLY mocs.
- **PERF: detect_clusters 200 notes < 1s** (backend measured 0.9ms).
- **E2E synthesize loop**: wiki_clusters via MCP (isError false) → propose_moc over members → human accept
  → MOC note (noteType=moc, 3 outbound links) in /wiki/mocs. The loop closes.

## Assumptions (user-review)
1. **C3 importance = ADVISORY** (RESOLVES spec L242/278): size×density orders MOC candidates + retrieval,
   NEVER gates pruning/auto-delete (north-star: code surfaces, human disposes). — to change: a deliberate
   "authoritative importance" decision (don't).
2. cluster thresholds min_size=3 / min_density=0.30 in config, env-overridable — defaults; tune per real vault.
3. suggestedTitle = highest-degree member (deterministic, not AI) — a hint; the LLM names the real MOC.

## Out of scope (W5b next)
- The W5 MOC screen (FE, /wiki/moc) — unblocked on the frozen /wiki/clusters + /wiki/mocs shapes.
