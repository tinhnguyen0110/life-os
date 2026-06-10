# Life OS — Personal AI Operating System

> An all-in-one life-tracing OS — projects, finance, Claude-Code usage, notes, and rule-based automation in one command center.
> **Built solo in ~11 hours across 15 sprints** by orchestrating a 5-role AI dev team under a self-authored process.

🔗 **Live demo:** [demo.tinhdev.com/life-command](https://demo.tinhdev.com/life-command/life-command.html) · **Portfolio:** [tinhdev.com](https://tinhdev.com)

---

## What it is

Life OS is a single-user "mission control" that answers, at a glance: *where is each project, what's the goal, who's using it, what's next* — alongside a live finance/portfolio view, Claude-Code quota tracking, notes, and an automation layer that runs rule-based routines (price polling, idle-project alerts, a build-to-90%-pattern check).

It is also a **demonstration of process**: the whole system was built by a team of AI agents (architect · backend · frontend · tester) coordinated by a documented operating model, with 3 blocking quality gates before every commit.

## By the numbers

| | |
|---|---|
| Build time | ~11 hours · 15 sprints (one commit per sprint) |
| Production code | ~15k LOC |
| Tests | **~1,089** (685 pytest · ~400 vitest) |
| Backend modules | 12 (auto-discovered) |
| Frontend screens | 14 |
| Live bugs after ship | 0 (all caught by pre-commit gates) |

## Architecture

**Stack:** FastAPI (backend) · Next.js (frontend) · Markdown-on-git + SQLite (storage) · APScheduler (automation) · Docker Compose.

**Module/registry pattern — the core "easy-to-extend" contract:**
Each feature is an independent folder under `backend/modules/<name>/` exposing `router · schema · service · (reader)`. A registry auto-discovers every module at startup and mounts it.

> **Adding a feature = adding a folder.** `core/registry.py` and `main.py` are never edited to wire a new module.

```
backend/
  core/        # registry (auto-discovery), base contract, config, scheduler
  modules/     # 12 features: projects, finance, market, claude_usage,
               #   notes, journal, automation, activity, brief, graveyard,
               #   exchange, settings  — each self-contained
  store/       # md_store (git-per-write) + SQLite (time-series)
frontend/
  app/         # 14 screens (App Router)
  components/  # shared: DataTable, KpiCard, HealthChip, ProgressBar, …
  lib/         # api client + design tokens
```

- **Source of truth = the API.** The dashboard is one client; an external AI (Claude Code via MCP) can be a second. Raw-data-first: the API returns real data, derived metrics are computed server-side.
- **Markdown + git storage** gives human-readable state and free version history (every write is a commit).
- **Automation layer:** rule-based routines (no embedded LLM) — `market-poll`, `idle-hunter`, `pattern-check` (flags projects stuck at ~90% with 0 users), `journal-nudge`, `wiki-refresh`, `morning-pull`.

## The AI dev-team process *(what makes this notable)*

Life OS was built by AI agents under a reusable, documented process (`CLAUDE.md` + role playbooks in `.claude/agents/` + an operating model):

- **Roles:** team-lead + architect + backend + frontend + tester
- **3 blocking quality gates** (API / function / sprint) before any commit
- **Decide-and-log autonomy:** agents decide algorithms and record assumptions, instead of blocking on the human
- **Independent verification (Rule #0):** no teammate claim is trusted without real evidence
- **Self-improving:** every recurring failure becomes a permanent rule

## Run it locally

```bash
docker compose up -d         # backend :8686 · frontend :3010
# both services hot-reload from host bind-mounts
```

Or run each service directly (FastAPI + Next.js) — see `docker-compose.yml`.

## Status

Personal project, actively used as a daily command center. Single-user by design — no auth, no multi-tenant, no billing. AI is intentionally *external* (connect Claude Code via API/MCP) rather than embedded.

---

*Built by [Nguyen Van Tinh](https://tinhdev.com) — AI Automation Engineer / Solution Architect.*
