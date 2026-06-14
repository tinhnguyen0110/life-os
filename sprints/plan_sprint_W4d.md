# Sprint W4d — Agent Autonomy Toggle (reverses D8 proposals-only, USER-ORDERED) · plan

> **User order (2026-06-14, direct):** add a config so the agent can write CRUD directly (bypass
> human-ratify). Chosen shape: **Full autonomous toggle** — one global Settings switch.
> ON = agent writes land in the vault directly (every kind); OFF (default) = proposals-only.
>
> ⚠️ This REVERSES the locked D8 / north-star "AI proposes, human ratifies." Reversed ONLY because
> the USER explicitly ordered it this session ([[implementer-flag-before-reversing-decision]] —
> surfaced + user-confirmed via direct answer). Built with safety guards so the north-star is the
> DEFAULT (toggle defaults OFF) and even auto-writes stay fully audited.

## Design — the toggle gates at the create_proposal chokepoint (NOT a write-server bypass)

**Key decision (D-W4d.1): auto-apply runs THROUGH the proposal pipeline, not around it.**
Every agent write still calls `create_proposal(...)` → records the proposal (intent + audit). THEN,
if the autonomy setting is ON, `create_proposal` immediately calls `accept_proposal(decided_by=
"agent:auto")` → applies via the SAME single-writer + apply-handlers + fail-closed logic. So:
- ON: the proposal is created AND auto-accepted in one call → write lands, status=accepted,
  decidedBy="agent:auto", appliedNoteId set. Still a full proposal row + audit trail (forensics
  intact — an auto-write is auditable + visible in P1 history as "accepted by agent:auto").
- OFF (default): create_proposal stops at pending (today's behavior, unchanged).
**Why this shape:** one chokepoint, reuses all apply-handlers + fail-closed + audit, trivially
reversible (flip setting), and the human REST/P1 path is untouched. The write server doesn't change
at all — it still only calls create_proposal. **How to change:** flip `wikiAgentAutonomous`.

**D-W4d.2 — only AGENT-actor auto-applies.** Auto-accept fires only when the proposal's actor starts
with "agent" / "mcp:" (an agent-originated write). A human-created proposal via REST/P1 NEVER
auto-accepts (the human queue is deliberate). Guards against the toggle accidentally auto-applying
the human's own drafts.

**D-W4d.3 — fail-soft on the auto-accept.** If the auto-apply raises (e.g. bad target), the proposal
stays PENDING (fail-closed on the write — same as manual accept) and create_proposal still returns
the pending proposal with a warning. The agent's propose call doesn't hard-error; the write just
didn't auto-land and waits in the queue. ([[fail-closed-write-fail-soft-addon]].)

## Settings
- NEW field `wikiAgentAutonomous: bool = False` in settings schema (AppConfig + AppConfigPatch) +
  persisted in md_store settings/config.md (same path as automationEnabled etc.).
- Read it in create_proposal via the settings service (get_config()), NOT core.config (this is a
  runtime-mutable user setting, not a static env setting).

## Scope
IN:
- settings schema field + persistence + GET/PATCH expose it (backend).
- create_proposal auto-apply branch (D-W4d.1/2/3) (backend).
- FE: a toggle in the Settings screen ("Agent tự động ghi vào vault" / "Autonomous agent writes")
  with a clear WARNING copy ("bỏ qua hàng đợi duyệt — agent ghi thẳng; mặc định TẮT để an toàn").
- FE: P1 Proposal Queue shows auto-accepted proposals in the "accepted" filter with decidedBy
  "agent:auto" so the human can audit what the agent wrote autonomously.
OUT: per-kind allowlist (user chose full toggle, not per-kind) · auto-revert window · the other
feature gaps (synthesize/consolidation — separate sprints).

## Gates / Defensive (E2E — the user explicitly asked for edge-case + E2E testing)
- **toggle OFF (default)**: propose via MCP → pending, vault unchanged (today's behavior — regression-proof).
- **toggle ON**: propose_note via MCP → note lands in vault IMMEDIATELY (status=accepted, decidedBy=agent:auto), NO human step. The full autonomous path.
- **toggle ON + human-created proposal** (actor=human via REST): does NOT auto-apply (D-W4d.2) — stays pending.
- **toggle ON + bad target** (propose_edit note 9999): auto-apply fails-closed → proposal stays pending + warning, no 500 (D-W4d.3).
- **toggle flip live**: ON→write lands; PATCH OFF→next propose is pending again (no restart needed — read per-call).
- audit: an auto-applied write has BOTH the propose audit row AND the accept audit row (actor=agent:auto).
- E2E via Chrome: flip the Settings toggle in the UI → (MCP propose) → see it auto-applied in P1 accepted list + the note in /wiki.
- pytest + vitest green (≥ baseline+new), mypy/tsc clean, no dup-name.
