#!/usr/bin/env python3
"""Notify user via Discord. Usage: python .claude/process/notify.py "message"
Reads webhook from .env key `discord=`. No webhook / no arg → exit 0 silently (never blocks the team)."""
import os, sys, urllib.request, json, pathlib


def webhook() -> str:
    env = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.strip().startswith("discord="):
            return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    msg = " ".join(sys.argv[1:]).strip()
    url = webhook()
    if not msg or not url:
        return 0  # nothing to send / not configured — skip silently
    req = urllib.request.Request(
        url, data=json.dumps({"content": msg}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"notify skipped: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
