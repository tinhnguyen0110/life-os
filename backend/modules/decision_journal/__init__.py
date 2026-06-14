"""modules/decision_journal — Decision Journal + Calibration (Sprint W7 A2).

A GENERAL decision learning-loop (the "self-improve" thesis applied to the user):
log a decision + a probabilistic prediction → on resolve, measure how calibrated
the user's confidence was (Brier + confidence-bands on the thesis/outcome axis) →
detect repeated bias by domain (rule-based, no LLM).

SEPARATE from the trade-shaped ``modules/journal/`` (BUY/SELL/asset/pnl) — this is
for GENERAL decisions (investment AND project), per the W7 kickoff decision. It
REUSES journal's calibration-band MATH as reference, ADDS Brier + domain bias-cluster.

The registry discovers ``MODULE`` from ``router.py`` — adding this folder is the
only wiring (no edit to core/ or main.py).
"""
