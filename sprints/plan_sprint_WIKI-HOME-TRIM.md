# Sprint WIKI-HOME-TRIM — remove "Inbox cần refine" from Wiki Home

Board task: #182. User CHỐT: AI-first → no manual refine triage → remove the "Inbox cần refine" section on Wiki Home. Notes still viewable/editable in Vault/Graph.

## Kickoff — 2026-06-29

### Findings on disk (wiki/page.tsx)
- The "Inbox cần refine" panel = L317-336 (a `grid` 2-col: inbox column + orphan column, `gridTemplateColumns: "1fr 1fr"` L318).
- `const inbox = overview.inbox` (L196) + `InboxRow` (imported L26 from _rows) are used ONLY by this panel on the home page. After removal both become orphan in page.tsx.
- KPI "Fleeting" StatTile (L294, `s.byStatus.fleeting`, sub "chờ refine") = a DIFFERENT metric (fleeting-STATUS count, not the inbox-queue) → KEEP.
- `overview.inbox` (BE payload) may be used elsewhere (life_brief) → do NOT touch BE; the FE just stops rendering its panel.
- #94 bulk-select on the orphan list (L60-80, L200-211) → KEEP.

### Decisions (architect)
- Remove the "Inbox cần refine" panel; the orphan-sweep column → FULL-WIDTH (grid 2col → 1col, or drop the grid wrapper). Keep #94 bulk-select working in the now-full-width orphan list.
- Drop `const inbox` + the `InboxRow` import from page.tsx (now unused). Leave `InboxRow`'s export in _rows.tsx (harmless; remove only if a lint flags it — not worth churn).
- KEEP the KPI Fleeting tile (different metric) + orphan KPI + density bar.
- No BE change (overview.inbox stays in the payload for life_brief etc.).
- **Parallel-safe with #181**: wiki/page.tsx is fully DISJOINT from #181's files (graph/page.tsx + tracing service). fe implements this in parallel (free post-T2-gate); I commit it SEQUENTIALLY after #181 (one committer — implement-parallel, commit-serial).

### Defensive
- Notes NOT lost — the panel was a SUMMARY (slice 4); the data lives in Vault/Graph (this only drops a home render). overview.inbox kept in BE.
- #94 bulk-select still works full-width. KPI Fleeting tile present. No empty-vault regression.
- Disjoint file from #181 → no commit race (sequential commits anyway).

### BE/FE split
- **FE only.** wiki/page.tsx (remove panel + full-width orphan + drop unused inbox/InboxRow). BE untouched.

### Final task list
- **T1 (FE):** remove the "Inbox cần refine" panel (L317-336), orphan-sweep → full-width, drop the now-unused `inbox` const + InboxRow import; keep #94 bulk-select + KPI Fleeting + orphan KPI. Tests: home does NOT render the inbox panel; orphan list full-width + bulk-select still works; Fleeting tile present; empty-vault state intact.

### Dispatch plan
- frontend ← T1 (parallel with #181, disjoint file). tester + team-lead Chrome-gate: home no "Inbox cần refine" · orphan full-width + bulk works · KPI Fleeting present · console clean.

## Assumptions (user-review) — filled in end_sprint
