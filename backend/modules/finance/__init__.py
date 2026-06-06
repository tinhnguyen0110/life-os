"""modules/finance — Finance feature module (Sprint 4, SPEC §S5/§S6).

Holdings (md_store) priced via the market module; channel allocations + drift,
unrealized P&L, and ladder-state all derived server-side and self-describing
(each derived field carries its inputs so an external agent can verify it).
The registry discovers MODULE from router.py (T2).
"""
