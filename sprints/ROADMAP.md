# Life OS — Project Roadmap & Overview

> The whole-project picture for direction approval, BEFORE any sprint kickoff.
> Sources: `life-os-SPEC-FULL.md` (14 screens S1–S14), `life-os-ARCHITECTURE.md` (§3 tree, §9 implement order), mock `template/Life Command/`.
> Author: architect · 2026-06-06 · Status: **awaiting user direction approval**

---

## 1. What we're building (one paragraph)

A **single-user, no-auth personal life-OS**: one dashboard tracking projects (alive/dead/build-to-90), finance & investing (portfolio, ladder, allocation drift), Claude Code usage, notes & investment journal — that **runs itself** via rule-based routines and **opens an API** so external Claude Code can later plug in as the "brain". The app is the source of truth; AI is external and replaceable. **14 screens, 8 backend modules, ~20 sprints.** Built module-by-module so each ships independently and "adding a feature = adding a folder".

### Sprint 0 = the FOUNDATION (two layers, both must be clear before we build)

The user's framing: **"Sprint 0 scaffold = lay the FOUNDATION, the place from which you see the whole system."** Sprint 0 is NOT just "an empty skeleton that runs". It is the foundation, and a foundation has two layers — both delivered before any module is built:

- **Layer A — the whole-system vision** (this document): structure + module↔screen↔sprint map + roadmap + workflow. Read it once and you understand how the entire system takes shape. *Vision = you can see where every later sprint plugs in.*
- **Layer B — the cross-cutting contracts laid in CODE at Sprint 0** (§6): BaseModule, registry auto-discover, common ProjectStatus shape, response format, store contract, design tokens. *These are the actual load-bearing concrete.* Sprints 1–8 then just **plug a module into this foundation without ever editing core** (§6.1 shows the relationship).

If the foundation is right, every later sprint is cheap and additive. If it's wrong, the cost compounds across all 14 screens — which is why Sprint 0 (and Sprint 1, which locks the status shape) are **Tier-S**.

---

## 2. Final project structure (what we'll actually build → ARCH §3)

```
life-os/
├── backend/                      # FastAPI — the heart (every screen + AI reads here)
│   ├── core/                     # ⭐ Sprint 0 — the contract everything plugs into
│   │   ├── base.py               #   BaseModule {name, router, routines()}
│   │   ├── registry.py           #   auto-discover modules/ → mount routers + register routines
│   │   ├── config.py             #   DATA_DIR, DB_PATH, repo pointers
│   │   └── scheduler.py          #   APScheduler engine (cron + event)
│   ├── modules/                  # ⭐ each feature = 1 self-contained folder
│   │   ├── projects/             #   router · schema · service · reader (git)     → S2/S3
│   │   ├── market/               #   + reader (price feeds)                       → S8
│   │   ├── finance/              #   + ladder/allocation logic                    → S5/S6
│   │   ├── claude_usage/         #   + reader (local Claude stats)                → S9
│   │   ├── notes/                #   markdown CRUD                                → S10
│   │   ├── journal/              #   + calibration                               → S7
│   │   ├── automation/           #   routines.py + run_log                        → S13
│   │   ├── activity/             #   run-log feed                                 → S14
│   │   ├── graveyard/            #   abandoned-project view (from projects data)  → S4
│   │   └── brief/                #   template-based morning brief                 → S1/S11
│   ├── store/
│   │   ├── md_store.py           # ⭐ Sprint 0 — read/write markdown + git commit per write
│   │   └── db.py                 # ⭐ Sprint 0 — SQLite (price_history, run_log, usage_history)
│   ├── data/                     # DATA_DIR — real markdown, git-versioned
│   │   ├── projects/<id>/        #   status.md · wiki.md · notes.md
│   │   ├── notes/  └── journal/
│   ├── main.py                   # ⭐ Sprint 0 — registry.mount_all(app)
│   └── pyproject.toml
│
├── frontend/                     # Next.js (App Router) — 14 routes
│   ├── app/                      # routes = screens (page.tsx S1 + 13 route folders)
│   ├── components/               # ⭐ Sprint 0 SHELL: Sidebar·TopBar·CommandBar·TickerTape
│   │   └── shared: HealthChip·ProgressBar·KpiCard·DataTable·AlertRow·RingGauge·Sparkline
│   ├── features/                 # each matches a BE module (projects/finance/market/...)
│   ├── lib/
│   │   ├── api.ts                # ⭐ Sprint 0 — backend client
│   │   ├── types.ts              # ⭐ Sprint 0 — types mirror BE schema (ProjectStatus...)
│   │   └── tokens.css            # ⭐ Sprint 0 — design tokens ported from mock app.css
│   └── package.json
│
└── template/Life Command/        # MOCK design baseline (immutable reference)
```

⭐ = built in **Sprint 0**, the foundation every later sprint depends on.

---

## 3. Module ↔ Screen ↔ Sprint map

The whole app on one table — 8 modules + shell serving 14 screens across ~20 sprints.

| BE module | Serves screen(s) | Lands in sprint | Reader / special logic |
|---|---|---|---|
| *(core + shell — no module)* | shell on all S1–S14 | **S0** | registry, store, scheduler, tokens |
| `projects` | S2 list · S3 detail | **S1–S2** | git reader → health/progress/next |
| `market` | S8 market · ticker (all screens) | **S3–S4** | price readers per asset class |
| `finance` | S5 overview · S6 portfolio | **S5–S6** | ladder state, allocation drift |
| `claude_usage` | S9 usage | **S7** | local Claude stats reader + manual fallback |
| `notes` | S10 notes | **S8** | markdown CRUD |
| `journal` | S7 journal | **S9** | calibration scoring |
| `automation` | S13 routines | **S10** | 6 rule-based routines + run_log |
| `activity` | S14 feed · Home widget | **S10** | run-log feed |
| `graveyard` | S4 graveyard | **S11** | derived from projects data |
| `brief` | S11 brief · S1 Home brief | **S12** | template + real data, no AI |
| *(integration)* | S1 Home full · S12 Settings | **S13** | wire all KPIs/registry |

> Screen ≠ sprint 1:1 — heavy screens (Projects, Finance) span 2 sprints (BE+reader, then FE+detail). Sprint numbers above are the **proposed roadmap in §4**, finalized at each kickoff.

---

## 4. Full sprint roadmap (~20 sprints, follows ARCH §9 implement order)

Each sprint ships something runnable on its own. **Tier-S = the hardest/most load-bearing foundation work** — get these right or every later sprint inherits the bug.

| Sprint | Goal | Ships | Module/Screen | Tier |
|---|---|---|---|---|
| **0** | Core + Shell | Frame runs, navigate empty; registry+store+scheduler boot | core, store, shell, tokens, 14 empty routes | **🔴 Tier-S** |
| **1** | Projects BE | `GET /projects` + git reader → common status shape | `projects` module | **🔴 Tier-S** (locks status shape) |
| **2** | Projects FE | S2 list (NEXT column) + S3 detail — first full BE→API→FE slice | S2, S3 | — |
| **3** | Market BE | price readers (crypto real, ETF/VN mock-first) + `GET /market` | `market` module | 🟠 |
| **4** | Market FE + Ticker | S8 screen + live ticker tape across shell | S8, ticker | — |
| **5** | Finance BE | portfolio, P&L, allocation, **ladder logic** (decide-and-log) | `finance` module | 🟠 (business rules) |
| **6** | Finance FE | S5 overview + S6 portfolio detail (ladder state UI) | S5, S6 | — |
| **7** | Claude Usage | reader (verify local source) + manual fallback + S9 ring/history | `claude_usage`, S9 | 🟠 (source unverified) |
| **8** | Notes | markdown CRUD + S10 + attach-to-project | `notes`, S10 | — |
| **9** | Journal | form + calibration scoring + S7 | `journal`, S7 | — |
| **10** | Automation + Activity | scheduler routines (poll/idle/pattern-check/nudge) + run log + S13/S14 | `automation`, `activity`, S13, S14 | 🟠 (app goes "active") |
| **11** | Graveyard | S4 from projects data + pattern stats (build-to-90) | `graveyard`, S4 | — |
| **12** | Brief | template morning brief + S11 + Home brief widget | `brief`, S11 | — |
| **13** | Home + Settings | wire S1 full (KPIs, alerts) + S12 registry (add project/asset no-code) | S1, S12 | — |
| **14+** | Polish / hardening | cross-screen consistency, command-bar grammar, alert channels, edge cases | all | — |
| **later** | MCP + AI brief | FastMCP wrapper, external Claude Code brief, GCP 24/7 scheduler | — | (out of this build) |

> ~14 numbered sprints + reactive (A/B) sprints as bugs/gaps appear → ~18–20 total. Roadmap is a draft; team-lead is priority gatekeeper, each sprint re-confirmed at kickoff.

---

## 5. How one sprint runs (workflow under Mode B)

```
team-lead assigns sprint
   ↓
architect KICKOFF (re-read spec/arch/code + last end-reports) → write dispatch contracts
   ↓
backend + frontend implement IN PARALLEL  (architect specs all non-CRUD logic up front — implementer never invents it)
   ↓
tester verifies  ║  architect reviews code        ← run in parallel
  • Rule #0: trust NO claim — re-run tests, curl endpoints, read files on disk
  • architect reads FULL functions (not just diff), traces runtime entry→exit
   ↓
3 Quality Gates green (API / Function / Sprint)
   ↓
architect commits (code + plan + end report, one commit) → sleep 120 && git push (user can say "no/wait/hold")
   ↓
Sprint Sync: Standup (bottom-up friction) → Retro (top-down root-cause) → learnings to memory/playbook
   ↓
team-lead auto-starts next sprint (Mode B: continuous, pings but doesn't block)
```

**Mode B = full-auto:** the team decides-and-logs instead of asking; surfaces decisions to the user async (Discord + end-report `## Assumptions`); only a true blocker or a <100%-pass stops the loop.

---

## 6. Cross-cutting contracts built in Sprint 0 — the "concrete" of the foundation (Layer B)

These six are the load-bearing foundation built in code at Sprint 0. Every later sprint **bolts onto** them; if any is wrong, the cost compounds across all 14 screens. This is why Sprint 0 and Sprint 1 are Tier-S.

| # | Contract | What it locks | File | Built |
|---|---|---|---|---|
| C1 | **BaseModule** `{name, router, routines()}` | the shape every feature implements to plug into core | `core/base.py` | S0 |
| C2 | **Registry auto-discovery** | "add a folder = add a module" — no edits to core/main.py ever | `core/registry.py` | S0 |
| C3 | **Common ProjectStatus shape** `{id,name,desc,health,progress,users,last,lastDays,next,repo,metrics{commits,stars,lang,test_pass},routines[],lastAuto}` | every reader returns ONE shape → core+FE+AI handle uniformly | `lib/types.ts` (S0) → `modules/projects/schema.py` (S1) | S0/S1 |
| C4 | **API response format** `{success: bool, data: ..., warning?: str}` + REST error codes (400/404/422/429/500, **no auth codes**) | every endpoint answers the same way → predictable client + AI | helper in `core/` (proven on `/health`) | S0 |
| C5 | **Store contract** — `md_store` (1 git-commit per write, AI reads markdown directly) + `db.py` (SQLite for time-series: price_history, run_log, usage_history) | one place metadata/notes live (md+git), one place time-series lives (SQLite) — modules never invent their own persistence | `store/md_store.py`, `store/db.py` | S0 |
| C6 | **Design tokens** (copper theme, fonts, component classes, spark/gauge helpers) | ported verbatim from mock — no redesign, visual consistency from screen 1 | `lib/tokens.css`, `lib/spark.ts` | S0 |

### 6.1 Foundation ↔ later layers — how Sprints 1–8 plug in WITHOUT touching core

This is the relationship the foundation buys us. Sprint 0 lays C1–C6 once; every later sprint is then purely additive:

```
        ┌─────────────────────── Sprint 0 FOUNDATION (built once, never re-edited) ───────────────────────┐
        │  C1 BaseModule   C2 registry   C3 status shape   C4 response fmt   C5 store   C6 design tokens    │
        └───────────▲──────────────▲──────────────▲──────────────▲─────────────▲──────────────▲───────────┘
                    │              │              │              │             │              │
  S1 projects ──────┘ implements   │ discovered   │ returns      │ answers     │ persists     │ (BE)
  S3 market   ──────┘ BaseModule   │ automatically│ status shape │ {success..} │ via store    │
  S5 finance  ──────┘ (router+     │ (drop folder │ (C3)         │ (C4)        │ (C5)         │
  ...         ──────┘  schema+      │  → endpoint  │              │             │              │
                       service+     │  live)       │              │             │              │
                       reader)      │              │              │             │              │
  S2 projects-FE ─────────────────────────────────────────────────────────────────┘ renders with C6 tokens
  S4/S6/... FE   ─────────────────────────────────────────────────────────────────┘ + shared shell
```

**The promise made concrete:** to add the `finance` module in Sprint 5, backend creates `modules/finance/` with `router.py·schema.py·service.py·reader.py` implementing **C1**, returning **C3/C4** shapes, persisting via **C5** — and the **C2** registry mounts it on next boot. **Zero edits to `core/` or `main.py`.** Frontend adds `features/finance/` + a route that renders with **C6** tokens inside the **S0** shell. That additive-only property is the entire payoff of getting Sprint 0 right.

| Later sprint | What it ADDS | What it does NOT touch |
|---|---|---|
| S1–S11 (each module) | a `modules/<name>/` folder (C1) + a `features/<name>/` + a route | `core/*`, `main.py`, `store/*` API, `tokens.css`, response-format helper |
| S0 (this sprint) | **all of core/store/shell/tokens** — the foundation itself | (nothing exists before it) |

---

## 7. What we are NOT building this version (ARCH §11 boundary)

❌ Embedded chat AI / LLM calls in-app · ❌ MCP wrapper (later) · ❌ AI-generated routines or briefs (template-based now) · ❌ auth / multi-user / billing / RBAC · ❌ Redis/queue/microservices/k8s. Single user, single machine, simplest thing that works.

---

## 8. Decision points the user will see along the way (decide-and-log)

The team decides these autonomously and logs them for async review — listing here so the user knows what's coming:
- **S3/S4 Market:** which price source per asset class (crypto = free API; ETF/VN = mock-first until a source is chosen).
- **S5 Finance:** ladder rung levels + target allocation (golden-path file absent → architect decides a baseline; user can override later).
- **S7 Claude Usage:** exact local token source (verify on this machine) + manual-entry fallback.
- **S10 Automation:** routine thresholds (idle N days, pattern-check ≥90% & 0 users).

---

➡️ **Approve this direction** (structure + module/screen/sprint allocation + workflow) and I'll proceed to the detailed **Sprint 0 kickoff + dispatch**. The `plan_sprint_0.md` is already drafted and waiting behind this approval.
