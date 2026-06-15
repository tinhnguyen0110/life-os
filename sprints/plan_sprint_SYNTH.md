# Sprint SYNTH — cross-tool composition (R2-G1 life_brief) + R2-G2 quota None-fallback

> From consumer-agent round-2 (memory `consumer-agent-round2-gaps-2026-06-15`, Rule#0-verified).
> Backend-only, low-risk, single lane (both touch the brief/synthesis layer).

## Kickoff — 2026-06-15 (architect)

### Verified the gaps against current code (confirms team-lead's reads + one location correction)
- **R2-G1 location:** `life_brief` is NOT in the brief module — it's the MCP synthesizer tool at **`mcp_servers/read_server.py:643`**. It composes 5 sections via `_section(source, build)` (L539, fail-soft wrapper) + per-section `_brief_*` helpers (`_brief_portfolio/_brief_market/_brief_projects/_brief_claude/_brief_decisions`). **It OMITS macro, news, wiki** — confirmed: the `brief.{...}` dict has only portfolio/market/projects/claude/decisions. So a cross-domain "macro+news+portfolio → risk this week?" forces the agent to fire 3 separate tools.
- **Shapes to fold in (verified live):**
  - `macro_overview()` (the existing MCP tool, already wraps `get_overview`) → `MacroOverview{asOf, indicators:[{label, latest, trend, source}], source}`. A 1-line backdrop = the 3 indicators' label+latest+trend (+ the mock-source honesty).
  - `news_digest()` (existing tool) → `{digest:{headline, items:[{title, source, url, publishedTs, tags}], count, asOf, note}}`. Top 1-2 headlines + source.
  - `wiki_overview()` (existing, from WIKI-MCP) → `{overview:{stats, inbox, orphans, ...}}`. A pointer (note count / orphan count) — optional, cheap.
- **R2-G2 location:** `brief/service.py:97-109` `_quota_pct(claude)` returns `pct5h` else None. When pct5h is None (no live snapshot) → claudePct None → the daily_brief quota line vanishes. `pctWeek` is ALSO a real 0-100 field (verified the claude_usage snapshot has pct5h + pctWeek). Fix: `pct5h` else `pctWeek` else None (show A sane %, never nothing-when-an-alternative-exists, never the raw overflow).

### Design decisions
- **R2-G1** = extend `life_brief` with 3 new fail-soft sections: `_brief_macro` (wraps macro_overview → a neutral 1-line backdrop: the 3 indicators' latest+trend + mock-source tag), `_brief_news` (wraps news_digest → top headline(s) + source, honest-empty when nothing captured), `_brief_wiki` (wraps wiki_overview → note/orphan-count pointer). Each via the SAME `_section(source, build)` wrapper (fail-soft — a down source reports `{error}`, the brief still assembles). Add to the `brief.{...}` dict. **NEUTRAL preserved** (descriptive, no advice). **Honest-empty** (no macro/news → omit gracefully, never fabricate).
- **R2-G2** = `_quota_pct` → `pct5h if not None else pctWeek if not None else None`. Distinct from G6 ("don't show the absurd raw 3316%") — this is "don't show NOTHING when pctWeek is a valid alternative." Never falls back to raw `pct`.

### Final task list (single backend lane)
- **SYNTH [backend]** — R2-G1 (life_brief folds in macro+news+wiki, fail-soft+neutral+honest-empty) + R2-G2 (quota None→pctWeek fallback). Both in the brief/synthesis layer; files: `read_server.py` (life_brief + 3 helpers) + `brief/service.py` (_quota_pct) + `test_mcp_read.py` (life_brief new sections) + `test_brief.py` (pctWeek fallback).

### NOT gaps (team-lead-confirmed — don't build)
- G5 decision-empty = DATA not code (propose_decision + POST /decision-journal both exist + discoverable). wiki↔projects cross-domain WORKS.

## Assumptions (user-review)
- life_brief now composes macro+news+wiki alongside the existing 5 sections (one-call cross-domain). NEUTRAL/honest-empty/fail-soft per section.
- daily_brief quota = pct5h, else pctWeek, else None (never raw pct, never nothing-when-pctWeek-exists).
