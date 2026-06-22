# Parked backlog (architect-tracked) — surface to team-lead when a relevant lane opens

> Low-priority, non-blocking items found during #142/#143. NOT dispatched (don't expand the current sprint). Surface to team-lead for prioritization when a tester/dogfood/parity lane opens.

## P-1 — reminders-test-isolation flake (tester-owned, LOW)
- **What:** a #31 Reminders vitest test fails ~1/6 full-suite runs, non-reproducing (isolation/timing). 2nd sighting of a reminders-suite isolation flake.
- **Class:** same as the #141 settings flake (a once-Once mock / spy-isolation timing leak — a `mockResolvedValueOnce` consumed by StrictMode double-invoke, or an afterEach reset gap).
- **Found:** #143 /tracing (FE saw it on a CSS-only change → definitely not caused by the change).
- **Fix direction:** audit the reminders test's mock setup (mockResolvedValueOnce → mockResolvedValue, or per-test reset) like #141 settings.test:33. tester-owned.
- **Why parked:** flaky 1/6, not a product bug; doesn't block any feature. team-lead noted "low-pri follow-up after, not blocking."

## P-6 — sync.test.tsx "renders open conflicts" intermittent flake (tester, LOW)
- **What:** `app/wiki/sync/__tests__/sync.test.tsx > renders open conflicts` failed 1/30 full-suite runs during B-T1 (did NOT reproduce in the other 29 + my run). A SEPARATE test from the B-T1 settings flake.
- **Class:** likely another isolation/timing flake (possibly the same StrictMode-re-render or an async-settle class as #141/B-T1-settings).
- **Found:** #B-T1 (tester, while verifying the settings fix — flagged-not-fixed, out of B-T1 scope).
- **Fix direction:** reproduce (run sync.test 30×), apply the same determinism discipline (act-flush before interaction / robust async settle) if it's the StrictMode class. tester-owned.
- **Why parked:** out of B-T1 scope (B-T1 = the settings flake); low-rate; not blocking. A future test-hardening micro-task.

## P-2 — MCP/REST wiki_overview parity bug (dogfood/parity lane, MEDIUM)
- **What:** `mcp wiki_overview` returns totalNotes **80** / fleeting **63**; REST `GET /wiki/overview` returns totalNotes **50** / fleeting **34** for the same vault. They DISAGREE.
- **Root cause:** MCP counts soft-deleted notes; REST excludes them (active-only). The agent-surface (MCP) and the human-surface (REST/FE) report different totals → an AGENT-FIRST honesty/parity violation (an agent reading MCP gets inflated counts).
- **Found:** #143 /wiki W2 trace (the 63-vs-34 confusion traced back to this; team-lead pulled both surfaces).
- **Fix direction:** align MCP wiki_overview to REST's active-only semantics (or document the difference explicitly in the MCP output — e.g. separate `total` vs `activeTotal` fields so an agent isn't misled). Backend-owned; fits a dogfood/parity round.
- **Why parked:** not blocking #143 (the FE label fix handles the UI clarity); it's a separate backend parity concern for a dogfood lane.

## P-3 — wiki inbox "fleeting" scope exceeds the vault's fleeting partition (backend, MEDIUM)
- **What:** REST `/wiki/overview` returns `inbox.length = 63` (all status:"fleeting") but `stats.byStatus.fleeting = 34` and `totalNotes = 50`. So the inbox's fleeting count (63) > the whole-vault fleeting partition (34) > totalNotes (50) — the two "fleeting" scopes don't reconcile.
- **Why it matters (agent-first):** a consumer-agent reading the API sees two irreconcilable "fleeting" numbers (inbox 63 vs stats 34) with no field explaining the scope difference. The FE now labels them distinctly (inbox = "cần refine"), so the UI isn't misleading — but the API itself is ambiguous to an agent.
- **Root cause (hypothesis):** the inbox likely counts pre-vault captures / a broader source set than the byStatus partition (which is active vault notes). Needs a backend look.
- **Found:** #143 /wiki W2 trace (FE flagged, architect confirmed via REST).
- **Fix direction:** either reconcile the two scopes, or add an explicit semantic to the inbox count (e.g. an `includesPreVaultCaptures` flag / a `scope` field) so an agent can interpret it. Backend-owned, dogfood/parity lane.
- **Why parked:** UI is honest post-#143; the API-level scope clarity is a separate backend concern.

## P-4 — finance load-order: headline KPIs render slowest (FE-fetch-sequencing, LOW, perf-gated)
- **What:** on /finance, the 3 headline KPI tiles (TỔNG TÀI SẢN / DRY POWDER / P&L MỞ) show skeleton dots for ~2s while the secondary equity-curve ($10,626) + allocation bars render FIRST → the most important numbers load last. RESOLVES correctly (verified post-settle: $10,624, 0 skeletons, console clean) — NOT a stuck-state bug.
- **Root cause:** the known finance no-cache fetch latency (see memory `finance-perf-no-cache` — get_quote fetches fresh per coin, no memo/TTL). The KPIs depend on the slow finance fetch; the equity-curve/allocation come from a faster path.
- **Found:** #143 /finance audit (architect + team-lead both caught the mid-load skeleton live; both verified it resolves).
- **Fix direction:** primarily BACKEND (memoize/batch/TTL the finance quotes — the existing finance-perf area). SECONDARY FE option (only IF/when backend perf is addressed): re-sequence so the headline KPIs fetch first, or surface the equity-curve total as the headline sooner. Low value until the backend latency is fixed.
- **Why parked:** not an FE-polish bug; #143 skipped /finance (mature). Tie to the finance-perf backend work.

## P-5 — /projects: progress/next/desc/users derivations return null (backend feature gap, MEDIUM)
- **What:** `GET /projects` returns `progress: null`, `next: null`, `desc: null` for **0/14** projects (all null). Populated: health, last, lastDays, metrics, repo (14/14), AND `users: 0` (14/14 — present, value 0 = zero external users, CORRECT for personal projects; NOT a null gap — corrected per team-lead's REST re-check). So the /projects list renders "—" for 3 spec'd derivation columns (TIẾN ĐỘ/progress, next-action, description).
- **Why it matters:** the original Projects spec called for these as DERIVED metrics (progress% from commits/milestones, next-action, etc.). They're unimplemented → the screen shows 4 honest-but-empty columns. The FE correctly honest-mirrors the nulls (not an FE bug).
- **Found:** #143 /projects audit (architect REST source-check, W2 lesson).
- **🔴 REFRAMED (2026-06-23, architect read the reader before specing):** this is NOT a missing derivation — it's a LOCKED DESIGN. reader.py:11-12 "progress/next/users: from status.md front-matter… **NEVER fabricated from git**." The fields come from each project's user-authored `status.md` YAML; the reader deliberately refuses to guess them from commits (raw-data-first / honest-mirror). The nulls = the repos' status.md don't have these fields filled → honestly null. The FE "—" is CORRECT.
- **Decision (surfaced to team-lead):** (1) close as by-design [recommended — the honest null is correct], (2) an FE flow to let the user enter progress/next/desc into status.md [honest path if the user wants them populated], or (3) override the locked "never fabricate from git" with a git-derived progress [needs explicit USER sign-off — architect argues against, it's the guessed-data the architecture avoids].
- **Status (RESOLVED 2026-06-23):** CLOSED as by-design (Option 1, team-lead verified on disk). The honest null is correct (never-fabricate-from-git, same discipline as finance F2 / wiki honest labels). Option (3) git-derive = REJECTED (anti-honest-mirror, needs user sign-off). Option (2) — an optional FE flow to let the user enter progress/next/desc into status.md from /projects — is a legit NET-NEW FE feature (not a backend task); team-lead is surfacing it to the user as an optional future enhancement (don't auto-build; user greenlight required).
