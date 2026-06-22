# life-os MCP Tool Catalog

> **The canonical, always-current catalog is the MCP tool `list_tools_catalog()`** on the
> read-server — it is DERIVED from the live tool registries, so it never drifts. As of #32 it walks
> EVERY mount (read · write · wiki-read · wiki-write · finance · reminders · tracing), not just the
> shared read+write servers — so this doc's wiki/finance/reminders/tracing sections are generator-covered too.
> This doc is a human-readable snapshot; if it disagrees with `list_tools_catalog()`, the tool is
> right. (Regenerate: see the generator at the bottom.)

Mounts (every server `list_tools_catalog()` enumerates — #32):
- whole-app shared: **46 read · 4 write** (propose) — `/mcp/read` · `/mcp/write`
- standalone wiki (canonical): **14 wiki-read · 6 wiki-write** — `/mcp/wiki-read` · `/mcp/wiki-write`
- finance domain (narrow): **15 finance-read** — `/mcp/finance` — a SUBSET of the whole-app read
  (the SAME 15 fn objects, zero dup), for a finance-only agent. Listed under BOTH `finance` and
  `read` in the catalog (the honest "what THIS agent sees" view) — adds no NEW tool fns.
- reminders domain (writable): **3 reminders** — `/mcp/reminders` — reminders_list (read) +
  reminder_create/reminder_tick (reversible single-user direct write, no proposal gate).
- tracing domain (writable): **3 tracing** — `/mcp/tracing` — tracing_overview + tracing_templates
  (reads, is-identity with the shared read tools) + tracing_log (reversible single-user direct
  append, no proposal gate).

The wiki tools were CONSOLIDATED onto the standalone wiki servers (no longer duplicated on the
shared servers). The shared write-server's `propose_note` was renamed `propose_quicknote` (the
NOTES module) to remove the clash with the wiki note proposal.

MCP-DOMAINS: `lifeos-finance` (`mcp_servers.finance_server`) exposes a curated 15-tool finance
subset (finance_overview/channel/analytics/simulate/guardian, allocation_target, decision_weight,
macro_cycle, nav_history, exchange_overview, macro_overview, market_overview/summary/indicators,
journal_entries) by reference-importing the exact read-server fns — so a finance agent sees 15
focused tools instead of the 40-tool whole-app read. Deeper TA + cross-domain composers excluded.

## Capability boundary (the supervision contract)

- **read** — reads only — writes nothing
- **write** — ENQUEUE proposals only (status=pending) — agent proposes, cannot apply/accept its own proposal
- **apply** — HUMAN-ONLY via POST /agent-proposals/{id}/accept — the agent never has an apply/accept handle (proven by capability-gate tests)
- **feedback** — agent READS its verdict via check_proposal_status / list_my_proposals / proposal_stats — read-only, cannot ratify
- **neutrality** — analysis tools return NEUTRAL data (no buy/sell advice); the agent does the reasoning

## Read tools (read-server — write nothing)

| Tool | Neutral | Description |
|---|---|---|
| `finance_overview` |  | Portfolio overview: per-channel allocations, golden-path targets, total value, |
| `finance_channel` |  | One portfolio channel's detail (holdings + allocation + sell-ladder state) |
| `finance_simulate` |  | What-if: shape a HYPOTHETICAL allocation vs the current portfolio (HHI/drift/turnover) — read-only, no mutation |
| `finance_analytics` | ✓ | Portfolio analytics over the live overview: actionable REBALANCE amounts (per channel, the |
| `market_overview` |  | Live market view: quotes (+ change%), alert triggers, macro signals, alert |
| `market_history` |  | Price-history points for an asset over the last ``hours`` (oldest→newest) |
| `market_indicators` | ✓ | Technical indicators over a tracked asset's close series (NEUTRAL data — no |
| `market_ohlc` |  | OHLC candles for a TRACKED asset, DERIVED from the close-tick series (the feed |
| `market_watchlist` | ✓ | The watchlist with a rich per-symbol view: ``{items:[{symbol,name,price, |
| `market_summary` | ✓ | ONE-call market read for the agent: the rich watchlist (price/changePct/ |
| `market_correlation` | ✓ | Pairwise Pearson correlation matrix over ≥2 symbols (≤10) close series — NEUTRAL |
| `market_relative_strength` | ✓ | A symbol vs a benchmark (price-ratio trend + % change) — NEUTRAL, not a recommendation |
| `projects_list` |  | All tracked, non-abandoned projects with derived health/commit/lang status |
| `project_get` |  | One project's status by id (includes abandoned). Unknown id → |
| `project_context` | read | A project's full context: metadata + its wiki notes (tagged project:<id>) as "project memory". {project, notes, noteCount} (#42). |
| `project_dev_activity` | read | A project's dev-activity, JOINED by slug(dev_activity.repo)==project_id. {projectId, found, commits, locNet, lastActiveDay, days, activeDays, matches[], reason?, warning?}. found:false honest when not in the scan; slug-collision → both+warning. Byte-identical to REST GET /projects/{id}/dev-activity (#112). |
| `graveyard_overview` |  | The graveyard: abandoned projects + post-mortem pattern aggregates |
| `claude_usage` |  | Claude token-usage view: per-day burn series, by-model / by-project split, |
| `daily_brief` |  | Generate today's brief on the fly from live reads: prioritised actions + |
| `brief_history` |  | Past persisted briefs (newest-first). ``{briefs}``. [] if none persisted |
| `journal_entries` |  | Trade journal: entries matching the optional filters (newest-first) + derived |
| `decision_entries` |  | Decision journal: entries matching the optional filters (newest-first) + |
| `activity_feed` |  | Automation activity feed: routine runs (newest-100) + roll-up stats, filters |
| `activity_run` |  | One routine run's detail by id. Unknown id → ``{found: False}`` |
| `exchange_overview` |  | OKX exchange overview: balances + open positions snapshot. ``{exchange, |
| `app_settings` |  | The app config (thresholds, toggles, usage cap …) the agent should respect |
| `reliability_report` |  | The reliability suite report: grounding-eval + fail-closed gates. ``{report}`` |
| `macro_overview` | ✓ | Macro economic context: latest Fed funds rate / US CPI / DXY dollar index + a |
| `macro_history` |  | One macro indicator's time-series over the last ``days`` (oldest→newest) |
| `news_digest` | ✓ | A NEUTRAL, source-cited roll-up of the grounded news the module has captured |
| `news_list` | ✓ | Raw captured headlines, newest-first — each with source url + published_ts |
| `life_brief` | ✓ | THE agent data-layer: ONE call → a neutral, source-tagged snapshot of the |
| `insights` | ✓ | Cross-domain NEUTRAL evidence-grounded observations (undeployed-capital / all-crypto-overbought / framework-vs-execution / stalled-project) over real data |
| `tracing_overview` | ✓ | The habit/activity board for today-VN: per-activity today/streak/week/history12w + 12w heatmap (per-day COUNT of activities met) + score. All derived server-side. Byte-identical to REST GET /tracing (#65). |
| `tracing_templates` | ✓ | Merged task-template list (built-in SEED ⊕ user override), each tagged source. LEAN prefill suggestions {id,name,goal,unit,emoji,color,source} for starting a habit without typing. Byte-identical to REST GET /tracing/templates (#109). |
| `dev_activity` | ✓ | Local git dev-activity over N days: per VN day × repo × source(you/other) commits + LOC(filtered, INFORMATIONAL) + active-span + byRepo + summary. honest-empty + warnings (roots/identity). Byte-identical to REST GET /dev_activity (#63). |
| `code_insight` | ✓ | On-demand FRESH read of a repo for a cold agent: top-level structure + README excerpt + recent git-log + detected stack + asOf (live, never indexed). repo = name|path under the :ro roots. honest found:false + bounded (caps warned). Byte-identical to REST GET /code_insight (#64). |
| `repo_memory` | ✓ | The DURABLE curated Repos/<name> wiki note (summary/stack/decisions/lessons/in-progress) a cold agent reads — the persisted complement to code_insight. found:false if none. Write = the wiki PROPOSE tool (kind=note, folder=Repos). Byte-identical to REST GET /code_insight/memory (#64). |
| `check_proposal_status` |  | One proposal's disposition by id: status (pending|accepted|rejected), |
| `list_my_proposals` |  | The agent's proposals (newest-first) with their current disposition — the review |
| `proposal_stats` |  | Counts of the agent's proposals by status (pending/accepted/rejected) so the |
| `list_tools_catalog` | ✓ | The agent's self-discovery index: every MCP tool across ALL MOUNTS (read/write/wiki/finance/reminders) as |

## Write tools (write-server — ENQUEUE proposals only; human applies)

| Tool | Description |
|---|---|
| `propose_decision` | Propose a NEW decision-journal entry (module=decision_journal, kind=decision_create) |
| `propose_quicknote` | Propose a NEW quick note (module=notes, kind=note_create). Lands PENDING; a human applies. (Renamed from `propose_note`, MCP-DEDUP #70.) |
| `propose_journal` | Propose a NEW trade-journal entry (module=journal, kind=journal_create) |
| `propose_project_update` | Propose an UPDATE to a project's human-authored status fields (module=projects, |

## Wiki tools (standalone canonical servers — `/mcp/wiki-read` · `/mcp/wiki-write`)

The wiki MCP tools live on the standalone wiki servers (modules/wiki/mcp), NOT the shared ones
(MCP-DEDUP #70). The read server has the M4 no-write gate; the write server is enqueue-only.

| Tool | Server | Description |
|---|---|---|
| `wiki_search` | wiki-read | Full-text search the vault → ranked results [{id, title, snippet, status}] |
| `wiki_overview` | wiki-read | Vault overview: {stats, inbox, orphans, recentActivity, proposalCount} + warning |
| `wiki_inbox` | wiki-read | Fleeting notes awaiting triage (oldest→newest) |
| `wiki_get_note` | wiki-read | One note by its INTEGER id (the citation key); missing → {found: False} |
| `wiki_context` | wiki-read | A note's full neighborhood in ONE call: {found, note_id, graph, backlinks}. Supersedes wiki_graph + wiki_backlinks (#23). |
| `wiki_suggest_links` | wiki-read | Top 3-5 NEW link candidates for a note: {suggestedLinks:[{id,title,relevance}]} (FTS by title, self+already-linked excluded). Suggest-only (#34). |
| `wiki_stale` | wiki-read | Staleness + contradiction-candidate detector: stale evergreen notes (>threshold, ≥1 inbound) + mutually-linked divergent-trust pairs. Read-only, no AI (#41). |
| `wiki_recent_ops` | wiki-read | Recent wiki mutations (op-log activity feed), newest first |
| `wiki_clusters` | wiki-read | MOC candidates: graph-detected clusters of linked notes (W5a) |
| `wiki_verify_citations` | wiki-read | Post-verify citations (anti-fabrication gate): verified/rejected/ungrounded/weakly_grounded |
| `wiki_proposal_status` | wiki-read | One WIKI proposal's disposition by id (the wiki_proposals queue). PORTED #70. |
| `wiki_list_proposals` | wiki-read | The agent's WIKI proposals (newest-first) + counts. PORTED #70. |
| `wiki_reindex` | wiki-read | Bulk-reconcile the cache vs md files: prune orphan rows whose .md is gone. {scanned,dropped,rebuilt,unchanged,droppedIds}. Idempotent (#53). |
| `propose_note` | wiki-write | Propose a NEW wiki note → wiki_proposals queue |
| `propose_edit` | wiki-write | Propose an EDIT to a wiki note → wiki_proposals queue |
| `propose_link` | wiki-write | Propose ADDING a [[target]] link to a wiki note → wiki_proposals queue |
| `propose_unlink` | wiki-write | Propose REMOVING a [[target]] link from a wiki note → wiki_proposals queue |
| `propose_merge` | wiki-write | Propose MERGING wiki note source_id INTO target_id → wiki_proposals queue |
| `propose_moc` | wiki-write | Propose a wiki Map-of-Content note → wiki_proposals queue |

## Reminders tools (reminders domain — `/mcp/reminders`; reversible single-user direct write)

| Tool | Server | Description |
|---|---|---|
| `reminders_list` | reminders | What's on the user's plate: reminders by `filter` (today\|week\|undone\|all) |
| `reminder_create` | reminders | Create a reminder — DIRECT write-through (no proposal gate; reversible single-user CRUD) |
| `reminder_tick` | reminders | Mark a reminder done — DIRECT write-through, IDEMPOTENT (re-ticking keeps the first done_at) |

## Tracing tools (tracing domain — `/mcp/tracing`; reversible single-user direct write)

| Tool | Server | Description |
|---|---|---|
| `tracing_overview` | tracing | The habit board for today-VN (per-activity today/streak/week/history12w + 12w heatmap + score). is-identity with the shared read tool |
| `tracing_templates` | tracing | Merged task-template list (SEED ⊕ user override, each tagged source) — LEAN prefill suggestions. is-identity with the shared read tool (#109) |
| `tracing_log` | tracing | Log a session against an activity — DIRECT write-through (no proposal gate); same-day logs accumulate; returns the updated activity view. Unknown id → {found:False} |

## Regenerate this doc

This snapshot is generated from `list_tools_catalog()`. To refresh after adding a tool,
re-run the generator (it reads the live registries — no hand-editing the tables).

