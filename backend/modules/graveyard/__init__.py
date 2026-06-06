"""modules/graveyard — Graveyard ("Nghĩa địa") feature module (Sprint 8, SPEC §S4).

The honest-mirror of ABANDONED projects + their patterns. Reads the abandoned set
from the projects store (abandon-orthogonal-to-health: membership = the `abandoned`
flag, NEVER health=dead). Aggregates peak/reasons/reached-vs-before-user/lessons.
GET /graveyard. The registry discovers MODULE from router.py.
"""
