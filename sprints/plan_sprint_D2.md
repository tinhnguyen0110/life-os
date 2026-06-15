# Sprint D2 — finance-snapshot routine (equity-curve capture, built-but-not-wired)

> Answer-quality audit (memory `answer-quality-audit-data-gaps-2026-06-15`) D2: "how has my wealth trended" is weak because `finance/history` has 1 point — `take_snapshot()` exists but is never scheduled. Wire it into morning_pull. Backend-only, small.

## Kickoff — 2026-06-15 (architect)

### Verified on disk
- **`finance.service.take_snapshot()`** (service.py:372) — records TODAY's portfolio snapshot, **ONE row per UTC day (upsert — idempotent)**: totalValue + per-channel from `get_overview()`. Returns `{day, ts, totalValue, byChannel}`. An empty portfolio snapshots $0 (a real data point). So calling it twice/day is safe (upsert, no dup row).
- **`value_history(days)`** (service.py) — the equity curve reader; empty list until snapshots exist. (This is what fills as snapshots accumulate.)
- **`morning_pull()`** (automation/service.py:162) — cron 08:00. Already reads finance (`fin.get_overview()`) for the pull summary, THEN has a **fail-soft brief add-on** (try/except: a brief failure is noted but does NOT downgrade a successful pull — `pull_status` is decided BEFORE the add-on; final `status = pull_status if "warn" else brief_status`). The snapshot follows the SAME add-on pattern.
- Existing tests: `tests/test_automation.py` covers morning_pull.

### 🔑 THE DECISION (architect call — fail-soft add-on, mirrors the brief step)
Add `fin.take_snapshot()` as a **best-effort add-on** in `morning_pull()`, after the finance read, in its OWN try/except — per the `fail-closed-write-fail-soft-addon` discipline: **the snapshot's failure must NOT downgrade a successful pull** (the pull's contract is the read summary; the snapshot is a capture add-on, exactly like the brief).

Placement + status rule:
- After the existing finance read step (reuse the `from modules.finance import service as fin` already imported there), in a SEPARATE try/except so a snapshot error is isolated.
- On success → append a part ("equity snapshot $X" or "snapshot ok"). On failure → `logger.error(...)` + append "snapshot ERR (...)" + a `snapshot_status="warn"` that, like brief, does NOT downgrade a successful PULL (only notes it).
- **Final status rule:** the pull's primary contract still decides ok/warn; the snapshot add-on (like the brief add-on) only contributes a noted warning, never fails a pull that read successfully. Keep the existing `status = pull_status if pull_status=="warn" else <add-on status>` shape — fold the snapshot into the add-on tier (e.g. `status = pull_status if pull_status=="warn" else worst(brief_status, snapshot_status)`).

### Scope boundary
- **Capture going FORWARD only** — this fills the curve day-by-day from now. It does NOT backfill past net-worth (no past daily snapshots exist; fabricating them would lie). Honest + correct — the user sees the curve grow from today. (Log this in §Assumptions so it's not mistaken for a bug "why is my history short".)
- Do NOT change `take_snapshot` itself (it works, it's idempotent). Do NOT add a separate scheduled routine (morning_pull is the daily 08:00 cron — reuse it; no new APScheduler job needed).

### Final task list (single backend lane)
- **D2 [backend]** — in `morning_pull()`, add `fin.take_snapshot()` as a fail-soft add-on after the finance read; note success/failure in the summary parts; snapshot failure does NOT downgrade a successful pull (mirror the brief add-on's status discipline). Tests in test_automation.py.

## Verification (distinguishing cases)
- **Capture works:** after a `morning_pull()` run, `value_history()`/`finance/history` has a snapshot row for today (count increments from baseline).
- **Idempotent (upsert, no dup):** a SECOND `morning_pull()` same UTC day → still ONE row for today (count does NOT increment again — take_snapshot upserts per day). Distinguishing: run twice, assert exactly 1 today-row.
- **Fail-soft (the add-on discipline):** mock `take_snapshot` to RAISE → `morning_pull()` still completes + returns (pull not aborted), the finance READ part still present, status reflects the pull's success (a snapshot-only failure does NOT make a clean pull fail). Assert the pull's other parts intact + status not driven to error by the snapshot raise.
- Full suite ≥ baseline (1497), 0 errors/unhandled. types clean.

## Assumptions (user-review)
- `morning_pull()` (daily 08:00 cron) now also calls `take_snapshot()` (fail-soft add-on) → the equity curve fills one row/day going forward. take_snapshot upserts per UTC day (a second run same day overwrites, no dup).
- **Forward-only capture** — does NOT backfill past net-worth (none exists; fabricating would lie). The curve grows from today; a short history early on is honest, not a bug.
- Snapshot failure is best-effort: it notes a warning but never fails a pull whose reads succeeded (same as the existing brief add-on).
