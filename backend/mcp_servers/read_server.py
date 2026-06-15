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
  - market:           get_market, history, compute_indicators, tracked_assets
                      (READ paths only — NOT poll_once / add_rule / delete_rule;
                      compute_indicators is the GET /market/indicators TA read path
                      dev shipped — WRAPPED, never edited; this file does NOT touch
                      market/service.py or market/ta.py, which dev owns)
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

from typing import Any, Callable

# READ-ONLY imports only (the capability gate — see module docstring + the no-write
# test). Each is aliased with a leading underscore: these are private read wrappers,
# and the alias keeps the bound names unambiguous for the namespace-scan test.
from modules.finance.service import get_overview as _fin_overview
from modules.finance.service import get_channel as _fin_channel
from modules.market.service import get_market as _mkt_market
from modules.market.service import history as _mkt_history
# TA read path shipped by dev (GET /market/indicators) — wrapped, NOT edited. Returns
# NEUTRAL technical data (no advice) + warnings. tracked_assets is the read-only
# config list of symbols (no asset-mgmt mutation).
from modules.market.service import compute_indicators as _mkt_indicators
from modules.market.service import tracked_assets as _mkt_tracked
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


def claude_usage(window: str = "5h") -> dict[str, Any]:
    """Claude token-usage view: per-day burn series, by-model / by-project split,
    today's total, quota %, cost. ``{usage}``. Fail-open to manual/stub if no local
    stats. ``window`` accepted for the API contract."""
    return {"usage": _jsonable(_claude_usage(window=window))}


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
        "pnlTotal": _jsonable(ov.pnlTotal),
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
    + calibration counts. From modules/decision_journal (list_entries). No advice."""
    stats, warnings = _decision_list(status="open")
    return {
        "openCount": len(stats.entries),
        "open": [{"id": e.id, "decision": e.decision, "domain": e.domain,
                  "date": e.date, "confidence": getattr(e, "confidence", None)}
                 for e in stats.entries],
        "warnings": list(warnings or []),
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
        }
    }


# Registry of (name → logic fn) — the single source of truth for what tools exist.
# Tests iterate this for callability + parity; FastMCP registration iterates it below.
TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "finance_overview": finance_overview,
    "finance_channel": finance_channel,
    "market_overview": market_overview,
    "market_history": market_history,
    "market_indicators": market_indicators,
    "projects_list": projects_list,
    "project_get": project_get,
    "graveyard_overview": graveyard_overview,
    "claude_usage": claude_usage,
    "daily_brief": daily_brief,
    "brief_history": brief_history,
    "journal_entries": journal_entries,
    "decision_entries": decision_entries,
    "activity_feed": activity_feed,
    "activity_run": activity_run,
    "exchange_overview": exchange_overview,
    "app_settings": app_settings,
    "reliability_report": reliability_report,
    "life_brief": life_brief,
}


# --------------------------------------------------------------------------- #
# FastMCP server — registers each TOOLS entry as an MCP tool over stdio. Built   #
# lazily in build_server() so importing this module (for tests / the no-write    #
# capability check) does NOT require the SDK to spin up a server.                #
# --------------------------------------------------------------------------- #
def build_server() -> Any:
    """Construct the FastMCP server with all read tools registered. Separated from
    import so tests can import TOOLS without constructing the server. FastMCP infers
    each tool's schema from the fn signature + docstring."""
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("life-os-read")
    for fn in TOOLS.values():
        mcp.add_tool(fn, description=fn.__doc__)
    return mcp


def main() -> None:
    """stdio entrypoint — Claude Code launches this via its mcp config."""
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
