# Plan Sprint 9 — Investment Journal (S7) [write module · md_store · calibration]

> Author: architect · 2026-06-06 · Status: kickoff DONE · awaiting team-lead mock-diff + greenlight.
> Spec: SPEC §S7 (Investment Journal — calibration). Mock: `template/Life Command/app/screens-finance.js` `SCREENS.journal` + `DB.journal` (`data.js:116`) — HAS a mock → PORT. ARCH §6 (md_store write, like Notes) / §7 (`GET /journal` · `POST /journal`) / §9 (Journal "dùng finance/market" — calibration references positions/price).
> Memory: `schema-freeze-gate`, `unhandled-errors-not-green`, `mock-diff-catches-dropped-feature`, `dev-server-ports`, `test-where-the-reader-greps`, `host-file-source-must-mount` (container-up), `single-dev-no-overengineering`. **Closest precedent: the Notes module (md_store write + git-per-write).**

## Objective
Replace the Journal EmptyScreen with the real S7 "Nhật ký lệnh" — turn investment DECISIONS into learning data (calibration). A WRITE module via md_store (1 git commit per entry, like Notes). Closes the finance→journal loop (S6's `/journal` nav button). Full feature per SPEC §S7 (thesis/confidence/calibration), simplest impl (north-star). Turns a Home stub → live (if Home has a journal tile; verify at kickoff — Home currently has Brief/Activity stubs, journal may not be a Home tile).

## Data source + edges (named upfront — backend's highest-leverage ask, pre-empt the real-data round)
- **Source = a SELF-CONTAINED md_store write store** (NO external data source like S7's stats-cache — Journal owns its data). `journal/<id>.md`, YAML front-matter + body, 1 git commit/write. `settings.journal_dir` ALREADY exists (config.py:137); the `journal/` dir exists but is EMPTY (fresh start — like notes/graveyard were). The closest precedent is the NOTES module (slug-id, yaml.safe_dump/safe_load, glob("*.md"), fail-open parse, write_file-per-entry) — mirror it.
- **The real-data EDGES to handle (these are where first-build is weakest — name + pre-empt):**
  1. **`pnl` is a FREE-FORM string** — "+5.5%", "-4.1%" (percent) BUT the mock also has currency display strings elsewhere ("$2,000" size, "62,000đ" px). pnl specifically is percent-string. The stats parser (winRate/avgPnl) must parse leading sign+number, and **fail-SOFT on anything unparseable** (→ treat as open/excluded + warn, NEVER crash the stats). A "+18%" parses; a hypothetical "$200" pnl or "" does not → excluded.
  2. **SPARSE calibration data** — early/real entries may have NO confidence or NO outcome (open). calibration only buckets CLOSED entries WITH a confidence value. Real data will often have few/none → calibration = empty list (honest "chưa đủ dữ liệu"), NOT a fabricated curve. (Same class as S8's null-lesson — the real-data edge the clean mock hides: every mock entry has pnl+tag, but none has confidence/thesis.)
  3. **EMPTY journal/ start** — fresh dir → `{entries:[], count:0, winRate:null, avgPnl:null, ...}`, 200 not 500.
  4. **NO finance/market tie-back this sprint** — ARCH §9 says Journal "dùng finance/market" for calibration, but auto-pulling current price to compute pnl is DEFERRED (out of scope below). pnl is user-entered. So NO cross-module data dependency this sprint → no Finance/Market reader edge. (Named so backend doesn't go build a tie-back.)

## The framing resolution (the key kickoff decision)
The **mock** (`SCREENS.journal`) shows a TRADE LOG (date/action/asset/size/px/reason/tag/pnl + win-rate/avg-pnl/ladder-discipline stats). The **SPEC §S7** wants a DECISION JOURNAL with CALIBRATION (thesis/negation-condition/confidence%/calibration-scoring/process-vs-pnl/post-close-reconciliation). These are two framings of "journal."
**Decision (north-star: full feature per SPEC, port the mock):** ONE `JournalEntry` shape that UNIFIES both —
- **Execution fields (mock):** date, action(BUY/SELL), asset, size, px, tag, reason, pnl.
- **Decision/calibration fields (SPEC):** thesis, negationCondition (điều kiện phủ định), confidence (0-100%), channel, outcome (open/right/wrong after close), lesson.
The mock SCREEN renders the trade-log table + the 4 stat cards (win-rate/avg-pnl/ladder-discipline/this-month) — all DERIVED. Calibration is the SPEC's monthly-review layer (derived: does confidence-band match actual win-rate). Mock fields are required-ish; SPEC fields optional (a quick trade log entry needn't fill thesis, but CAN — full feature available, simple entry possible).

## Vocab-lock (mock labels vs SPEC)
Mock: "Nhật ký lệnh", "ghi lại lý do không chỉ con số", tabs Tất cả/Mua/Bán/Ladder, "Ghi lệnh" button, stats Win rate / P&L TB / Kỷ luật ladder / Lệnh tháng này, table cols Ngày/Lệnh/Tài sản/Khối lượng/Giá/Loại/P&L/Lý do. SPEC adds: thesis, điều kiện phủ định, confidence %, calibration review. FE ports mock labels verbatim; the entry FORM adds the SPEC decision fields.

## Honest-mirror — every SCREENS.journal panel (none dropped)
| Mock panel | Data | Sprint 9 |
|---|---|---|
| Title + tabs (Tất cả/Mua/Bán/Ladder) + "Ghi lệnh" | filter + create | **LIVE** |
| 4 stat cards (Win rate / P&L TB / Kỷ luật ladder / Lệnh tháng này) | derived from entries | **LIVE** |
| "Mọi lệnh" table (date/action/asset/size/px/tag/pnl/reason) | journal entries | **LIVE** |
| (SPEC) entry form: thesis/negation/confidence/channel | create form | **LIVE** |
| (SPEC) calibration review (confidence band vs actual) | derived | **LIVE** (a calibration stat/panel — confidence-bucket accuracy) |
| (SPEC) post-close reconcile (outcome + lesson) | PUT entry (close) | **LIVE** (mark outcome right/wrong + lesson) |

## JournalEntry + JournalStats SHAPE (full field list — T1 gating dispatch msg #1)
```
JournalEntry {
  id:        str            # slug(asset-date)-<hex> or uuid-short
  date:      str            # ISO-8601 UTC (entry/decision date)
  action:    Literal["BUY","SELL"]
  asset:     str            # "BTC", "ETH", "VNM"...
  size:      str            # free-form "$2,000" / "62,000đ" (mock is a display string — keep simple)
  px:        str            # entry price, free-form display string (mock: "$68,240")
  tag:       str            # "ladder","dca","rebalance","value"... (free-form)
  reason:    str            # the decision rationale (mock's "Lý do")
  channel:   Literal["crypto","etf","vn","dry"] | None  # finance channel (calibration grouping)
  thesis:    str | None     # SPEC: the investment thesis
  negationCondition: str | None  # SPEC: "what would prove me wrong"
  confidence: int | None    # SPEC: 0-100% conviction at decision time
  pnl:       str | None     # null = open position; "+5.5%" / "-4.1%" when closed (display string, mock-aligned)
  outcome:   Literal["open","right","wrong"]  # open until closed; then thesis right/wrong
  lesson:    str | None     # post-close learning
  createdAt: str            # ISO-8601 UTC
  updatedAt: str            # ISO-8601 UTC
}
JournalStats {
  entries:        list[JournalEntry]
  count:          int
  winRate:        float | None   # closed entries with positive pnl / total closed (None if 0 closed) — carries {wins, closed}
  avgPnl:         float | None   # mean of closed pnl % (parse the +X%/-X% strings) — carries {sum, closed}
  ladderDiscipline: float | None # count(tag=="ladder")/count(total) — "% ladder-tagged" NOT plan-adherence (see Logic) — carries {ladderCount, total}
  thisMonth:      {total, buy, sell, ladder}  # this-month counts
  calibration:    list[{band, predicted, actual, n}]  # SPEC: confidence buckets (e.g. 60-70%) vs actual win-rate
}
```
Endpoints: `GET /journal?action=&tag=&channel=&asset=` (list+filter) · `GET /journal/{id}` · `POST /journal` (create) · `PUT /journal/{id}` (update/close — set pnl+outcome+lesson) · `DELETE /journal/{id}`. Stats either folded into the list response or a `GET /journal/stats`. Envelope + codes.

## Tasks (4: BE gating → FE → tester)
- **T1 [backend, GATING] — journal module (schema/service/router) via md_store.**
  - Mirror the NOTES pattern: entries as md_store `journal/<id>.md` (YAML front-matter + reason/thesis body), 1 git commit per write. FREEZE field-by-field + curl payload.
  - Derived stats (winRate/avgPnl/ladderDiscipline/thisMonth/calibration) — the §Logic below.
  - **Write module → write-failure teeth-tests** (Notes lesson): failed md_store write surfaces an error, NO silent loss (fail-closed on write).
  - Gates T2/T3.
- **T2 [backend] — journal router** (if separate). GET/POST/PUT/DELETE /journal + filters + stats. Auto-discovered. (May fold into T1.)
- **T3 [frontend] — S7 Journal screen** (`app/journal/page.tsx`, replace EmptyScreen).
  - Port SCREENS.journal: tabs filter, 4 stat cards, trade-log table, "Ghi lệnh" create form (execution + SPEC decision fields), close-entry (PUT outcome+pnl+lesson), calibration panel. Blocked by T1 frozen + serving.
- **T4 [tester] — verify journal.**
  - pytest (CRUD: create→read-back md+front-matter, **git-commit landed** per Sprint-13; write-failure teeth; stats math winRate/avgPnl/ladderDiscipline/calibration on fixtures; pnl-string parsing; filter by action/tag/channel). Chrome `docker compose up -d`: create entry → appears in table + stats update, close an entry → pnl/outcome, value-by-value vs `GET /journal`, console 0, 0 unhandled. Pre-scaffold from T1.

## Logic/Algorithm (architect-decided — decide-and-log)
- **id:** `slug(asset)-<6hex>` (readable: `btc-3f2a`), else `entry-<6hex>`.
- **Storage:** `journal/<id>.md` YAML front-matter (all fields except reason/thesis) + body = reason + thesis + lesson (markdown). 1 md_store write = 1 commit (Notes pattern).
- **pnl parsing:** pnl is a display string ("+5.5%", "-4.1%", null=open). For avgPnl/winRate, parse the leading sign+number; null/unparseable → treated as open (excluded from closed stats). (Keep pnl a string for mock-fidelity; parse only for stats.)
- **winRate:** closed entries (pnl not null) with parsed pnl > 0, / total closed. None if 0 closed. carries {wins, closed}.
- **avgPnl:** mean of parsed closed pnl %. None if 0 closed. carries {sum, closed}.
- **ladderDiscipline (LOCKED — no ambiguity):** `count(tag=="ladder") / count(total entries)`. carries `{ladderCount, total}` (self-describing). **LABEL it honestly = "% lệnh ladder-tagged"** (share of trades that were planned ladder entries), NOT "% plan-adherence" — we have NO per-trade followed-plan field, so we CANNOT compute true plan-adherence; do not imply we can. The mock's "94% theo đúng kế hoạch" is approximated by the ladder-tag ratio + an honest label. None if 0 entries. (A real adherence metric needs a new per-entry `followedPlan` field — OUT of scope this sprint.)
- **thisMonth:** count entries with date in the current month, split by action + ladder tag.
- **calibration (SPEC core — LOCKED):** bands `["50-59","60-69","70-79","80-89","90-100"]` (drop confidence<50 or null — not calibration data). Population per band = CLOSED entries (pnl parses) with confidence in band. Per band: `n`=count, `predicted`=band MIDPOINT (54.5/64.5/74.5/84.5/95.0), `actual`=`%(outcome=="right")`×100 (1dp). **`outcome` is the right/wrong source (pnl-seeded at close: pnl>0→right, user-overridable) — NOT pnl directly: calibration scores the THESIS (SPEC "process tách P&L"), while winRate/avgPnl score the MONEY. Two intentional axes.** n=0 bands OMITTED; ALL-empty → `[]` (the current real state — no confidence entries yet — honest "chưa đủ dữ liệu", NOT a bug). carry n (FE grays low-n bands).
- **outcome:** "open" until pnl set (close); on close, the user marks right/wrong (or derive: pnl>0 → right, else wrong, as a default the user can override). Lean: explicit on close, default from pnl sign.
- **channel:** for calibration-by-channel grouping (optional this sprint — the by-confidence-band calibration is the SPEC's core).

## Defensive (MANDATORY — WRITE module, fail-CLOSED on write)
- **Write-failure teeth (Notes lesson):** md_store write fails → surface the error (500 or explicit fail response), do NOT return success with no entry written. No silent loss.
- Empty journal/ → `{entries:[], count:0, winRate:null, ...}`, 200 not 500.
- Malformed entry file → skip+warn (fail-open on READ, like notes).
- 0 closed entries → winRate/avgPnl = null (not 0 — null means "no data", honest). carries the {wins,closed}/{sum,closed}.
- Unparseable pnl string → treat as open (excluded from closed stats) + warn.
- confidence out of 0-100 → 422 on input.
- Unknown id (GET/PUT/DELETE) → 404. action not BUY/SELL → 422. Empty asset/reason → 422 (min_length 1).
- calibration with no confidence-tagged closed entries → empty list (honest "chưa đủ dữ liệu").

## Dispatch standards
- Runtime: `docker compose up -d` (FE :3010 → BE :8001; DETACHED — leave it up). Baseline: pytest 499, vitest 281 (post-S8).
- **`## Read first (memory)` per role** (BE → `schema-freeze-gate` + `unhandled-errors-not-green` + `test-where-the-reader-greps` + the Notes md_store pattern; FE → `mock-diff-catches-dropped-feature` + `unhandled-errors-not-green` + `dev-server-ports`; tester → `verify-live-app-not-just-suite` + `behavior-test-not-field-read` + `workaround-then-ask-why-accepted`).
- **Full field list in T1 msg #1.** Freeze field-by-field. Test-ownership-split. Container-up-detached.
- FE: mock = SCREENS.journal, mirror frozen shape render-only; the create FORM adds the SPEC decision fields.

## Dispatch ordering
1. T1 GATING (journal module via md_store + stats) alone → freeze.
2. T2 (router) after T1 (or folded).
3. T3 (FE) after schema frozen + serving. T4 pre-scaffolds from T1.

## Out of scope (north-star)
- **journal-nudge routine** (price-hits-rung → remind to log) — Automation sprint (ARCH §9 step 7); Journal SHOWS/stores, the scheduled nudge is separate.
- **Auto-link to Finance positions** — calibration references confidence/outcome this sprint; tying an entry to a live Finance holding (auto-pull current px) is a later enhancement. Entry px is a manual display string for now (mock-aligned).
- **Rich pnl computation** — pnl is a user-entered display string (mock-fidelity); auto-computing pnl from entry-px vs current-price (via Market) is a later enhancement.
- **No WYSIWYG** — thesis/reason/lesson are markdown textareas stored raw (Notes pattern).
- **Stricter ladder-discipline** (did the entry follow the actual ladder plan from Finance) — this sprint uses the tag ratio; the plan-adherence version needs Finance ladder integration (defer).
