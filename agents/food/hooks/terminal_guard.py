#!/usr/bin/env python3
"""Pre-tool hook for the food agent: the terminal may run only the `health` CLI.

Hermes sends the tool call as JSON on stdin and reads a decision from stdout.
Anything other than a plain `health ...` command is blocked, so the agent cannot
reach the API directly (curl, python, a URL or a port), pipe or redirect
output, or chain commands. The hook is registered with fail_closed, so an error
here blocks the call rather than letting it through.
"""

import json
import re
import sys

ALLOWED = re.compile(r"^(~/\.local/bin/health|health)(\s|$)")
FORBIDDEN = re.compile(
    r"[;&|`<>\n]|\$|--url|HEALTH_API_URL|curl|wget|python|\bnc\b|/api/|8000|/dev/"
)
ALLOW = {}
BLOCK = {
    "decision": "block",
    "reason": "The food agent may only run the health command, with plain arguments.",
}


def decide(payload: dict) -> dict:
    if payload.get("tool_name") != "terminal":
        return ALLOW
    command = str((payload.get("tool_input") or {}).get("command") or "").strip()
    if ALLOWED.match(command) and not FORBIDDEN.search(command):
        return ALLOW
    return BLOCK


if __name__ == "__main__":
    print(json.dumps(decide(json.load(sys.stdin))))
