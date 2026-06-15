# life-os MCP Tool Catalog

> **The canonical, always-current catalog is the MCP tool `list_tools_catalog()`** on the
> read-server — it is DERIVED from the live tool registries, so it never drifts. This doc is a
> human-readable snapshot generated from that tool; if it disagrees with `list_tools_catalog()`,
> the tool is right. (Regenerate: see the generator at the bottom.)

Totals: **32 tools** — 28 read · 4 write (propose).

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
| `market_overview` |  | Live market view: quotes (+ change%), alert triggers, macro signals, alert |
| `market_history` |  | Price-history points for an asset over the last ``hours`` (oldest→newest) |
| `market_indicators` | ✓ | Technical indicators over a tracked asset's close series (NEUTRAL data — no |
| `market_ohlc` |  | OHLC candles for a TRACKED asset, DERIVED from the close-tick series (the feed |
| `market_watchlist` | ✓ | The watchlist with a rich per-symbol view: ``{items:[{symbol,name,price, |
| `market_summary` | ✓ | ONE-call market read for the agent: the rich watchlist (price/changePct/ |
| `projects_list` |  | All tracked, non-abandoned projects with derived health/commit/lang status |
| `project_get` |  | One project's status by id (includes abandoned). Unknown id → |
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
| `life_brief` | ✓ | THE agent data-layer: ONE call → a neutral, source-tagged snapshot of the |
| `check_proposal_status` |  | One proposal's disposition by id: status (pending|accepted|rejected), |
| `list_my_proposals` |  | The agent's proposals (newest-first) with their current disposition — the review |
| `proposal_stats` |  | Counts of the agent's proposals by status (pending/accepted/rejected) so the |
| `list_tools_catalog` | ✓ | The agent's self-discovery index: every MCP tool across BOTH servers as |

## Write tools (write-server — ENQUEUE proposals only; human applies)

| Tool | Description |
|---|---|
| `propose_decision` | Propose a NEW decision-journal entry (module=decision_journal, kind=decision_create) |
| `propose_note` | Propose a NEW note (module=notes, kind=note_create). Lands PENDING; a human |
| `propose_journal` | Propose a NEW trade-journal entry (module=journal, kind=journal_create) |
| `propose_project_update` | Propose an UPDATE to a project's human-authored status fields (module=projects, |

## Regenerate this doc

This snapshot is generated from `list_tools_catalog()`. To refresh after adding a tool,
re-run the generator (it reads the live registries — no hand-editing the tables).

