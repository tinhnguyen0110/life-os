"""modules/code_insight/ — on-demand repo read for a cold session-agent (REPO-MEMORY-P1, #64).

``code_insight`` is an ON-DEMAND (never-indexed) fresh read of a local repo: top-level structure +
README excerpt + recent git-log + detected stack + asOf. So a session-agent entering repo X gets
instant "what's here NOW" context — always-current (an index goes stale; on-demand can't). Reuses
the dev_activity :ro mounts (the repo roots) + the projects read-only git whitelist (read-only HARD
invariant — NO mutating git). P2 (later) = the durable Repos/<name> wiki memory note.
"""
