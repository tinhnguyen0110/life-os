# plan_sprint_uxpolish-wiki — #143 UI/UX polish pass: /wiki

> #143 UX-polish lane, screen 2 = /wiki (after /tracing bcb09d9). Architect Chrome-audit → rough-edge list → team-lead scope pick → FE one-screen behavior-preserving pass → 4-step → commit → team-lead before/after gate.

## Live Chrome audit (architect, :3010, 2026-06-23) — rough-edge list
Screen is FUNCTIONAL + console-CLEAN (0 errors) + rich (KPI tiles, explorer tree, inbox, orphan sweep, op-log, proposal queue, the #142-portaled folder ⋯ menus). Polish nits:

### W2 — "fleeting" labeled with TWO different numbers (the clearest clarity nit)
- KPI tile reads **"FLEETING 34"**; the INBOX section badge reads **"63 fleeting"**. Same word, two numbers → confusing (a user sees 34 vs 63 both "fleeting"). They're likely DIFFERENT metrics (34 = notes with fleeting STATUS; 63 = inbox items needing refine) but the labels don't disambiguate. Fix: relabel one so they read distinctly — e.g. the inbox badge → "63 cần refine" / "63 chờ xử lý" (it's the refine-queue count, not the fleeting-status count). Confirm the intended meaning with team-lead, then relabel. Pure label change, no logic.

### W4 — accent badge on an EMPTY queue (same anti-pattern as tracing R2)
- PROPOSAL QUEUE badge "0 chờ duyệt" = rgb(255,106,51) (the accent/orange) even when the count is **0**. Same "loud color for a benign empty state" pattern we just fixed in tracing R2 (the Đặt-giờ pill). An empty queue should RECEDE (muted) — reserve the accent for when there's actually something to review (count > 0). Fix: conditional — accent when >0, muted (--tx-2) when 0. Behavior-preserving (style only).

### W1 — section-badge color consistency (minor)
- Section header badges differ: INBOX "63 fleeting" = yellow (245,180,61) on dark-yellow bg; ORPHAN SWEEP "15 cô lập" = red; PROPOSAL QUEUE "0 chờ duyệt" = orange/accent. Confirm these colors are SEMANTIC-intentional (yellow=refine-pending, red=problem/orphan, accent=action-queue) vs drift. If intentional → leave; if drift → align to a consistent badge scale. Likely mostly intentional — verify-only.

### W3 — explorer "0"-count folders (verify, likely intentional)
- agents (0), Projects (0) folders show a "0" count. Confirm showing empty folders with "0" is intentional (vs hiding them). Likely fine (the vault structure should show all folders). Verify-only, probably skip.

### W5 — empty/zero-state honesty (verify, looks good)
- "PROPOSAL QUEUE 0 chờ duyệt — Chưa có đề xuất AI…" reads as an honest, explained empty state (good). Confirm consistent with the tracing empty-states. Likely fine.

## Severity / recommendation
- **W2 (fleeting label collision) = the clearest worth-fixing nit** — a real clarity bug (two "fleeting" numbers). Needs team-lead confirm on the intended label.
- **W4 (accent-on-empty-queue) = a clean win** — it's the SAME anti-pattern as tracing R2 (we just established the principle: loud color for a benign empty state → recede). Consistent to apply here.
- W1 (badge colors) = verify-only (likely semantic-intentional).
- W3/W5 = verify-only, likely skip.
- Behavior-preserving ONLY (labels + conditional badge color); NO logic, don't touch the #142 portaled folder ⋯ menus or the explorer tree behavior. vitest green (visual/label → team-lead Chrome before/after).

## Open question for team-lead (scope)
- W2: confirm the inbox "63" is the refine-queue count (not fleeting-status) → relabel to "63 cần refine"? (need your call on the exact label.)
- W4: apply the tracing-R2 principle (accent→muted when count 0) to the proposal-queue badge? (recommend yes — consistent.)
- W1/W3/W5: verify-only — fold any genuine drift, else skip (don't manufacture work).
