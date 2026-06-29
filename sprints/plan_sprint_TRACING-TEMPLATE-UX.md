# Sprint TRACING-TEMPLATE-UX — import=replace (atomic) + modal list-render

Board task: #181. Follow-up #180. 2 user asks on "+ Từ mẫu".

## Kickoff — 2026-06-29

### Findings on disk
1. `import_template_set` (service.py L772) creates a UNIQUE id per member (slug+suffix) → re-import ADDS duplicates (board accumulates). User wants import → board = EXACTLY the template.
2. TemplateSetsModal (LIST view L142-156) renders each set as a CARD with a compact " · "-joined member preview string. User wants a per-member LIST like the /tracing timeline (giờ · tên · nhắc-chip).
3. archive_activity (L369, soft-delete recoverable) + list_activities (active) available. Import = POST /template-sets/{id}/import → page refetches GET /tracing.

### Decisions (architect)
- **D1 — import = ATOMIC replace (BE).** In import_template_set: (1) snapshot the currently-ACTIVE activity ids (`list_activities`); (2) CREATE all members (keep unique ids — avoids collision); (3) ONLY after all creates succeed, archive the snapshotted old ids. **Order = create-then-archive** → atomic-safe: if a create fails mid-way, NO old activity was archived → the board is never left empty (the user's "đừng để board trống nếu create lỗi"). Recoverable (archive=soft-delete). Re-import → the prior import's activities get archived → board = exactly the new template (no doubling). Return (created, skipped, archivedCount) so the FE can toast.
  - Edge: a member whose create fails → it's in `skipped`; the old set is STILL archived only if ALL creates succeeded — actually safest: archive the old ids only for the ones we successfully replaced. Simpler + still atomic: create all → if ≥1 created, archive the old snapshot; report skipped. (The board has the new members; nothing lost—archived is recoverable.) architect locks: create-all-first, then archive-old-snapshot, report skipped — board never empty because creates ran first.
- **D2 — modal list-render (FE).** TemplateSetsModal LIST view: render each set's members as a per-row LIST (each member: time · content · a remind chip if remindRepeat≠off) mirroring the /tracing timeline row, instead of the compact card string. "Nhập vào hôm nay" stays = the (now replace) import.
- **D3 — confirm-UX = skip-confirm + informative toast (FAST, recoverable).** Replace is destructive-but-recoverable (archive). User wants NHANH → no modal-confirm; on import show a toast "✓ Đã nhập mẫu · N việc · M việc cũ chuyển vào thùng rác (khôi phục được)". (Recoverable archive + fast = acceptable; a confirm would slow the flow the user explicitly wants fast.)
- KEEP: the 3-check-in default (#180), #168-180 + the graph arc, deterministic, no dep.

### Defensive
- Atomic: create-first → board never empties on a mid-create failure. Replace recoverable (archive). Re-import idempotent-ish (board = the template, old archived, no doubling). Skipped members reported honestly.
- The default template-set (#180 "Check-in hàng ngày") still imports correctly (3 check-ins with custom/daily reminders).
- Don't regress #168-180 or the graph.

### BE/FE split
- **BE** ← D1 import=atomic-replace (service.py import_template_set + router response shape). 
- **FE** ← D2 modal list-render + D3 toast (TemplateSetsModal).
- Parallel (disjoint: BE service vs FE modal). The wire: import response gains `archivedCount` (additive) — FE reads it for the toast.

### Final task list
- **T1 (BE):** import_template_set → atomic replace (snapshot active → create all members → archive old snapshot; create-first so never-empty-on-failure; return created/skipped/archivedCount). Tests: re-import doesn't double (board=template); a forced create-failure leaves the old board intact (atomic); archived recoverable; the #180 default set imports the 3 check-ins.
- **T2 (FE):** TemplateSetsModal LIST view per-member rows (time·content·remind-chip, timeline-like) + import toast (N imported · M archived, recoverable). Tests: list renders each member as a row; import calls the replace + toasts the counts.

### Dispatch plan
- backend ← T1 ∥ frontend ← T2 (disjoint). tester: replace (no double) + atomic (no empty on failure) + list-render. team-lead Chrome-gate: add a temp activity → Nhập mẫu → board = ONLY the template (temp gone, no doubling) · modal shows a per-member list (not a card) · console clean.

## Assumptions (user-review) — filled in end_sprint
