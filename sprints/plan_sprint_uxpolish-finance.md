# plan_sprint_uxpolish-finance — #143 UI/UX polish pass: /finance

> #143 UX-polish lane, screen 3 = /finance (after /tracing bcb09d9, /wiki 87e0a43). Architect Chrome-audit → rough-edge list → team-lead scope → FE pass → 4-step → commit → gate.

## Live Chrome audit (architect, :3010, 2026-06-23) — rough-edge list
🔴 HONEST: /finance is notably MORE polished than tracing/wiki (it's a mature screen). It's FUNCTIONAL + console-CLEAN + data-correct ($10,624 total, equity-curve $10,626, allocation crypto 100% / Vốn gốc $10,637, full ticker). Few actionable FE-polish nits — most observations are taste-calls or backend-perf, not clear polish wins. Don't manufacture work.

### F1 — staggered KPI load: the 3 top KPI tiles skeleton for ~2s while the rest renders (perceived slowness)
- The TỔNG TÀI SẢN / DRY POWDER / P&L MỞ tiles show skeleton dots for ~2s AFTER the equity-curve + allocation table already render → the most important numbers load LAST/slowest. RESOLVES correctly (not a stuck-state — verified after settle: $10,624; console clean).
- 🔴 NOT an FE-polish bug: this is the known finance no-cache fetch latency (memory `finance-perf-no-cache` — get_quote fetches fresh per coin). The real fix is BACKEND perf (memoize/batch/TTL), already a known area. FE could only tighten the skeleton or surface the equity-curve total sooner — low value. → recommend PARK as a backend-perf item, not an FE polish task.

### F2 — every 0%-holding channel (dry/etf/vn) shows a ⚠ drift warning (taste/decision call)
- dry "⚠ 0% vs 20% (−20.0)", etf "⚠ 0% vs 24% (−24.0)", vn "⚠ 0% vs 18% (−18.0)" — 3 ⚠ rows for "you hold nothing here". This is arguably CORRECT (it IS drift from the golden-path target) — but for a user 100%-in-crypto-by-choice, 3 ⚠ for empty channels may be noise (same family as the W4/R2 "loud signal for a benign state"). HOWEVER unlike W4 (an empty QUEUE is truly benign), allocation drift IS a real signal the finance tower wants surfaced. → TASTE/decision call for team-lead/user, NOT a clear nit. Recommend LEAVE unless team-lead wants the ⚠ softened when a channel is intentionally 0.

### F3 — "—" in the P&L column for 0-holding channels (verify, looks honest)
- dry/etf/vn show "—" in the rightmost P&L cell → honest empty-state for no-holding. Looks fine. Verify-only, skip.

### F4 — warning-styling consistency (verify, looks fine)
- The top ⚠ banner + per-channel ⚠ badges + KPI deltas (red ▼ / green ▲) — confirm consistent, not over-warned. Looks intentional + consistent. Verify-only, skip.

## Severity / recommendation
- **There is NO clear FE-polish win on /finance** (unlike tracing R2 / wiki W2+W4). The screen is mature.
- F1 = a known BACKEND-perf item → park (not FE polish).
- F2 = a taste/decision call → team-lead/user, likely LEAVE (drift is a real signal).
- F3/F4 = verify-only, fine, skip.
- 🔴 Honest recommendation: /finance likely needs NO polish commit. Confirm with team-lead — if they/their eye agree it's clean, SKIP /finance and move to /projects (don't manufacture a commit). If team-lead's eye catches something specific, scope that.

## Open question for team-lead
- Do you see a specific /finance nit worth an FE pass? My audit says it's mature + clean — the only items are F1 (backend-perf, park) + F2 (taste, likely leave). Recommend SKIP /finance polish + move to /projects, OR you name a specific fix. Don't-over-build: no commit if there's no real win.
