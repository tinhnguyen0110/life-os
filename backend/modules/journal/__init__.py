"""modules/journal — Investment Journal feature module (Sprint 9, SPEC §S7).

Turns investment DECISIONS into learning data (calibration). A WRITE module via
md_store (one git commit per entry, like Notes). Self-contained store — pnl is
user-entered (no auto price tie-back this sprint). The registry discovers MODULE
from router.py. GET /journal (list + stats).
"""
