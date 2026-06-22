# end_sprint_uxpolish-wiki — #143 /wiki polish: disambiguate the two "fleeting" counts (W2) + mute empty proposal badge (W4)

> #143 UX-polish lane, screen 2 = /wiki (after /tracing bcb09d9). Architect Chrome-audit → team-lead scope (W4 + W2-trace-then-label; W1/W3/W5 skip) → FE behavior-preserving pass → 4-step → commit → team-lead before/after gate.

## What shipped (1 file: app/wiki/page.tsx)
- **W2 (label honesty):** the INBOX badge "{inbox.length} fleeting" → **"{inbox.length} cần refine"** (+ testid `vault-inbox-count` + a comment). The KPI tile "Fleeting 34" is UNCHANGED (it's correct). Both were labeled "fleeting" with different numbers (34 vs 63) → confusing; now each reads by its true meaning. Pure label, no logic.
- **W4 (quiet empty state):** the PROPOSAL QUEUE badge color is now CONDITIONAL — accent (var(--accent)/--accent-dim) when `proposalCount > 0`, MUTED (var(--tx-2)/transparent) when 0. Same quiet-empty principle as tracing R2. Style-only inline conditional (no new CSS class).

## W2 — traced FIRST (honest-mirror), NO FE bug + a real backend finding
FE (and I, independently) curled live REST `/wiki/overview`:
- `stats.byStatus = {fleeting:34, developing:3, evergreen:13}` → sums to **50 = totalNotes**. So the KPI tile "Fleeting **34**" = `byStatus.fleeting` = the active fleeting-STATUS note count → CORRECT, not a wrong binding.
- `overview.inbox.length = **63**` (all 63 status:"fleeting") → the inbox badge counts the REFINE-QUEUE, a different/broader scope.
- So 34 and 63 are GENUINELY DIFFERENT real metrics sharing the word "fleeting" — not a bug. Fix = label distinctly (KPI keeps "Fleeting", inbox → "cần refine", matching its own "Inbox cần refine" kicker). Honest-mirror, source-correct.
- (team-lead's initial "don't relabel, inbox 63 is the fleeting count" was from a STALE MCP pull — MCP wiki_overview returns 80/63 incl. soft-deleted; REST returns 50/34 active-only. REST is the FE's source = authoritative. team-lead self-corrected via REST; FE's trace + my REST re-pull agree.)

## 🔶 Backend-scope finding (FE flagged, I confirmed via REST — parked, NOT this commit)
**The inbox has 63 fleeting items, but byStatus.fleeting=34 and totalNotes=50.** So the inbox's "fleeting" scope (63) EXCEEDS the whole vault's fleeting partition (34) AND totalNotes (50). A consumer-agent reading the API sees inbox=63-fleeting vs stats=34-fleeting and can't reconcile them (the inbox counts items the byStatus partition doesn't — likely pre-vault captures / a different source set). The FE now renders both honestly + distinctly-labeled (so the UI isn't misleading), but the BACKEND scope question (should the two "fleeting" scopes agree, or does the inbox count need an explicit "includes pre-vault captures" semantic?) is a separate concern → PARKED in BACKLOG_parked.md (P-3, near the MCP/REST parity P-2). Not blocking this commit.

## Verify (architect 4-step + independent REST trace + live Chrome — Rule#0)
1. **git diff:** 1 file (app/wiki/page.tsx); W2 relabel + W4 conditional. KPI tile, #142 menus, explorer untouched.
2. **Read full:** pure label + style-only conditional, no logic.
3. **Independent REST trace (Rule#0):** curled /wiki/overview myself → byStatus.fleeting=34 (sums to 50=totalNotes), inbox.length=63 (all fleeting), proposalCount=0 → confirms FE's trace + the honest labels + the backend-scope finding.
4. **tsc 0; vitest 1115** (no delta; vault 75/75 green — no test asserted the old inbox "fleeting" text; the proposal test asserts textContent not color → W4 keeps it green).
5. **🔴 Live Chrome (architect, :3010):** W2 inbox badge = "63 cần refine" (relabeled ✓), KPI tile still "Fleeting" ✓; W4 proposal badge "0 chờ duyệt" computed `color rgb(102,100,92)`=--tx-2 + `bg transparent` → MUTED at 0 ✓ (was accent). Console clean.

## Gates
- Gate 2 (Function): label + style-only; behavior preserved; tsc clean; vitest no-delta; live Chrome verified. ✓
- Gate 3 (Sprint): this doc + 4-step + independent REST trace + live Chrome + count == baseline. ✓

## Assumptions (user-review)
- **W2: the inbox badge is labeled "cần refine" (its true meaning = the refine queue), NOT "fleeting"** — team-decided honest-mirror disambiguation. The KPI "Fleeting 34" (active fleeting-status) is the accurate fleeting count. Rule: two metrics must not share one ambiguous label. How to change: rename if a clearer term emerges; the underlying numbers are source-correct.
- **W2 KPI-34 definition (logged per team-lead):** KPI "Fleeting" = `stats.byStatus.fleeting` = active (non-soft-deleted) fleeting-STATUS notes = 34. The inbox 63 = `overview.inbox.length` = the refine-queue (broader scope).

## Commit
- Hash: (filled) — `fix(sprint-uxpolish-wiki): mute empty proposal-queue badge (W4) + disambiguate the two "fleeting" counts → inbox = "cần refine" (W2)`
- Files: app/wiki/page.tsx + sprints/plan_sprint_uxpolish-wiki.md + sprints/end_sprint_uxpolish-wiki.md + sprints/BACKLOG_parked.md (the parked findings).
- HOLD push for team-lead's before/after Chrome gate (W2 distinct labels, W4 muted at 0, console clean) → OK → push. Next polish screen: finance → projects.
