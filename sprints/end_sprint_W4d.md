# Sprint W4d — Agent Autonomy Toggle · END (reverses D8, USER-ORDERED)

**Status:** ✅ BE + FE implemented + verified live (Rule#0, full E2E all 4 cases). **Commit:** (pending).

## What shipped
A global Settings toggle `wikiAgentAutonomous` (default **OFF**). OFF = proposals-only (north-star
unchanged). ON = agent writes apply DIRECTLY to the vault (bypass the P1 human-ratify queue), per the
user's direct order this session. Built so the north-star is the safe default and even auto-writes
stay fully audited + visibly tagged.

⚠️ This REVERSES the locked D8 / north-star "AI proposes, human ratifies." Done ONLY because the USER
explicitly ordered it (surfaced via [[implementer-flag-before-reversing-decision]] + user-confirmed).

### Backend (proposals_service.py + settings)
- `wikiAgentAutonomous: bool = False` in settings schema (AppConfig + AppConfigPatch), persisted in
  md_store settings/config.md, on GET/PATCH.
- create_proposal chokepoint (D-W4d.1): after recording the pending proposal, if the setting is ON
  AND actor is an agent (startswith agent/mcp:) → auto-call accept_proposal(decided_by="agent:auto").
  All writes still flow through the one chokepoint + the existing single-writer/apply-handlers.
- D-W4d.2 agent-actor only (human proposals never auto-apply). D-W4d.3 fail-soft (auto-apply raise →
  proposal stays pending + warning, no hard-error, defaults OFF on a settings-read failure).

### Frontend (settings + P1)
- Settings AutonomyPanel toggle with state-aware DANGER copy (OFF safe / ON red banner explaining it
  reverses the north-star + that auto-writes show in P1 as agent:auto). Save-on-flip, fail-closed.
- P1 accepted cards with decidedBy="agent:auto" get a distinct "◇ agent:auto" badge (vs "bởi human")
  so a human auditing the accepted filter can tell autonomous writes apart.

## Verified LIVE (team-lead, Rule#0 — full E2E, the user explicitly asked for it)
- BE pytest 920 (+7 autonomy), FE vitest 503 (+6), mypy/tsc clean, no dup-name.
- **E2E all 4 cases live on container:**
  1. OFF (default): agent propose → pending, vault unchanged (regression-safe).
  2. ON: agent propose_note → AUTO-APPLIED (status accepted, decidedBy=agent:auto, appliedNoteId set),
     vault 0→1, NO human step.
  3. ON + human-actor proposal → does NOT auto-apply (stays pending) — the D-W4d.2 guard.
  4. ON + bad target (note_edit 99999) → fail-soft: stays pending, HTTP 200, no 500 — D-W4d.3.
  + toggle flip live (read per-call, no restart). FE Chrome E2E (toggle PATCH persists, P1 agent:auto
    badge) proven by frontend + matches.

## Assumptions (user-review)
1. **Full global toggle** (user's chosen shape), not per-kind allowlist — one switch, all kinds.
2. **agent:auto is the decidedBy** for autonomous writes (distinct from "human") — audit/P1 distinction.
3. **Default OFF + fail-safe-OFF**: a settings-read error defaults to proposals-only (never silently
   autonomous). The dangerous mode is never the fallback.
4. Auto-writes keep BOTH audit rows (propose + accept) — full forensic trail even when autonomous.

## North-star note
The proposals-only trust loop remains the DEFAULT and is fully intact when the toggle is OFF. The
toggle is an opt-in escape hatch the user explicitly wanted; it does not weaken the default posture.
