"""modules/macro — Macro economic context module (MACRO-1).

Turns the agent from "knows coin prices" into "understands the backdrop": captures
real-time macro indicators (Fed funds rate / US CPI / DXY dollar index) → stores a
time-series → serves them so an agent reading the portfolio has context.

Pattern mirrors market: capture (reader, FRED with mock fail-open) → store (own
``macro_history`` table on the shared db) → read (service overview/history). Mounts at
``/macro`` via the registry (``MODULE`` in router.py — auto-discovered, no core/main
edit). NEUTRAL by contract: the overview reports the latest value + a DESCRIPTIVE trend
(up/down vs prior), never a forecast. A daily poll routine refreshes the series.

Source: FRED (free, key-optional). No key / fetch failure → honest deterministic mock
tagged source='mock' + a warning — never blocks (mock-first).
"""
