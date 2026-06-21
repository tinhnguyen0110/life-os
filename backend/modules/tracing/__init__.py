"""modules/tracing/ — daily habit/activity tracing (the G-HABIT module, DAILY-TRACING-P1 #65).

Track day-to-day habits (run/code/study/work): the user LOGS raw sessions, the service DERIVES all
metrics (today/streak/week/12w-history/12w-heatmap/score) server-side. Raw-data-first — store the
raw sessions, never a pre-computed metric. DISTINCT from reminders (alarms) + journal (decisions).
Single-user, no-auth. The registry auto-discovers ``MODULE`` from router.py.
"""
