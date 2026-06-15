# Sprint CONTEXT-UI — News-via-MCP + FE for Macro/News

> Spec written 2026-06-15 by team-lead. Two independent sub-sprints, can run in parallel
> (different lanes: NEWS-MCP = backend/mcp, FE-5 = frontend). Both are "replicate an existing
> proven pattern", not greenfield.
>
> Context: round-2 added macro (Fed/CPI/DXY) + news (RSS) modules + wrapped MACRO via MCP +
> FE-4 market dashboard. Two gaps remain: (1) news is NOT yet readable by the agent over MCP
> (macro is — asymmetric), (2) macro & news have NO UI (market/finance/career do).
>
> Source-of-truth signatures verified against live code 2026-06-15:
> - news service: `list_news(tag=None, limit=30) -> NewsList`, `digest(tag=None, limit=10) -> NewsDigest`,
>   `capture() -> (int, warnings)` (WRITE — do NOT wrap). Schema: NewsItem/NewsList/DigestItem/NewsDigest.
> - news REST: GET /news?tag=&limit= · GET /news/digest?tag=&limit= · POST /news/capture
> - macro REST: GET /macro/overview · GET /macro/history?indicator=&days=
> - macro MCP wrap precedent (read_server.py L102-325): import read fns aliased-private,
>   `macro_overview()` + `macro_history(indicator, days)`, gate adds writes to WRITE_SYMBOLS.
> - nav.ts groups: "Tài chính" exists; add news/macro under a sensible group (see FE-5).

---

## SUB-SPRINT A — NEWS-MCP (wrap news via MCP read-server)

**Owner:** mcp/agent lane. **Symmetry:** exactly mirrors MACRO-2 (which wrapped macro reads).

### Context
The agent can read macro over MCP but NOT news — asymmetric. An agent answering "tin tức gì
đáng chú ý" needs to read the grounded news the news module already captures. Wrap the READ
side only; capture stays human/poller-triggered (it's a write/fetch).

### Scope (ONLY backend/mcp_servers/read_server.py + backend/tests/test_mcp_read.py)
- Add 2 read-only tools (mirror macro_overview/macro_history):
  - `news_digest(tag=None, limit=10)` → wrap `news.service.digest()` — NEUTRAL grounded
    roll-up, each item cites source url. Honest-empty when nothing captured.
  - `news_list(tag=None, limit=30)` → wrap `news.service.list_news()` — raw headlines +
    source url + published_ts, newest first.
- Import ONLY these read fns, aliased private (`_news_digest`, `_news_list`) — same style as
  `_macro_overview`/`_macro_history`.
- `list_tools_catalog()` is derive-based → it auto-picks the 2 new tools (no hardcode change).
  Read-server goes 28 → 30 tools; regenerate CATALOG.md from the live tool.

### Defensive (MANDATORY)
- Nothing captured yet → digest/list return honest empty (count 0, items []), NOT fabricated.
- tag with no match → [] clean.
- NEUTRAL preserved: news_digest must carry NO sentiment/advice (the module already guarantees
  this; the MCP wrapper must not add any). A test asserts no forbidden term leaks through MCP.
- Capability gate 0-leak: add `capture` (+ any news write/init fn: e.g. `init_news_tables`,
  `record_item` if present) to WRITE_SYMBOLS. The read-server must NOT import them. Re-run the
  AST + namespace gate tests → still 0 write-symbol leak.

### Verify
- AST/namespace gate green (no news-write leak).
- Behavioral: news_digest cites source per item + honest-empty; news_list shape + tag filter.
- Catalog count matches (30) — derive auto-pickup, no hardcode edit (proves the design holds).
- Full mcp suite + full BE suite green (run `.venv/bin/python -m pytest -q` FULL, no -k).

### Commit
`feat: expose news via MCP read-server (NEWS-MCP)` — read_server.py + test + CATALOG.md only.

---

## SUB-SPRINT B — FE-5 (UI for Macro + News)

**Owner:** frontend lane. **Symmetry:** mirrors FE-4 (market dashboard) structure + discipline.

### Context
macro (/macro/overview, /macro/history) and news (/news, /news/digest) have backend + data but
NO screen. User can't see the macro backdrop or the news feed. Build two read-only views.

### Scope (NEW FE files + 2 new routes + nav)
- **NEW `app/macro/page.tsx`** — Macro context view:
  - cards for Fed funds rate / CPI / DXY: latest value + DESCRIPTIVE trend (up/down/flat) +
    source badge (show "mock" honestly when source='mock' + the warning verbatim).
  - optional small sparkline per indicator from GET /macro/history (reuse chart-geometry, append-only).
- **NEW `app/news/page.tsx`** — News feed view:
  - digest panel (GET /news/digest): the neutral roll-up, each item a clickable source link.
  - full list (GET /news?tag=&limit=): headlines with source + published time, tag filter chips,
    "Capture now" button → POST /news/capture (the one write; apiPost; refresh after).
- **NEW** `lib/useMacro.ts` + `lib/useNews.ts` (apiGet/apiPost, types LOCAL — do NOT touch types.ts).
- **MOD `lib/nav.ts`** — add nav entries. Suggest: macro under "Tài chính" (it's market context),
  news under a new group "Tin tức" OR under "Tri thức". Pick one, keep nav.test.ts counts updated.
- **MOD `lib/tokens.css`** — `.macro*` / `.news*` styles, APPEND only (after existing blocks).
- **NEW** tests for both pages + hooks.

### Defensive (MANDATORY)
- macro/news empty (no data / not yet captured) → honest empty-state, NOT blank/crash.
- macro source='mock' → show the mock badge + warning so the user never mistakes it for live.
- news capture button error → toast/inline error + retry, page stays alive.
- API error per panel → that panel shows error+retry, does NOT kill the page (FE-4 lesson:
  coerce defensively, one panel failing ≠ whole page down).
- DO NOT touch api.ts/types.ts beyond nav.ts additions; use apiGet/apiPost + local types.
- chart-geometry.ts reuse = APPEND-ONLY (MarketChart/EquityCurve signatures intact).

### Verify
- vitest green (both pages, empty-state, mock-badge, capture-error, per-panel-isolation).
- tsc --noEmit clean. nav.test.ts counts updated to pass.
- Chrome live: /macro renders Fed/CPI/DXY cards (mock badge visible) + sparklines; /news renders
  digest + headline list with working source links + tag filter + capture button; dark-mode;
  console clean. DB untouched except a real capture (which is the intended write).

### Commit
`feat: macro + news UI views (FE-5)` — new app/macro, app/news, hooks, nav, tokens, tests.

---

## Ordering / parallelism
- A (NEWS-MCP) and B (FE-5) are INDEPENDENT — different files, can run fully in parallel.
- Within B, macro page and news page are independent; one agent can do both sequentially or split.
- No cross-dependency: FE reads existing REST endpoints (already shipped); MCP wraps existing
  service fns (already shipped). Neither blocks the other.

## Gates (both sub-sprints)
- Full BE suite green (no -k) for A; full FE vitest green for B.
- NEUTRAL preserved (no advice/forecast/sentiment added at any layer).
- Honest empty + mock-badge (never fabricate, never hide mock-ness).
- Scope-isolated commits; no shared-file edits beyond the explicit nav.ts/tokens.css appends.
