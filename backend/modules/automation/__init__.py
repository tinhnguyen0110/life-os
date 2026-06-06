"""modules/automation — Automation feature module (Sprint 10A, SPEC §S13).

The "active" layer: rule-based routines (NO AI — CLAUDE.md hard rule) that run on
a timer or on-demand and LOG to run_log. This module manages the routine catalog
(scheduler-registered + event-driven), exposes GET /routines (registered + run_log
stats), PATCH /routines/{id} (toggle, persisted), POST /routines/{id}/run (on-demand).
Also home of the `record_routine_run` wrapper + the morning-pull routine.
"""
