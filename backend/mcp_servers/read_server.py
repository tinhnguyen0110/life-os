"""mcp_servers/read_server.py — WHOLE-APP MCP READ-only server for life-os (MCP-1).

External Claude Code connects over **stdio** and READS the user's life data across
ALL modules: finance/portfolio, market (+ TA indicators), projects, Claude-usage,
journals (trade + decision), the daily brief, the activity feed, the graveyard, the
OKX exchange overview, app settings, and the reliability report. It also exposes
``life_brief`` — ONE tool that composes the per-module reads into a single neutral,
source-tagged snapshot of the user's life (the agent data-layer, MCP-2), so an
external agent gets the whole picture in one call then reasons itself. The agent
synthesises + advises; this server writes NOTHING (writes, if ever, go through a
SEPARATE propose-style write-server — the wiki MCP split is the template).

THE CAPABILITY GATE (least-privilege, STRUCTURAL — not a flag):
This module imports ONLY read entry-points, each aliased with a leading underscore so
the bound names are obviously private wrappers:
  - finance:          get_overview, get_channel
  - market:           get_market, history, compute_indicators, tracked_assets,
                      candles, watchlist_data
                      (READ paths only — NOT poll_once / add_rule / delete_rule;
                      compute_indicators/candles/watchlist_data are the GET
                      /market/indicators //ohlc //watchlist read paths dev shipped —
                      WRAPPED, never edited; this file does NOT touch market/service.py
                      or market/ta.py, which dev owns. summarize() stays NEUTRAL.)
  - projects:         list_projects, get_project
  - graveyard:        get_graveyard
  - claude_usage:     get_usage
  - brief:            generate_brief, get_history     (generate ASSEMBLES from live
                      reads — it does NOT persist; save_brief is NOT imported)
  - journal:          list_entries
  - decision_journal: list_entries
  - activity:         get_feed, get_run
  - exchange:         get_overview                    (cached read; sync is internal +
                      not imported as a tool)
  - settings:         get_config                      (read; set_config NOT imported)
  - reliability:      run_suite                       (READ-ONLY suite — verifies
                      against an existing note, never writes)
  - macro:            get_overview, get_history        (Fed/CPI/DXY context, READ
                      paths only — NOT refresh / record_point / init_macro_tables,
                      which stay in WRITE_SYMBOLS. NEUTRAL: descriptive trend, no
                      forecast; mock honestly tagged source='mock'.)
  - agent proposals:  get_proposal, list_proposals, count_by_status (MCP-5 — the
                      agent READS the disposition of its OWN proposals to learn from
                      accept/reject. ONLY these 3 read fns are imported from
                      proposals_store — NOT enqueue / mark_decided / set_applied_ref /
                      append_audit, so the agent cannot write/decide via the read-
                      server; accept/reject stays human-only at the REST surface.)
It imports NO mutation symbol (create_/update_/delete_/upsert_/set_/add_/register_/
abandon_/restore_/refresh_/save_/poll_/sync/enqueue …). ``tests/test_mcp_read.py`` asserts
(a) no such symbol is bound in this module's namespace and (b) the AST of its imports
binds none of them — the gate proven by grep+AST, not by this docstring.

NO per-call audit table: unlike the wiki MCP (whose audit feeds the proposal-review
trust boundary), this is a pure read of single-user, no-auth local data — an audit
table would be over-engineering with no consumer. (life-os: simplest implementation,
full feature set. If a real audit need appears, add it then.)

Run:  python -m mcp_servers.read_server   (stdio; registered in Claude Code config)

NOTE: this module deliberately does NOT use ``from __future__ import annotations``.
FastMCP introspects each tool's parameter annotations at registration via
``issubclass(annotation, Context)`` — with stringized (future) annotations that call
raises ``TypeError: issubclass() arg 1 must be a class``. Real (non-string)
annotations are required for the SDK to build each tool schema. (Same constraint the
wiki MCP servers document.)
"""

from datetime import datetime, timezone
from typing import Any, Callable

# READ-ONLY imports only (the capability gate — see module docstring + the no-write
# test). Each is aliased with a leading underscore: these are private read wrappers,
# and the alias keeps the bound names unambiguous for the namespace-scan test.
from modules.finance.service import get_overview as _fin_overview
from modules.finance.service import get_channel as _fin_channel
# NB-FINANCE-MCP: pure-compute analytics READ paths — simulate is a what-if shaper (reads
# golden-path + current holdings, computes HHI/drift/turnover, mutates NOTHING) and the
# market correlation/relative-strength are pure reads over the close series. NOT
# upsert_holding/delete_holding/set_golden_path (those stay in WRITE_SYMBOLS).
from modules.finance.service import simulate as _fin_simulate
# FINANCE-MCP-SHAPE (#50): get_analytics is a pure-compute READ (rebalance amounts / risk-HHI
# / returns over the live overview — mutates NOTHING). NOT set_golden_path/upsert_holding
# (those stay in WRITE_SYMBOLS). Aliased-private so the no-write namespace/AST gate auto-holds.
from modules.finance.service import get_analytics as _fin_analytics
# FINANCE-ASSISTANT P2 (#54): the decision tower — macro_cycle (RL state) + decision_weight
# (W=∏q). Pure read/compute (no mutation) → aliased-private, the no-write gate auto-holds.
from modules.decision.service import macro_cycle as _decision_macro_cycle
from modules.decision.service import decision_weight as _decision_weight
# FINANCE-ASSISTANT P3 (#55): allocation_target (NEUTRAL reference weighting) + finance_guardian
# (proactive NEUTRAL observations). Pure read/compute → aliased-private, the no-write gate holds.
from modules.decision.service import allocation_target as _decision_allocation
from modules.decision.service import finance_guardian as _decision_guardian
# FINANCE-ASSISTANT P4 (#56): the NAV-series reader (daily total-value history + confidence).
# Pure read over portfolio_snapshot → aliased-private, the no-write gate holds.
from modules.decision.service import nav_history as _decision_nav_history
from modules.market.service import correlation as _mkt_correlation
from modules.market.service import relative_strength as _mkt_rel_strength
from modules.market.service import MAX_COMPARE_SYMBOLS as _MAX_CORR_SYMBOLS
from modules.market.service import get_market as _mkt_market
from modules.market.service import history as _mkt_history
# TA read path shipped by dev (GET /market/indicators) — wrapped, NOT edited. Returns
# NEUTRAL technical data (no advice) + warnings. tracked_assets is the read-only
# config list of symbols (no asset-mgmt mutation).
from modules.market.service import compute_indicators as _mkt_indicators
from modules.market.service import tracked_assets as _mkt_tracked
# MCP-6: more market READ paths dev shipped — OHLC candles (close-derived, honest
# warning) + the rich watchlist (price/changePct/sparkline/RSI/trend). READ-only;
# add_rule/delete_rule/poll_once are NOT imported (they stay in WRITE_SYMBOLS).
from modules.market.service import candles as _mkt_candles
from modules.market.service import watchlist_data as _mkt_watchlist
from modules.projects.service import list_projects as _proj_list
from modules.projects.service import get_project as _proj_get
from modules.graveyard.service import get_graveyard as _grave_get
from modules.claude_usage.service import get_usage as _claude_usage
from modules.brief.service import generate_brief as _brief_generate
from modules.brief.service import get_history as _brief_history
from modules.journal.service import list_entries as _journal_list
from modules.decision_journal.service import list_entries as _decision_list
from modules.activity.service import get_feed as _activity_feed
from modules.activity.service import get_run as _activity_run
from modules.exchange.service import get_overview as _exch_overview
from modules.settings.service import get_config as _settings_get
from modules.reliability.service import run_suite as _reliability_suite
# MACRO-2: macro context (Fed/CPI/DXY) READ paths — get_overview/get_history only.
# NOT refresh / record_point / init_macro_tables (those stay in WRITE_SYMBOLS). The
# agent reads the macro backdrop; it cannot write the macro series.
from modules.macro.service import get_overview as _macro_overview
from modules.macro.service import get_history as _macro_history
# NEWS-MCP: the agent reads grounded news (digest/list) — READ paths only. NOT
# capture / init_news_tables (those stay in WRITE_SYMBOLS — the agent reads the
# captured news; it cannot capture/fetch or init the store).
from modules.news.service import digest as _news_digest
from modules.news.service import list_news as _news_list
# REMINDERS-2 (#28): the agent reads "what's on my plate" — list_reminders is a READ fn (no
# mutation; create/tick/delete are NOT imported here, they live on the lifeos-reminders write
# surface). Read-gate-safe.
from modules.reminders.service import list_reminders as _reminders_list
# WIKI-MCP: the agent reads the wiki (search/get/overview/backlinks) — READ paths
# only, aliased-private. NOT create_note/update_note/delete_note/merge_notes/enqueue/
# create_proposal/accept_proposal/reject_proposal (those stay in WRITE_SYMBOLS — the
# agent reads the vault + proposes via the WRITE server, it cannot mutate directly).
# MCP-DEDUP #70: _wiki_search + _wiki_overview are KEPT — life_brief (_brief_wiki) and
# insights (_brief_decision) consume them. The wiki MCP TOOLS (search/get/overview/
# backlinks/proposal-reads) were removed from this server (canonical = standalone
# modules/wiki/mcp/), so _wiki_backlinks / _wiki_get_note / the wiki-proposal read fns
# are no longer imported here.
from modules.wiki.reader import search as _wiki_search
from modules.wiki.reader import overview as _wiki_overview
# MCP-5: the agent reads the DISPOSITION of its own proposals (status/applied_ref) so it
# can learn from accept/reject — READ paths only. We import the SPECIFIC read fns (NOT
# the proposals_store module), so enqueue / mark_decided / set_applied_ref / append_audit
# stay unreachable here — the read-server's no-write gate holds (the no-write-symbol AST
# test asserts it). The agent CANNOT accept/reject its own proposal (human-only, REST).
from mcp_servers.proposals_store import get_proposal as _proposal_get
from mcp_servers.proposals_store import list_proposals as _proposal_list
from mcp_servers.proposals_store import count_by_status as _proposal_counts


# --------------------------------------------------------------------------- #
# JSON normalisers — the wrapped read fns return a mix of shapes: a bare        #
# pydantic model, ``(model, warnings)``, ``(dict, warnings)``, a list of        #
# models, or ``None``. These collapse every shape to a JSON-serialisable dict   #
# so the agent always gets a stable envelope (never a bare list / model / None).#
# --------------------------------------------------------------------------- #
def _jsonable(obj: Any) -> Any:
    """Recursively turn pydantic models into plain dicts; pass primitives through."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    return obj


def _with_warnings(result: tuple[Any, list[str]], key: str) -> dict[str, Any]:
    """Normalise a ``(data, warnings)`` tuple → ``{<key>: data, warnings: [...]}``."""
    data, warnings = result
    return {key: _jsonable(data), "warnings": list(warnings or [])}


# --------------------------------------------------------------------------- #
# Tool logic — plain fns returning JSON-serialisable dicts. Each wraps an        #
# existing read path; kept separate from the FastMCP registration so tests can   #
# exercise the logic without standing up stdio. Every tool returns a dict (never #
# a bare list / model / None) so the agent gets a stable envelope; a missing     #
# entity returns ``{found: False, ...}`` not a crash.                            #
# --------------------------------------------------------------------------- #
def finance_overview() -> dict[str, Any]:
    """Portfolio overview: per-channel allocations, golden-path targets, total value,
    P&L, sparkline. ``{overview, warnings}``. Fail-open (a down price feed → warning,
    not a crash)."""
    return _with_warnings(_fin_overview(), "overview")


def finance_channel(channel: str) -> dict[str, Any]:
    """One portfolio channel's detail (holdings + allocation + sell-ladder state).
    Unknown channel → ``{found: False}``."""
    data, warnings = _fin_channel(channel)
    if data is None:
        return {"found": False, "channel": channel, "warnings": list(warnings or [])}
    return {"found": True, "channel": _jsonable(data), "warnings": list(warnings or [])}


def market_overview() -> dict[str, Any]:
    """Live market view: quotes (+ change%), alert triggers, macro signals, alert
    history. ``{market, warnings}``. Fail-open (feed down → last-known + warning)."""
    return _with_warnings(_mkt_market(), "market")


def market_history(asset: str, hours: int = 24, limit: int = 1000) -> dict[str, Any]:
    """Price-history points for an asset over the last ``hours`` (oldest→newest).
    Empty series if none recorded. ``{asset, points}``."""
    points = _mkt_history(asset, hours=int(hours), limit=int(limit))
    return {"asset": asset, "points": _jsonable(points)}


def market_indicators(symbol: str, indicators: str = "summary",
                      hours: int = 720, full: bool = False) -> dict[str, Any]:
    """Technical indicators over a tracked asset's close series (NEUTRAL data — no
    buy/sell advice). ``indicators`` = comma-separated ∈ {sma,ema,rsi,macd,bollinger,
    atr,summary}. ``{indicators, warnings}``; ``data`` = {symbol, points, asOf,
    indicators:{...}}. Short/empty series → per-indicator warning, never a crash.
    (Wraps the GET /market/indicators read path.)"""
    names = [n.strip() for n in indicators.split(",") if n.strip()]
    data, warnings = _mkt_indicators(symbol, names, hours=int(hours), full=bool(full))
    return {"indicators": _jsonable(data), "warnings": list(warnings or [])}


def _is_tracked(symbol: str) -> bool:
    return any(a.get("symbol") == symbol for a in _mkt_tracked())


def market_ohlc(symbol: str, hours: int = 168, interval: int = 60) -> dict[str, Any]:
    """OHLC candles for a TRACKED asset, DERIVED from the close-tick series (the feed
    is close-only, so each bar's O/H/L/C are the first/max/min/last close in the
    ``interval`` (minutes) bucket — NOT exchange candles; each bar's ``ticks`` count
    shows how many observations it aggregates). ``{found, symbol, interval, candles,
    warnings}``. Untracked symbol → ``{found: False}`` (honest, not a crash). Keeps the
    honest close-derived warning. (Wraps the GET /market/ohlc read path.)"""
    if not _is_tracked(symbol):
        return {"found": False, "symbol": symbol}
    bars, warnings = _mkt_candles(symbol, hours=int(hours), interval_minutes=int(interval))
    return {"found": True, "symbol": symbol, "interval": int(interval),
            "candles": _jsonable(bars), "warnings": list(warnings or [])}


def market_watchlist() -> dict[str, Any]:
    """The watchlist with a rich per-symbol view: ``{items:[{symbol,name,price,
    changePct,source,sparkline[],rsi,trend,warning?}], warnings}``. A symbol with no
    series yet still appears (price from the live quote, sparkline empty, rsi/trend
    pending) + a per-row warning — never a crash. RSI/trend are NEUTRAL technical reads
    (no advice). (Wraps the GET /market/watchlist read path.)"""
    items, warnings = _mkt_watchlist()
    return {"items": _jsonable(items), "warnings": list(warnings or [])}


def market_summary() -> dict[str, Any]:
    """ONE-call market read for the agent: the rich watchlist (price/changePct/
    sparkline) + per-symbol NEUTRAL technical signals (RSI + trend from summarize()).
    ``{watchlist, warnings}``. NEUTRAL data only — NO buy/sell advice. Fail-open: a
    symbol with no series still appears with pending technicals + a per-row warning."""
    items, warnings = _mkt_watchlist()
    return {"watchlist": _jsonable(items), "warnings": list(warnings or [])}


# --------------------------------------------------------------------------- #
# NB-FINANCE-MCP — pure-compute analytics, surfaced READ-ONLY. The agent can      #
# run a what-if allocation + read cross-asset correlation / relative strength.    #
# Each wraps a pure service fn (NO portfolio/disk mutation). The MCP layer        #
# bypasses the router, so we replicate the router's INPUT guards here, returning  #
# an honest ``{error}`` dict (NOT a raised HTTPException/traceback to the agent).  #
# --------------------------------------------------------------------------- #
_SIM_VALID_CHANNELS = {"crypto", "etf", "vn", "dry"}


def finance_simulate(allocation: dict[str, float]) -> dict[str, Any]:
    """What-if: shape a HYPOTHETICAL allocation ``{channel: weight}`` and compare it to
    the CURRENT portfolio — HHI / concentration / drift-vs-golden-path / turnover + the
    HHI delta + per-channel delta-vs-current. Weights normalize to 100% (pass %s or $s).
    PURE NUMBERS for the agent to judge — NOT advice, mutates NOTHING (read-only what-if).
    Channels ∈ {crypto,etf,vn,dry}. Bad input (empty / unknown channel / negative weight)
    → ``{error: <reason>}`` (honest, no crash). A zero-sum allocation is accepted →
    None HHI + warning. ``{result, warnings}``. (Wraps the POST /finance/simulate compute.)"""
    if not isinstance(allocation, dict) or not allocation:
        return {"error": "allocation must have at least one channel {channel: weight}"}
    unknown = [ch for ch in allocation if ch not in _SIM_VALID_CHANNELS]
    if unknown:
        return {"error": f"unknown channel(s) {unknown}; valid: {sorted(_SIM_VALID_CHANNELS)}"}
    negative = [ch for ch, w in allocation.items() if w < 0]
    if negative:
        return {"error": f"negative weight(s) for {negative} — weights must be ≥0"}
    result, warnings = _fin_simulate(allocation)
    return {"result": _jsonable(result), "warnings": list(warnings or [])}


def macro_cycle() -> dict[str, Any]:
    """The Investment-Clock RL STATE (FINANCE-ASSISTANT P2): which macro phase we're in —
    ``phase`` ∈ recovery|overheat|stagflation|slowdown|unknown — from growth (INDPRO+UNRATE)
    × inflation (CPI) + the yield-curve regime, with ``qCycle`` = the q-engine's confidence
    (freshness×coverage×agreement) over those axes. ``favored``/``defensive`` are the CLASSIC-
    CLOCK reference map (which asset classes that phase is associated with), NOT advice for the
    user's book. NEUTRAL — data + q. Honest: a mock/missing axis → coverage<1 → lower qCycle +
    a warning; phase 'unknown' if too thin (never a fabricated phase). ``{macroCycle}``."""
    return {"macroCycle": _jsonable(_decision_macro_cycle())}


def decision_weight() -> dict[str, Any]:
    """The DECISION TOWER's tip (FINANCE-ASSISTANT P2): how hard the data says you can bet right
    now. ``weight`` = W = q_cycle × q_macro × q_flow × s_asset — a PURE PRODUCT (a dark layer
    → W=0, "blind = don't bet"; no inter-layer clamp). ``bindingConstraint`` names the dimmest
    layer (where adding data helps most). CRITICAL: ``weight`` (signal strength) and
    ``confidence`` (how much to trust the weight measurement) are TWO SEPARATE numbers — the
    legend spells out the dangerous high-weight+low-confidence quadrant so the agent never
    conflates them. NEUTRAL — a descriptive verdict band + breakdown, NO buy/sell/should verb;
    the agent reads W and decides. ``{decisionWeight}``."""
    return {"decisionWeight": _jsonable(_decision_weight())}


def allocation_target(capital: float | None = None, phase: str | None = None,
                      monthly_add: float = 0.0, horizon_years: float = 3.0) -> dict[str, Any]:
    """A NEUTRAL reference weighting (FINANCE-ASSISTANT P3): given your ``capital`` (USD) and the
    macro ``phase`` (defaults to the live macro_cycle phase), the classic Investment-Clock + your
    capital-size implies these reference channel weights — with per-channel ``rationale``, the
    delta ``vsStaticGoldenPath``, and a ``confidence``. Capital-tier thresholds are user-
    configurable. ``capital`` is OPTIONAL (FINANCE-FINISH G2): omit it → uses your LIVE portfolio
    value (finance totalValue); pass one → a what-if at that size. NEUTRAL — a MODEL ASSUMPTION
    surfaced as DATA (the classic clock + your capital size), NOT an instruction to act; the
    agent/user reasons + decides. ``{allocation}``."""
    cap = float(capital) if capital is not None else None
    return {"allocation": _jsonable(_decision_allocation(
        cap, phase=phase, monthly_add=float(monthly_add),
        horizon_years=float(horizon_years)))}


def finance_guardian() -> dict[str, Any]:
    """The PROACTIVE scan (FINANCE-ASSISTANT P3): NEUTRAL observations the user hasn't asked about
    — each a real-data FACT + evidence, framed as a QUESTION (never 'you should X'). e.g. 'crypto
    is 98% stablecoin while Fear&Greed reads 23 — intentional bet?'. Real-data-ONLY: a mock/empty
    source does NOT fire (firing on mock would fabricate concern). Severity-ranked; honest-empty
    (a note, not a fabricated alert) when nothing notable. The agent reads the observations and
    reasons — the tool never tells the user what to DO. ``{guardian}``."""
    return {"guardian": _jsonable(_decision_guardian())}


def nav_history(date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    """The daily NET-ASSET-VALUE series (FINANCE-ASSISTANT P4): your total portfolio value per
    day → ``{series:[{date, nav}], points, range, confidence, warning}``. ``date_from``/
    ``date_to`` ('YYYY-MM-DD', optional → full series). ``confidence`` rises with the point count
    — a SHORT series can't be trusted for a trend (few points → low confidence + a warning).
    Honest-empty: no snapshots yet → series:[], points:0, confidence:0 + a warning (the daily
    series is still accumulating), never a crash. NEUTRAL — data + confidence; long-term metrics
    (CAGR/drawdown/volatility) need a longer series (not in this tool). ``{navHistory}``."""
    # by_alias so range carries `from`/`to` (the spec §1.6 shape), not `from_`.
    return {"navHistory": _decision_nav_history(date_from=date_from, date_to=date_to).model_dump(by_alias=True)}


def finance_analytics() -> dict[str, Any]:
    """Portfolio analytics over the live overview: actionable REBALANCE amounts (per channel,
    the |USD| to move to hit its golden-path target + buy/sell/hold), RISK metrics
    (concentration: top-holding %, top-3 %, HHI; total drift; rebalance distance), and RETURN
    metrics (period return + volatility, when a value series exists). ``{analytics, warnings}``.
    PURE NEUTRAL NUMBERS — explicitly NOT advice (no buy/sell/recommend); the agent reasons.
    Fail-open: an empty portfolio → zeroed/None metrics + warnings, never a crash. (Wraps the
    GET /finance/analytics read path — read-only, mutates nothing.)"""
    return _with_warnings(_fin_analytics(), "analytics")


def _parse_symbols_mcp(symbols: str | list[str], *, min_n: int) -> tuple[list[str], str | None]:
    """De-dupe + uppercase the symbols (str CSV or list); enforce min_n..MAX bounds.
    Returns (parsed, error) — error is a string when invalid, else None (mirrors the
    router's _parse_symbols 422 guards but as an honest error string, not a raise)."""
    raw = symbols.split(",") if isinstance(symbols, str) else list(symbols)
    parsed: list[str] = []
    seen: set[str] = set()
    for s in raw:
        sym = str(s).strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            parsed.append(sym)
    if len(parsed) < min_n:
        return parsed, f"need ≥{min_n} distinct symbols (got {len(parsed)})"
    if len(parsed) > _MAX_CORR_SYMBOLS:
        return parsed, f"too many symbols ({len(parsed)}); max {_MAX_CORR_SYMBOLS}"
    return parsed, None


def market_correlation(symbols: str, hours: int = 720) -> dict[str, Any]:
    """Pairwise Pearson correlation matrix over the close series of ≥2 comma-separated
    symbols (≤10; N² so bounded). Each cell ∈ [-1, 1] or None (no overlap / flat series —
    honest, not fabricated 0). NEUTRAL numbers — no advice. <2 or >10 symbols →
    ``{error}`` (honest, no crash). ``{correlation, warnings}``. (Wraps GET
    /market/correlation — read-only.)"""
    syms, err = _parse_symbols_mcp(symbols, min_n=2)
    if err:
        return {"error": err}
    data, warnings = _mkt_correlation(syms, hours=int(hours))
    return {"correlation": _jsonable(data), "warnings": list(warnings or [])}


def market_relative_strength(symbol: str, vs: str = "BTC", hours: int = 720) -> dict[str, Any]:
    """``symbol`` vs a ``vs`` benchmark (default BTC): the price-ratio trend + % change
    over the window. ratioTrend 'up' = OUTPERFORMING the benchmark (NEUTRAL observation,
    NOT a recommendation). Thin data → None fields + a warning, never fabricated.
    ``{relativeStrength, warnings}``. (Wraps GET /market/relative-strength — read-only.)"""
    data, warnings = _mkt_rel_strength(symbol.strip().upper(), vs=vs.strip().upper(), hours=int(hours))
    return {"relativeStrength": _jsonable(data), "warnings": list(warnings or [])}


def projects_list() -> dict[str, Any]:
    """All tracked, non-abandoned projects with derived health/commit/lang status.
    ``{projects, warnings}``. Fail-open per-project."""
    return _with_warnings(_proj_list(), "projects")


def project_get(project_id: str) -> dict[str, Any]:
    """One project's status by id (includes abandoned). Unknown id →
    ``{found: False}``."""
    status = _proj_get(project_id)
    if status is None:
        return {"found": False, "project_id": project_id}
    return {"found": True, "project": _jsonable(status)}


def graveyard_overview() -> dict[str, Any]:
    """The graveyard: abandoned projects + post-mortem pattern aggregates.
    ``{graveyard}``. Fail-open (empty → all-zero stats)."""
    return {"graveyard": _jsonable(_grave_get())}


def claude_usage(window: str = "5h", verbose: bool = False) -> dict[str, Any]:
    """Claude token-usage view. LEAN by DEFAULT (CLAUDE-USAGE-LEAN #18, agent-first): the few
    numbers an agent usually wants — leading with the LIVE quota signal (pct5h / resetIn / weekly)
    + today's tokens + costUSD ($.01) + provenance. ``verbose=true`` returns the FULL shape (the
    per-day series + by-model + by-project splits + the context-window fields).

    Why lean leads with pct5h/resetIn, NOT remaining: ``remaining`` is cap − used, but ``cap`` is
    a PLACEHOLDER (200k, NOT from disk — there's no rate-limit ceiling readable). With used ≫ cap,
    remaining is honest-null. The REAL quota answer is the live ``pct5h``/``resetIn``/``weekly``
    (the statusline snapshot). remaining STAYS honest-null (never faked from the placeholder cap);
    when it's null-due-to-placeholder, the lean view carries a ``remainingNote`` saying so + where
    the real signal is (the same honest-null-WITH-reason pattern as dxy.warning).

    ``window`` accepted for the API contract. Fail-open to manual/stub if no local stats. The REST
    GET /claude-usage + the FE consume the FULL model unchanged — this lean projection is the MCP
    tool's presentation only (service.get_usage returns the full shape)."""
    u = _jsonable(_claude_usage(window=window))

    # costUSD → 2 decimals (cumulative magnitude is a KNOWN item; just format). Underlying precise.
    cost_raw = u.get("costUSD")
    cost_fmt = round(float(cost_raw), 2) if isinstance(cost_raw, (int, float)) else cost_raw

    if verbose:
        # FULL shape — keep everything; only normalize costUSD to 2 decimals for consistency.
        u["costUSD"] = cost_fmt
        return {"usage": u, "verbose": True}

    # LEAN (default): the agent-readable ~8-field slice. Lead with the LIVE quota signal.
    lean: dict[str, Any] = {
        "pct5h": u.get("pct5h"),
        "resetIn": u.get("resetIn"),
        "weekly": u.get("weekly"),
        "today": u.get("today"),
        "costUSD": cost_fmt,
        "remaining": u.get("remaining"),       # honest-null when cap is a placeholder (see note)
        "quotaSource": u.get("quotaSource"),
        "tokenSource": u.get("tokenSource"),
    }
    # honest-null-WITH-reason (the dxy.warning pattern): remaining is null because the cap is a
    # placeholder (used > cap), NOT because quota is exhausted. Tell the agent where the real
    # signal is. Only when null-due-to-placeholder; a real manual-override cap (used ≤ cap) →
    # remaining computes → no note.
    if lean["remaining"] is None:
        lean["remainingNote"] = ("cap is a placeholder (not from disk); use pct5h/resetIn for "
                                 "the live quota signal")
    return {"usage": lean, "verbose": False}


def reminders_list(filter: str = "today") -> dict[str, Any]:
    """What's on the user's plate: reminders by ``filter`` (today|week|undone|all; unknown →
    lenient all). REMINDERS-2 (#28): so ANY agent on lifeos-read sees the agenda without a 2nd
    connection. Agent-first lean shape — the filtered list + counts (not a dump): each reminder is
    {id, title, due_at(UTC), repeat, done_at}; plus count + undoneCount + the filter applied. The
    SAME fn is exposed on the lifeos-reminders server (is-identity). Read-only (no mutation)."""
    view, warnings = _reminders_list(filter)
    return {
        "reminders": [{"id": r.id, "title": r.title, "due_at": r.due_at,
                       "repeat": r.repeat, "done_at": r.done_at} for r in view.reminders],
        "count": view.count,
        "undoneCount": view.undoneCount,
        "filter": view.filter,
        "warnings": list(warnings or []),
    }


def daily_brief() -> dict[str, Any]:
    """Generate today's brief on the fly from live reads: prioritised actions +
    summary across market / projects / finance / Claude. ``{brief}``. Fail-soft per
    source. (Read-only: assembles, does NOT persist.)"""
    return {"brief": _jsonable(_brief_generate())}


def brief_history(limit: int = 30) -> dict[str, Any]:
    """Past persisted briefs (newest-first). ``{briefs}``. [] if none persisted."""
    return {"briefs": _jsonable(_brief_history(limit=int(limit)))}


def journal_entries(action: str | None = None, tag: str | None = None,
                    channel: str | None = None, asset: str | None = None) -> dict[str, Any]:
    """Trade journal: entries matching the optional filters (newest-first) + derived
    win-rate / P&L stats over the filtered set. ``{journal, warnings}``."""
    return _with_warnings(
        _journal_list(action=action, tag=tag, channel=channel, asset=asset), "journal")


def decision_entries(domain: str | None = None, status: str | None = None) -> dict[str, Any]:
    """Decision journal: entries matching the optional filters (newest-first) +
    calibration stats over the filtered set. ``{decisions, warnings}``."""
    return _with_warnings(_decision_list(domain=domain, status=status), "decisions")


def activity_feed(routine: str | None = None, status: str | None = None,
                  range: str | None = None) -> dict[str, Any]:
    """Automation activity feed: routine runs (newest-100) + roll-up stats, filters
    optional + lenient. ``{activity}``. Fail-open."""
    return {"activity": _jsonable(_activity_feed(routine=routine, status=status, range=range))}


def activity_run(run_id: int) -> dict[str, Any]:
    """One routine run's detail by id. Unknown id → ``{found: False}``."""
    run = _activity_run(int(run_id))
    if run is None:
        return {"found": False, "run_id": int(run_id)}
    return {"found": True, "run": _jsonable(run)}


def exchange_overview() -> dict[str, Any]:
    """OKX exchange overview: balances + open positions snapshot. ``{exchange,
    warning}``. Never raises; not-configured → an honest empty overview + warning."""
    data, warning = _exch_overview()
    return {"exchange": _jsonable(data), "warning": warning}


def app_settings() -> dict[str, Any]:
    """The app config (thresholds, toggles, usage cap …) the agent should respect.
    ``{settings}``. Read-only."""
    return {"settings": _jsonable(_settings_get())}


def reliability_report() -> dict[str, Any]:
    """The reliability suite report: grounding-eval + fail-closed gates. ``{report}``.
    READ-ONLY (verifies against an existing note; never writes). Empty vault → the
    grounding check is reported skipped (honest)."""
    return {"report": _jsonable(_reliability_suite())}


def macro_overview() -> dict[str, Any]:
    """Macro economic context: latest Fed funds rate / US CPI / DXY dollar index + a
    DESCRIPTIVE trend (up/down/flat vs the prior observation). ``{macro, warnings}``.
    NEUTRAL — observed data, NO forecast; the agent reasons about portfolio impact. A
    mock source (no FRED key) still returns values, tagged source='mock' + a warning so
    the agent knows it's a placeholder, not live. (Wraps GET /macro/overview.)"""
    overview, warnings = _macro_overview()
    return {"macro": _jsonable(overview), "warnings": list(warnings or [])}


def macro_history(indicator: str, days: int = 365) -> dict[str, Any]:
    """One macro indicator's time-series over the last ``days`` (oldest→newest).
    ``indicator`` ∈ {fed_funds_rate, cpi, dxy}. Unknown indicator → ``{found: False}``
    (honest, not a crash). ``{found, history}``. (Wraps GET /macro/history.)"""
    hist = _macro_history(indicator, days=int(days))
    if hist is None:
        return {"found": False, "indicator": indicator}
    return {"found": True, "history": _jsonable(hist)}


def news_digest(tag: str | None = None, limit: int = 10) -> dict[str, Any]:
    """A NEUTRAL, source-cited roll-up of the grounded news the module has captured.
    Each item carries its source url + published_ts. NO sentiment / advice / forecast —
    it ONLY lists what's in the store. Honest empty-state when nothing has been captured
    (never invents a headline). ``tag`` filters by exact tag (no match → empty). ``{headline,
    items, count, asOf, note}``. (Wraps GET /news/digest — read-only; capture is human/poller.)"""
    return {"digest": _jsonable(_news_digest(tag, limit=int(limit)))}


def news_list(tag: str | None = None, limit: int = 30) -> dict[str, Any]:
    """Raw captured headlines, newest-first — each with source url + published_ts.
    ``tag`` filters by exact tag (unknown tag → empty). NEUTRAL (headlines only, no
    commentary). ``{items, count, asOf, tag}``. (Wraps GET /news — read-only.)"""
    return {"news": _jsonable(_news_list(tag, limit=int(limit)))}


# --------------------------------------------------------------------------- #
# WIKI tools removed (MCP-DEDUP #70): these were DUPLICATES of the canonical      #
# standalone wiki MCP server (modules/wiki/mcp/, mounted at /mcp/wiki-read). The  #
# 4 read dupes (wiki_search/wiki_get→wiki_get_note/wiki_overview/wiki_backlinks)  #
# live there already; wiki_proposal_status + wiki_list_proposals were PORTED to   #
# the standalone read_server first (port-before-delete). NO wiki capability lost  #
# — the standalone is the single source. The _wiki_search/_wiki_overview imports  #
# are KEPT above because life_brief (_brief_wiki) + insights (_brief_decision)    #
# still consume them — those are NOT wiki MCP tools.                              #
# --------------------------------------------------------------------------- #
# Proposal feedback (MCP-5) — the agent READS the disposition of its own         #
# proposals so it can learn (a rejected proposal → propose differently next      #
# time). READ-ONLY: these report the human's verdict; the agent CANNOT accept/   #
# reject (that is human-only, gated at the /agent-proposals REST surface).       #
# --------------------------------------------------------------------------- #
def check_proposal_status(proposal_id: int) -> dict[str, Any]:
    """One proposal's disposition by id: status (pending|accepted|rejected),
    appliedRef (the entry id an accept created), applyError (why an accept couldn't
    apply), decidedBy + decided (who ratified, when). Unknown / malformed id →
    ``{found: False}`` (honest, not a crash/traceback — NG4). READ-ONLY."""
    # NG4: a non-int id (e.g. "nope123") must not leak a raw ValueError to the agent.
    try:
        pid = int(proposal_id)
    except (ValueError, TypeError):
        return {"found": False, "proposalId": proposal_id}
    p = _proposal_get(pid)
    if p is None:
        return {"found": False, "proposalId": pid}
    return {
        "found": True,
        "proposalId": p["id"],
        "module": p["module"],
        "kind": p["kind"],
        "status": p["status"],
        "appliedRef": p.get("appliedRef"),
        "applyError": p.get("applyError"),
        "decidedBy": p.get("decidedBy"),
        "decided": p.get("decided"),
        "rationale": p.get("rationale"),
    }


def list_my_proposals(status: str | None = None, limit: int = 50) -> dict[str, Any]:
    """The agent's proposals (newest-first) with their current disposition — the review
    queue from the agent's POV, so it can see what's still pending vs accepted/rejected.
    Optional ``status`` filter (pending|accepted|rejected). Empty → ``{proposals: []}``.
    READ-ONLY."""
    proposals = _proposal_list(status=status, limit=int(limit))
    return {"proposals": _jsonable(proposals)}


def proposal_stats() -> dict[str, Any]:
    """Counts of the agent's proposals by status (pending/accepted/rejected) so the
    agent can self-assess its acceptance rate. Empty queue → all-zero. READ-ONLY."""
    counts = _proposal_counts()
    accepted = counts.get("accepted", 0)
    rejected = counts.get("rejected", 0)
    decided = accepted + rejected
    return {
        "counts": {
            "pending": counts.get("pending", 0),
            "accepted": accepted,
            "rejected": rejected,
        },
        # acceptanceRate over DECIDED proposals (None if none decided yet — honest, not 0)
        "acceptanceRate": round(accepted / decided, 3) if decided else None,
    }


# --------------------------------------------------------------------------- #
# Tool catalog (MCP-8) — a discoverable, machine-readable index of the WHOLE     #
# agent toolkit so a future agent can ASK "what can I do?" instead of guessing.  #
# DERIVED from the live TOOLS registries (read here + write lazily) — NEVER a     #
# hand-maintained second list, so it cannot drift (the catalog-derive-from-NAV   #
# lesson). READ/metadata only: it lists capabilities, it does not grant them.    #
# --------------------------------------------------------------------------- #
def _one_line(fn: Callable[..., Any]) -> str:
    """First non-empty line of a tool's docstring (its 1-line description)."""
    doc = (fn.__doc__ or "").strip()
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line.rstrip(".")
    return ""


def _is_neutral(fn: Callable[..., Any]) -> bool:
    """True if the tool's docstring declares it NEUTRAL (no advice) — the market/brief
    analysis tools assert this; the catalog surfaces it so the agent knows the data
    carries no buy/sell signal and IT must do the reasoning."""
    return "neutral" in (fn.__doc__ or "").lower()


# ALL mounted MCP servers (#32) — mirrors main.py's _MCP_MOUNTS so the catalog walks EVERY mount,
# not just the shared read+write. Each entry: (server-label, module-path, capability). The label is
# the agent-facing server name (matches the /mcp/<label> mount); capability is "read" (read-only
# servers) or "propose" (write/proposal servers). A test asserts this list stays in sync with
# main._MCP_MOUNTS so a new mount can't be silently missed. Modules are imported LAZILY inside
# list_tools_catalog() (NEVER at module top-level) for metadata only — keeps this read-server's
# no-write-gate namespace pristine (test_catalog_does_not_grant_write_capability).
_CATALOG_MOUNTS: list[tuple[str, str, str]] = [
    ("read", "mcp_servers.read_server", "read"),
    ("write", "mcp_servers.write_server", "propose"),
    ("wiki-read", "modules.wiki.mcp.read_server", "read"),
    ("wiki-write", "modules.wiki.mcp.write_server", "propose"),
    ("finance", "mcp_servers.finance_server", "read"),
    ("reminders", "mcp_servers.reminders_server", "read"),
]


def list_tools_catalog() -> dict[str, Any]:
    """The agent's self-discovery index: every MCP tool across ALL MOUNTED SERVERS as
    machine-readable metadata so an agent can enumerate its own capabilities instead of
    hard-coding tool names. Each entry: {name, server (the mount label), capability
    (read|propose), neutral (bool), description (1-line)}.

    #32: walks EVERY mount in _CATALOG_MOUNTS (read, write, wiki-read, wiki-write, finance,
    reminders) — mirroring main.py's _MCP_MOUNTS — not just the shared read+write. Each
    module is DERIVED from its live TOOLS registry, imported LAZILY for metadata only (name +
    docstring; the propose/write fns are NEVER called here), so the catalog can never drift
    from what the servers actually mount, and building it binds NO write symbol into this
    read-server's namespace (the no-write gate stays pristine).

    NOTE on per-mount counts (the honest "what THIS agent sees" view): a tool can appear under
    MORE THAN ONE mount — e.g. the 15 finance tools are reference-imported by the /mcp/finance
    domain server AND already in /mcp/read, so they're listed under BOTH ("finance" and "read").
    That is CORRECT: a finance-scoped agent on /mcp/finance sees 15; a general agent on /mcp/read
    sees the full read set. ``counts`` carries a per-mount breakdown; ``counts.read``/``write``/
    ``total`` are KEPT for backward-compat (read = the shared read-server, write = the shared
    write-server, total = read+write — the historical meaning consumers rely on).

    CAPABILITY BOUNDARY (stated explicitly so the agent reasons within it):
      - READ servers (read, wiki-read, finance, reminders-read) only read; they write NOTHING.
      - WRITE/PROPOSE servers (write, wiki-write) only ENQUEUE proposals (status=pending) — the
        agent PROPOSES; it can NEVER apply/accept its own proposal. Applying is HUMAN-ONLY, via
        the /agent-proposals REST surface (human disposes). The agent can READ the verdict back
        (check_proposal_status / list_my_proposals / proposal_stats) to learn, but cannot ratify.
        (reminders is a reversible single-user direct-write domain — labelled capability "read"
        for its read tool; its write tools, if surfaced, propose nothing — out of the proposal gate.)
      - Analysis tools are NEUTRAL data (no buy/sell advice); the agent does the reasoning.
    READ-ONLY: this tool lists capabilities; it does not grant any."""
    import importlib

    tools: list[dict[str, Any]] = []
    per_mount: dict[str, int] = {}
    for label, mod_path, capability in _CATALOG_MOUNTS:
        # lazy import for METADATA only — never bound at module level, never invoked.
        mod = importlib.import_module(mod_path)
        mount_tools = getattr(mod, "TOOLS", {})
        per_mount[label] = len(mount_tools)
        for name, fn in mount_tools.items():
            tools.append({
                "name": name, "server": label, "capability": capability,
                "neutral": _is_neutral(fn), "description": _one_line(fn),
            })
    return {
        "tools": tools,
        "counts": {
            # backward-compat: read = shared read-server, write = shared write-server, total = both.
            "read": per_mount.get("read", 0),
            "write": per_mount.get("write", 0),
            "total": per_mount.get("read", 0) + per_mount.get("write", 0),
            # #32: the full per-mount breakdown (every mount, incl. wiki/finance/reminders).
            "byMount": per_mount,
            "allMounts": len(tools),
            # per-mount counts can OVERLAP where a domain server reference-imports shared fns
            # (e.g. /mcp/finance's 15 are the SAME fn objects as 15 of /mcp/read's; reminders_list
            # is on both /mcp/read and /mcp/reminders). So sum(byMount) > distinct tool count — that
            # is the honest "what THIS agent sees per mount" view, NOT inflation of distinct tools.
            "note": "per-mount counts overlap where a domain server reference-imports shared fns; "
                    "allMounts is the listing length (with overlaps), not the distinct-fn total.",
        },
        "capabilityBoundary": {
            "read": "reads only — writes nothing",
            "write": "ENQUEUE proposals only (status=pending) — agent proposes, "
                     "cannot apply/accept its own proposal",
            "apply": "HUMAN-ONLY via POST /agent-proposals/{id}/accept — the agent "
                     "never has an apply/accept handle (proven by capability-gate tests)",
            "feedback": "agent READS its verdict via check_proposal_status / "
                        "list_my_proposals / proposal_stats — read-only, cannot ratify",
            "neutrality": "analysis tools return NEUTRAL data (no buy/sell advice); "
                          "the agent does the reasoning",
        },
    }


# --------------------------------------------------------------------------- #
# life_brief — the AGENT DATA-LAYER synthesizer (MCP-2). ONE tool composes the   #
# read paths into a single neutral, SOURCE-TAGGED snapshot of the user's life so #
# an external agent gets the whole picture in one call instead of 10 separate    #
# ones, then reasons itself. NEUTRAL: it aggregates DATA only — it gives NO       #
# advice, NO buy/sell signal, NO prioritisation. Every section carries a          #
# ``source`` (which module the numbers came from) so the agent can trace + cite. #
# Fail-soft PER SECTION: one source raising must NOT 500 the whole brief — that   #
# section reports ``{error: <str>, source}`` and the rest still assembles (an     #
# empty / unconfigured app still yields a full-shaped brief).                     #
# --------------------------------------------------------------------------- #
def _section(source: str, build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run one brief section's builder fail-soft. Always returns a dict carrying a
    ``source`` tag; on failure → ``{source, error}`` instead of propagating."""
    try:
        out = build()
        out["source"] = source
        return out
    except Exception as exc:  # noqa: BLE001 — one bad source must not break the brief
        return {"source": source, "error": f"{type(exc).__name__}: {exc}"}


def _brief_portfolio() -> dict[str, Any]:
    """Neutral finance snapshot: total value, change, P&L, dry powder, per-channel
    allocation %. Numbers from modules/finance (get_overview)."""
    ov, warnings = _fin_overview()
    return {
        "totalValue": ov.totalValue,
        "change": _jsonable(ov.change),
        # FINANCE-AUDIT2 (#66): pnlTotal is now the BASIS-KNOWN per-coin sum (honest direction,
        # was a fake +$7); pnlScope carries the coverage % + note so an agent doesn't misread
        # a −X% on the basis-known slice (often a few % of the book) as a whole-portfolio loss.
        "pnlTotal": _jsonable(ov.pnlTotal),
        "pnlScope": _jsonable(ov.pnlScope),
        "dryPowder": ov.dryPowder,
        "allocations": [
            {"channel": a.channel, "value": a.value,
             "pct": getattr(a, "pct", None), "target": getattr(a, "target", None)}
            for a in ov.allocations
        ],
        "holdingCount": len(ov.holdings),
        "warnings": list(warnings or []),
    }


def _brief_market(indicators: str = "summary", hours: int = 720) -> dict[str, Any]:
    """Neutral market snapshot: per TRACKED asset, latest quote + its TA indicators
    (default the ``summary`` block — neutral technical readout, NO advice). Quotes
    from modules/market (get_market); indicators from the /market/indicators TA read
    path (compute_indicators)."""
    data, mkt_warn = _mkt_market()
    quotes = data.get("quotes", []) if isinstance(data, dict) else []
    warnings = list(mkt_warn or [])
    names = [n.strip() for n in indicators.split(",") if n.strip()]
    per_asset: list[dict[str, Any]] = []
    for asset in _mkt_tracked():
        symbol = asset.get("symbol")
        if not symbol:
            continue
        quote = next((q for q in quotes if q.get("symbol") == symbol), None)
        try:
            ind_data, ind_warn = _mkt_indicators(symbol, names, hours=int(hours), full=False)
            indicators_out = ind_data.get("indicators") if isinstance(ind_data, dict) else None
            warnings.extend(f"{symbol}: {w}" for w in (ind_warn or []))
        except Exception as exc:  # noqa: BLE001 — a bad TA read must not drop the asset
            indicators_out = None
            warnings.append(f"{symbol}: indicators failed ({type(exc).__name__}: {exc})")
        per_asset.append({
            "symbol": symbol,
            "quote": _jsonable(quote),
            "indicators": _jsonable(indicators_out),
        })
    return {"assets": per_asset, "indicatorSet": names, "warnings": warnings}


def _brief_projects() -> dict[str, Any]:
    """Neutral project snapshot: counts by health + the IDLE set (health ∈
    {slow,stall,dead}) with days-since-commit. From modules/projects (list_projects).
    No prioritisation — just which projects haven't moved."""
    statuses, warnings = _proj_list()
    by_health: dict[str, int] = {}
    idle: list[dict[str, Any]] = []
    for s in statuses:
        by_health[s.health] = by_health.get(s.health, 0) + 1
        if s.health in ("slow", "stall", "dead"):
            idle.append({"id": s.id, "name": s.name, "health": s.health,
                         "lastDays": s.lastDays, "progress": s.progress})
    return {
        "total": len(statuses),
        "byHealth": by_health,
        "idle": idle,
        "warnings": list(warnings or []),
    }


def _brief_claude() -> dict[str, Any]:
    """Neutral Claude-usage snapshot: today's tokens, cap, used %, remaining, 5h/weekly
    reset. From modules/claude_usage (get_usage). Fail-open to stub if no local stats."""
    u = _claude_usage()
    return {
        "today": u.today, "used": u.used, "cap": u.cap, "pct": u.pct,
        "remaining": u.remaining, "resetIn": u.resetIn, "weekly": u.weekly,
        "quotaSource": u.quotaSource, "stale": u.stale,
    }


def _brief_decisions() -> dict[str, Any]:
    """Neutral decision snapshot: the OPEN (status=open) decisions awaiting an outcome
    + calibration counts. From modules/decision_journal (list_entries). No advice.

    JOURNAL-NUDGE (#14, SPEC §172): closes the dark journal loop for an MCP agent reading
    life_brief —
      - ``note`` when ZERO decisions are logged at all (calibration/brier idle = CORRECT for 0
        resolved, not a bug; the loop just has no data yet — honest, not alarming).
      - ``pendingNudges``: the OPEN rung-triggered nudges (a buy-ladder rung was entered → log a
        decision). So the agent sees rung-hit + pending nudge + 0-logged and prompts the user.
        Honest-empty (never fabricated); the nudges themselves NEVER wrote a journal entry."""
    stats, warnings = _decision_list(status="open")
    out: dict[str, Any] = {
        "openCount": len(stats.entries),
        "open": [{"id": e.id, "decision": e.decision, "domain": e.domain,
                  "date": e.date, "confidence": getattr(e, "confidence", None)}
                 for e in stats.entries],
        "warnings": list(warnings or []),
    }
    # the TOTAL logged (across all statuses) — 0 → flag the dark loop honestly.
    try:
        all_stats, _ = _decision_list()
        total_logged = len(all_stats.entries)
        out["totalLogged"] = total_logged
        if total_logged == 0:
            out["note"] = ("0 decisions logged — calibration/brier idle; the journal loop has no "
                           "data yet (log a decision to start tracking)")
    except Exception as exc:  # noqa: BLE001 — best-effort; never break the brief section
        out.setdefault("warnings", []).append(f"decision total read failed: {exc}")
    # ALWAYS surface the open rung-triggered nudges (honest-empty when none).
    try:
        from store import db as _db
        out["pendingNudges"] = [
            {"id": r["id"], "channel": r["channel"], "rung": r["rung"],
             "triggerPrice": r["trigger_price"], "observedPrice": r["observed_price"],
             "ts": r["ts"], "status": r["status"]}
            for r in _db.pending_journal_nudges(limit=20)
        ]
    except Exception as exc:  # noqa: BLE001
        out["pendingNudges"] = []
        out.setdefault("warnings", []).append(f"pending nudges read failed: {exc}")
    return out


def _brief_reminders() -> dict[str, Any]:
    """REMINDERS-4 (#30): what's on the user's plate — the un-done reminders that are OVERDUE or
    due-today or due-this-week (the GAP-4 'what's on my plate this week' question). Reuses the #29
    reminders reader (overdue field + today/week filters); LEAN per item {id,title,due_at,overdue}
    (the #18/reminders_list precedent — NOT the full 10-field reminder). SORTED overdue→today→week,
    due_at asc within each band. Honest-empty → {reminders:[], count:0, overdueCount:0} (never
    omitted/fabricated). De-duped by id (overdue overlaps today/week). source added by _section."""
    # the 'week' filter (due ≤ now+7d AND un-done) is the superset of today+overdue-within-a-week;
    # but an OVERDUE reminder can be MORE than a week past due, so union 'week' with 'undone'-overdue.
    week_view, _w = _reminders_list("week")        # un-done, due ≤ now+7d
    undone_view, _u = _reminders_list("undone")    # all un-done (to catch overdue >1wk past)
    by_id: dict[int, Any] = {}
    for r in week_view.reminders:
        by_id[r.id] = r
    for r in undone_view.reminders:
        if r.overdue and r.id not in by_id:        # include overdue even if >1 week past due
            by_id[r.id] = r
    items = list(by_id.values())

    # band: overdue (0) → due-today (1) → this-week (2); within band by due_at asc.
    today_end = (datetime.now(timezone.utc)
                 .replace(hour=23, minute=59, second=59, microsecond=999999).isoformat())

    def _band(r) -> int:
        if r.overdue:
            return 0
        return 1 if r.due_at <= today_end else 2

    items.sort(key=lambda r: (_band(r), r.due_at))
    lean = [{"id": str(r.id), "title": r.title, "due_at": r.due_at, "overdue": r.overdue}
            for r in items]
    return {
        "reminders": lean,
        "count": len(lean),
        "overdueCount": sum(1 for r in items if r.overdue),
    }


def _brief_macro() -> dict[str, Any]:
    """Neutral macro snapshot (R2-G1): latest Fed funds rate / US CPI / DXY + a
    DESCRIPTIVE trend. From modules/macro (get_overview → (data, warnings)). NEUTRAL —
    observed data, NO forecast. Honest on a mock source (tagged source='mock')."""
    overview, warnings = _macro_overview()
    return {"macro": _jsonable(overview), "warnings": list(warnings or [])}


def _brief_news() -> dict[str, Any]:
    """Neutral news snapshot (R2-G1): a source-cited digest of the captured headlines
    (each cites its url). From modules/news (digest). NEUTRAL — lists what's captured,
    NO sentiment. Honest-empty when nothing captured (never invents a headline)."""
    return {"digest": _jsonable(_news_digest(None, limit=5))}


def _brief_wiki() -> dict[str, Any]:
    """Neutral wiki snapshot (R2-G1): vault overview (stats / inbox / orphans /
    recentActivity). From modules/wiki (reader.overview → (data, warning)). Honest-
    empty vault → pctWithLink None + a warning, never a crash."""
    data, warning = _wiki_overview()
    return {"overview": _jsonable(data), "warning": warning}


def _brief_decision() -> dict[str, Any]:
    """Neutral DECISION-TOWER snapshot (FINANCE-FINISH G1): the assistant's tip composed from
    the tower fns — ``{weight, verdict, bindingConstraint, phase, topGuardianAlert}``. weight/
    verdict/bindingConstraint from decision_weight (W=∏q + the neutral band + the dimmest layer);
    phase from macro_cycle (the Investment-Clock state); topGuardianAlert = the highest-severity
    proactive observation's msg (or None — honest-empty when nothing fired). NEUTRAL: a band, a
    state label, and a question — no advice. (Composes the tower read-only; never rebuilds it.)"""
    dw = _decision_weight()
    cyc = _decision_macro_cycle()
    guardian = _decision_guardian()
    # the guardian's alerts are already severity-ranked (high→low); the first is the top one.
    alerts = guardian.alerts if guardian is not None else []
    top_alert = alerts[0].msg if alerts else None   # honest-empty: None when nothing fired
    return {
        "weight": dw.weight,
        "verdict": dw.verdict,
        "bindingConstraint": dw.bindingConstraint,
        "phase": cyc.phase,
        "topGuardianAlert": top_alert,
    }


def life_brief(indicators: str = "summary", market_hours: int = 720) -> dict[str, Any]:
    """THE agent data-layer: ONE call → a neutral, source-tagged snapshot of the
    user's life composed from the per-module read paths, so an external agent gets the
    whole picture without firing 10 separate tools, then reasons itself.

    Sections (each tagged with its ``source`` module; each fail-soft — a down source
    reports ``{error}`` and the brief still assembles):
      - ``portfolio`` (finance):  total value / change / P&L / dry powder / allocations
      - ``market``    (market + TA /indicators):  per tracked asset → quote + neutral
        technical ``summary`` (override via ``indicators`` = comma-list)
      - ``projects``  (projects): health counts + the IDLE set (slow/stall/dead)
      - ``claude``    (claude_usage): today's tokens / cap / used% / remaining / reset
      - ``decisions`` (decision_journal): OPEN decisions awaiting an outcome
      - ``macro``     (macro): Fed funds / CPI / DXY + descriptive trend (R2-G1)
      - ``news``      (news): source-cited digest of captured headlines (R2-G1)
      - ``wiki``      (wiki): vault overview — stats / inbox / orphans (R2-G1)
      - ``decision``  (decision tower): W (weight) + verdict band + bindingConstraint +
        macro phase + the top guardian alert (FINANCE-FINISH G1 — the assistant's tip)

    NEUTRAL: aggregates DATA only — NO advice, NO buy/sell signal, NO prioritisation.
    The agent reads this and decides. An empty / unconfigured app still returns a
    full-shaped brief (honest-empty sections, never a 500)."""
    return {
        "brief": {
            "portfolio": _section("finance", _brief_portfolio),
            "market": _section("market",
                               lambda: _brief_market(indicators=indicators, hours=market_hours)),
            "projects": _section("projects", _brief_projects),
            "claude": _section("claude_usage", _brief_claude),
            "decisions": _section("decision_journal", _brief_decisions),
            "macro": _section("macro", _brief_macro),
            "news": _section("news", _brief_news),
            "wiki": _section("wiki", _brief_wiki),
            # FINANCE-FINISH G1: the decision tower (W/verdict/binding/phase/top-alert), fail-soft.
            "decision": _section("decision", _brief_decision),
            # REMINDERS-4 (#30): what's on the user's plate (overdue+today+week un-done), fail-soft.
            "reminders": _section("reminders", _brief_reminders),
        }
    }


# --------------------------------------------------------------------------- #
# INSIGHTS (D1) — cross-domain OBSERVATIONS over the live read paths. Each rule  #
# is a fail-soft builder returning ONE insight dict (or None = doesn't fire),     #
# carrying evidence + the source modules it read. NEUTRAL: it OBSERVES a cross-   #
# domain pattern in the real data — it never tells the user what to DO (the agent #
# reasons). Honest-empty: no rule fires → []. Severity-ranked (warn > info).      #
# Rules over REAL data only — a rule whose source is a stub/empty simply doesn't  #
# fire (the Fear&Greed rule was DROPPED — its mock source isn't real data).       #
# --------------------------------------------------------------------------- #
# Severity rank for ordering (high → medium → low) — the dispatch's frozen severities.
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_STABLE_UNDEPLOYED_PCT = 90.0  # crypto channel >this% stablecoin → undeployed (cash-equivalent)
_FRAMEWORK_DEPLOYED_PCT = 1.0  # a target channel deployed BELOW this % = effectively un-executed
_STALLED_PROJECT_DAYS = 30     # a project idle ≥ this many days


def _insights_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _insight_undeployed_capital() -> dict[str, Any] | None:
    """Fires when the crypto channel is >90% stablecoin (cash-equivalent) — i.e. capital is
    parked in stables, not deployed to crypto exposure vs its target. NEUTRAL observation of
    a composition fact (NB4 stablePct); no 'deploy it' advice."""
    ov, _ = _fin_overview()
    crypto = next((a for a in ov.allocations if a.channel == "crypto"), None)
    if crypto is None:
        return None
    stable_pct = getattr(crypto, "stablePct", None)
    if stable_pct is None or stable_pct <= _STABLE_UNDEPLOYED_PCT:
        return None
    return {
        "insight": f"crypto channel is {stable_pct:.0f}% stablecoin (cash-equivalent) — "
                   f"undeployed vs target, not crypto exposure",
        "severity": "high",
        "evidence": {"stablePct": stable_pct, "dryPowder": ov.dryPowder,
                     "cryptoTarget": getattr(crypto, "target", None)},
        "sources": ["finance_overview"],
    }


def _insight_all_crypto_overbought() -> dict[str, Any] | None:
    """Fires when ≥2 tracked crypto assets are ALL technically overbought (RSI≥70 → the
    neutral summary rsi_signal). One overbought asset ≠ 'all' — doesn't fire. NEUTRAL
    technical observation — NOT 'sell'."""
    crypto = [a for a in _mkt_tracked() if a.get("assetClass") == "crypto" and a.get("symbol")]
    if len(crypto) < 2:
        return None
    per_asset: dict[str, Any] = {}
    all_overbought = True
    for a in crypto:
        sym = a["symbol"]
        ind, _ = _mkt_indicators(sym, ["summary"], hours=720, full=False)
        summary = (ind.get("indicators", {}) or {}).get("summary", {}) if isinstance(ind, dict) else {}
        sig = (summary.get("signals", {}) or {}).get("rsi")
        per_asset[sym] = (summary.get("latest", {}) or {}).get("rsi")
        if sig != "overbought":
            all_overbought = False
    if not all_overbought:
        return None
    return {
        "insight": f"all {len(crypto)} tracked crypto overbought (RSI≥70)",
        "severity": "medium",
        "evidence": {"perAsset": per_asset},
        "sources": ["market_indicators"],
    }


def _insight_framework_vs_execution() -> dict[str, Any] | None:
    """Cross-domain JOIN: the vault has an investment/strategy framework note AND a target
    channel (etf/vn) sits ~0% deployed → a written framework not yet reflected in positions.
    Fires ONLY if BOTH halves are real (a real note AND a real under-deployed target) — the
    JOIN is the insight; never fabricate either half. NEUTRAL observation of the gap."""
    hits = _wiki_search("investment framework strategy", limit=10)
    note = next((h for h in hits if any(
        kw in str(h.get("title", "")).lower()
        for kw in ("framework", "invest", "strategy", "allocation", "portfolio")
    )), None)
    if note is None:
        return None  # no real framework note → no JOIN
    ov, _ = _fin_overview()
    # a target channel (etf/vn) with a real target but ~0% deployed
    for a in ov.allocations:
        if a.channel in ("etf", "vn") and a.target > 0 and a.pct <= _FRAMEWORK_DEPLOYED_PCT:
            return {
                "insight": f"framework note #{note['id']} '{note['title']}' on record, "
                           f"but finance shows {a.pct:.0f}% deployed to {a.channel} "
                           f"(target {a.target:.0f}%)",
                "severity": "medium",
                "evidence": {"noteId": note["id"], "noteTitle": note["title"],
                             "channel": a.channel, "deployedPct": a.pct, "targetPct": a.target},
                "sources": ["wiki_search", "finance_overview"],
            }
    return None  # framework note exists but no under-deployed target → no gap to observe


def _insight_stalled_projects() -> dict[str, Any] | None:
    """Fires per project idle > 30 days (health stall/dead). NEUTRAL observation of which
    projects haven't moved; no 'revive or kill' advice. Returns the single most-stalled
    (one low-severity insight; evidence carries the count)."""
    statuses, _ = _proj_list()
    stalled: list[dict[str, Any]] = [
        {"projectId": s.id, "name": s.name, "idleDays": int(s.lastDays or 0)}
        for s in statuses
        if s.health in ("stall", "dead") and (s.lastDays or 0) >= _STALLED_PROJECT_DAYS
    ]
    if not stalled:
        return None
    stalled.sort(key=lambda p: -int(p["idleDays"]))  # idleDays is int (set via int() above)
    top = stalled[0]
    return {
        "insight": f"project '{top['name']}' idle {top['idleDays']}d"
                   + (f" (+{len(stalled) - 1} more stalled ≥{_STALLED_PROJECT_DAYS}d)"
                      if len(stalled) > 1 else ""),
        "severity": "low",
        "evidence": {"projectId": top["projectId"], "idleDays": top["idleDays"],
                     "stalledCount": len(stalled), "stalled": stalled},
        "sources": ["projects_list"],
    }


_INSIGHT_RULES: list[Callable[[], dict[str, Any] | None]] = [
    _insight_undeployed_capital,
    _insight_all_crypto_overbought,
    _insight_framework_vs_execution,
    _insight_stalled_projects,
]


def insights() -> dict[str, Any]:
    """Cross-domain INSIGHTS: neutral, evidence-grounded OBSERVATIONS connecting finance /
    market / wiki / projects that no single-module read surfaces (e.g. 'framework written but
    a target channel still ~0% deployed'). Each insight: ``{insight: str, severity:
    high|medium|low, evidence: {real numbers it derived from}, sources: [tool names]}``.

    The agent reads these as grounded starting points and does its OWN reasoning — they are
    NEUTRAL composition/evidence statements, NOT advice (no should/buy/sell/rebalance/move/
    consider/recommend verb). Severity-ranked high→low. Each rule is fail-soft (a down/empty
    source → that rule simply doesn't fire, never breaks the others; an erroring rule is
    tagged in ``sources`` as an error and skipped).

    Rules run over REAL data ONLY — the Fear&Greed rule was DROPPED because F&G is a stub
    mock (citing it would fabricate evidence, the opposite of this tool's spine).

    Honest-empty: nothing fires → ``{insights: [], note: "...", asOf, sources: []}`` (NOT a
    fabricated insight). READ-ONLY: observes the live read paths, writes nothing.
    ``{insights, asOf, sources, note?}``."""
    found: list[dict[str, Any]] = []
    sources_touched: set[str] = set()
    for rule in _INSIGHT_RULES:
        try:
            ins = rule()
            if ins is not None:
                found.append(ins)
                sources_touched.update(ins.get("sources", []))
        except Exception as exc:  # noqa: BLE001 — one bad rule must not break the composer
            sources_touched.add(f"{rule.__name__}:error:{type(exc).__name__}")
    found.sort(key=lambda i: _SEVERITY_RANK.get(i.get("severity", "low"), 9))
    out: dict[str, Any] = {
        "insights": _jsonable(found),
        "asOf": _insights_now(),
        "sources": sorted(sources_touched),
    }
    if not found:
        out["note"] = "nothing notable across modules right now"
    return out


# Registry of (name → logic fn) — the single source of truth for what tools exist.
# Tests iterate this for callability + parity; FastMCP registration iterates it below.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "finance_overview": finance_overview,
    "finance_channel": finance_channel,
    # NB-FINANCE-MCP: pure-compute analytics (read-only — no portfolio mutation)
    "finance_simulate": finance_simulate,
    # FINANCE-MCP-SHAPE (#50): rebalance + risk/HHI + returns over the live overview (READ)
    "finance_analytics": finance_analytics,
    # FINANCE-ASSISTANT P2 (#54): the decision tower — RL state + W=∏q (NEUTRAL read/compute)
    "macro_cycle": macro_cycle,
    "decision_weight": decision_weight,
    # FINANCE-ASSISTANT P3 (#55): policy (reference weighting) + proactive scan (NEUTRAL)
    "allocation_target": allocation_target,
    "finance_guardian": finance_guardian,
    # FINANCE-ASSISTANT P4 (#56): the daily NAV-series reader (total-value history + confidence)
    "nav_history": nav_history,
    "market_overview": market_overview,
    "market_history": market_history,
    "market_indicators": market_indicators,
    "market_ohlc": market_ohlc,
    "market_watchlist": market_watchlist,
    "market_summary": market_summary,
    "market_correlation": market_correlation,
    "market_relative_strength": market_relative_strength,
    "projects_list": projects_list,
    "project_get": project_get,
    "graveyard_overview": graveyard_overview,
    "claude_usage": claude_usage,
    "reminders_list": reminders_list,  # REMINDERS-2 #28: agenda on lifeos-read (read-only)
    "daily_brief": daily_brief,
    "brief_history": brief_history,
    "journal_entries": journal_entries,
    "decision_entries": decision_entries,
    "activity_feed": activity_feed,
    "activity_run": activity_run,
    "exchange_overview": exchange_overview,
    "app_settings": app_settings,
    "reliability_report": reliability_report,
    "macro_overview": macro_overview,
    "macro_history": macro_history,
    "news_digest": news_digest,
    "news_list": news_list,
    # MCP-DEDUP #70: wiki tools removed — canonical = standalone modules/wiki/mcp
    # (mounted at /mcp/wiki-read). The 4 read dupes live there; wiki_proposal_status +
    # wiki_list_proposals were PORTED there. Zero wiki capability lost.
    "life_brief": life_brief,
    # INSIGHTS (D1): cross-domain neutral observations over the live read paths
    "insights": insights,
    "check_proposal_status": check_proposal_status,
    "list_my_proposals": list_my_proposals,
    "proposal_stats": proposal_stats,
    "list_tools_catalog": list_tools_catalog,
}


# --------------------------------------------------------------------------- #
# FastMCP server — registers each TOOLS entry as an MCP tool over stdio. Built   #
# lazily in build_server() so importing this module (for tests / the no-write    #
# capability check) does NOT require the SDK to spin up a server.                #
# --------------------------------------------------------------------------- #
def build_server(transport_security: Any = None, stateless_http: bool = False) -> Any:
    """Construct the FastMCP server with all read tools registered. Separated from
    import so tests can import TOOLS without constructing the server. FastMCP infers
    each tool's schema from the fn signature + docstring.

    ``transport_security`` (default None = stdio-identical) is passed through to FastMCP
    so main.py can mount this over streamable-http with DNS-rebinding protection OFF for
    remote/LAN clients (MCP-HTTP). None keeps the stdio entrypoint behaviourally unchanged.

    ``stateless_http`` (default False = stdio-identical) → MCP-STATELESS (#75): True = no
    per-session state, so a backend RESTART does NOT drop HTTP clients (no mcp-session-id to
    re-initialize — agent-first). Read tools are pure request/response (no server-push/
    subscribe), so stateless loses nothing. main.py passes True for the HTTP mount."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-read", transport_security=transport_security,
                  stateless_http=stateless_http)
    for fn in TOOLS.values():
        mcp.add_tool(fn, description=fn.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
