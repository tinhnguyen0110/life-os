# Sprint FINANCE-MCP-SHAPE — expose finance_analytics over MCP + warnings hygiene

**Task #50. Theme:** the REST `/finance/analytics` (rebalance + risk/HHI + returns) isn't an MCP read tool, so the agent can't read it; finance warnings are re-shipped across overview/analytics. Backend-only MCP-surface + payload hygiene.
**Type:** numbered sprint (single backend theme, ~2-3 tasks).
**Source:** team-lead live Rule#0 verify.

## Kickoff — 2026-06-16 (every claim verified live)

### CLAIM 1 — finance_analytics NOT in MCP → CONFIRMED, build it
- `modules/finance/service.py:792 get_analytics() -> (PortfolioAnalytics, warnings)` + `router.py:92 @router.get("/analytics")` EXIST.
- `read_server.py` has `finance_overview`/`finance_channel`/`finance_simulate` wrappers but **NO finance_analytics** (the "NB-FINANCE-MCP" comments are about simulate/correlation/rel-strength, not analytics). → Genuinely missing. Build a thin MCP read wrapper, exactly like `finance_simulate` (a pure-compute READ; no mutation → capability gate unaffected).
- `PortfolioAnalytics` shape: `{totalValue, rebalance:[RebalanceAction], risk:RiskMetrics, returns:ReturnMetrics, asOf}`. Returns `(model, warnings)` → wrap via the existing `_with_warnings` normaliser.

### CLAIM 2 — warnings duplication → NUANCED (NOT a simple verbatim copy; consumer-risky)
- `get_analytics()` calls `get_overview()` and **inherits its FULL warnings list** (service.py:797 `overview, warnings = get_overview()`), then appends `_aggregate` warnings deduped-against-itself (L818 `[w for w in agg_warn if w not in warnings]`). So overview's gp+price+okx+stable+drift warnings get **re-shipped** in analytics.
- `simulate()` builds its OWN gp warnings (`get_golden_path()`) + simulate-specific — overlaps overview only on the gp set.
- So it's **duplication-by-inheritance**, not copy-paste. "Consolidate to one place" is NOT straightforwardly safe (see consumers).

### MANDATORY consumer grep (dissolved-finding-recheck-all-consumers) — moving warnings OUT of overview is UNSAFE
- **`brief/reader.py:49`** `src.warnings.extend(w or [])` where `w` = finance `get_overview()` warnings → **the BRIEF synthesis surface READS overview.warnings.** Stripping them breaks the brief.
- **`read_server.py` finance_overview tool** wraps overview warnings into its MCP envelope (`_with_warnings`) → the agent reads them.
- **`router.py`** `/finance` returns overview warnings in the response.
- → **overview MUST keep its warnings.** The genuine, safe dedup is NARROWER than "one place": analytics re-shipping overview's warnings is only redundant for a consumer who ALSO reads overview — but the analytics MCP tool is read STANDALONE, so it legitimately needs self-contained warnings. **Likely verdict: the "duplication" is mostly CORRECT (each tool self-contained); the only real fix is to ensure NO warning is listed TWICE within a single tool's output (already deduped in analytics) + maybe a one-line doc that analytics warnings are a superset of overview's. Will propose to team-lead that the dedup scope is smaller than it first looked — possibly a no-op beyond CLAIM 1.**

### CLAIM 3 — finance_summary (optional) → DEFER unless team-lead wants it
- A `finance_summary` (totalValue/change/pnlTotal/dryPowder) for "how much total" — but `finance_overview` ALREADY returns all of those + `life_brief.portfolio` gives the lean version. So finance_summary would be a 4th overlapping read. **Lean toward NOT building it (over-engineering — north-star); flag to team-lead.**

### Final task list (proposed — pending team-lead approval, esp. the CLAIM 2 scope pushback)
- **T1:** add `finance_analytics()` MCP read wrapper in read_server.py (thin, wraps `get_analytics()` via `_with_warnings`) + register in TOOLS + the catalog count test (read tools 40→41). Capability gate: pure read, no mutation symbol → AST/namespace gate auto-holds; add `get_analytics` to the imported read fns (aliased-private).
- **T2 (pending team-lead):** warnings hygiene — likely SMALLER than first stated. Within-tool dedup is already done; overview warnings can't move (brief/MCP/REST consume them). Propose: leave overview as-is, confirm analytics has no INTRA-list dupes, document the superset relationship. NOT a strip-and-relocate (would break the brief).
- **T3:** tests — finance_analytics MCP callable + envelope + no-write-leak gate (gate count) + the warnings-not-double-listed assertion.

### Locks (team-lead, 2026-06-16 — after kickoff approval)
- **CLAIM 1 — BUILD.** finance_analytics thin MCP wrapper (mirror finance_simulate, `_with_warnings`, register TOOLS, count 40→41). Capability gate auto-holds (pure read).
- **CLAIM 2 = (b) `_finance_warnings()` shared-assembly refactor.** DRY the SOURCE (≥2 verbatim sites: service.py:603 + :705 + simulate gp). **HARD LOCK: emitted warnings OUTPUT of get_overview/get_analytics/channel-detail/simulate must be BYTE-IDENTICAL to before** — pure dedup, zero behavior change. BEHAVIOR-TEST the output equality (not "helper exists"). Rejected (a) doc-only — the dup is real + (b) is cheap+safe. Never strip overview's warnings (brief/reader.py:49 consumes them).
- **CLAIM 3 — SKIP.** No finance_summary (overview already returns totalValue/change/pnlTotal/dryPowder + life_brief.portfolio is the lean version; 4th overlapping read = over-engineering).

### Routing / sequencing
Dispatched to **backend-2** (active; stale `backend` idle). backend-2 done → team-lead verifies live (analytics MCP returns rebalance/risk + warnings output identical) → architect review+commit+push. Next sprint after = WRITE-LOOP-E2E.
