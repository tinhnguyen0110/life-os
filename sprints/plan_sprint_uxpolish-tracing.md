# plan_sprint_uxpolish-tracing — #143 UI/UX polish pass: /tracing

> #143 UX-polish lane (continuous, one-screen-per-commit). team-lead: START with /tracing — daily-driver + heaviest recent rework (#136 redesign + #137 template-sets + #139 activity-row) → most likely polish debt. Flow: architect Chrome-audit → rough-edge list → team-lead → dispatch FE one-screen pass (behavior-preserving, visual/interaction ONLY, no logic, don't regress #136/#137/#139) → 4-step → commit fix(sprint-uxpolish-tracing) → HOLD for team-lead Chrome verify → push.

## Live Chrome audit (architect, :3010, 2026-06-23) — rough-edge list
Screen is FUNCTIONAL + console-CLEAN (0 errors) + the recent fixes render (per-card edit, Đặt-giờ pills, template "+ Từ mẫu", ⋯ menus now portaled from #142). These are POLISH nits, not bugs:

### R1 — time-column alignment: set-time row vs unset row don't line up (the clearest nit)
- The set-time row ("Viết nhật ký" 07:00) uses `tl-time-btn` (plain time text); the 6 unset rows use a red `tl-settime-pill` ("⏰ Đặt giờ"). They occupy the same left slot but have DIFFERENT width/visual weight → the checkbox + activity-name columns DON'T align vertically between a timed row and an untimed row (the name column shifts). Polish: give the time slot a FIXED width so `tl-time-btn` and `tl-settime-pill` reserve the same box → checkbox/name align in a clean column down all rows.

### R2 — the red "⏰ Đặt giờ" pill is visually heavy for an empty/default state
- 6 of 7 rows show a saturated red/accent pill for "no time set". Red usually signals negative/destructive; for a neutral "set a time" affordance it's loud + repetitive down the list. Polish: consider a quieter/ghost style for the unset pill (muted/outline) so a SET time (or a real alert) stands out, and the default state isn't a wall of red. (Confirm with team-lead — may be intentional accent.)

### R3 — empty states: verify honest + styled (not bare)
- Notes panel: "Chưa có ghi chú nào." + "0 ghi chú". Streak: "streak tốt nhất 0d · mở để xem". These are honest (good) but check they're STYLED as intentional empty-states (centered, muted, maybe an icon/hint) vs bare text. The notes "Chưa có ghi chú nào." looks like plain centered text — fine, but confirm consistency with EmptyScreen elsewhere.

### R4 — ⋯ ops button discoverability (verify, likely OK)
- `tl-ops-btn` opacity:0.55 baseline (visible, not hover-only — the #136/#137 fix held). Likely FINE; flagging only to confirm the .55 reads as discoverable (not too faint) on the daily-driver. Live measure = visible. No action unless team-lead's eye disagrees.

### R5 — add-row controls spacing (minor)
- The "Thêm việc cần làm hôm nay…" input + the "08:00" time input + "Thêm" + "+ Từ mẫu" buttons sit in one row; in the screenshot the time-input/Thêm edges crowd slightly. Polish: confirm consistent gap between the add-input, time field, and the two buttons (no crowding/overlap at the daily-driver width).

### R6 — section consistency (minor)
- "HÔM NAY · THEO GIỜ" and "GHI CHÚ TRONG NGÀY" panels + "STREAK & LỊCH SỬ 12 TUẦN" — confirm consistent panel header style, padding, and the count-badge alignment (e.g. "0/7 xong", "0 ghi chú" right-aligned). Looks consistent; confirm no drift.

## Severity / recommendation
- **R1 (alignment) is the one real, clearly-worth-fixing nit** — a visible column-misalignment on the daily-driver. 
- R2 (red pill) is a TASTE call → confirm with team-lead/user before changing (may be intentional).
- R3/R4/R5/R6 are verify-and-tidy (likely small or already fine).
- Behavior-preserving ONLY — CSS/markup spacing + the time-slot fixed-width; NO logic, don't touch #136 edit / #137 templates / #139 row-content. vitest stays green (visual → team-lead Chrome before/after gate).

## Proposed dispatch (after team-lead picks scope)
One FE polish pass: R1 (fixed-width time slot for column alignment) as the core + R3/R5/R6 tidy where genuinely needed; R2 only if team-lead greenlights the pill restyle. Commit `fix(sprint-uxpolish-tracing)`. team-lead Chrome before/after gate.

## Open question for team-lead
- R1 fix = yes (clear nit). R2 red-pill restyle — your call (taste; may be intentional accent — confirm before I scope it). R3/R4/R5/R6 — fold the genuine ones into the same pass or skip if fine?
