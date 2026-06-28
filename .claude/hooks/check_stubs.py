#!/usr/bin/env python3
"""PostToolUse: bounce bare TODO/FIXME/HACK, require STUB(D-xxx) + DEBT.md entry."""
import sys, json, re
from pathlib import Path

BARE = re.compile(r'(?<!\()\b(TODO|FIXME|HACK)\b(?!\s*\(D-\d+\))', re.IGNORECASE)

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    inp = data.get("tool_input", {})
    file_path = inp.get("file_path", "")
    content = inp.get("new_string") or inp.get("content", "")

    if not content or not file_path.endswith(".py"):
        sys.exit(0)

    matches = BARE.findall(content)
    if matches:
        print(json.dumps({
            "decision": "block",
            "reason": (
                f"Bare {matches[0]} in {file_path}.\n"
                "Convert to: STUB(D-NNN): <reason>  (use next D-number in DEBT.md)\n"
                "Then add a row to DEBT.md before continuing."
            )
        }))
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
