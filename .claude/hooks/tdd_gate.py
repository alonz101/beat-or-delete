#!/usr/bin/env python3
"""Stop hook: block if tests are red after source changes."""
import sys, json, subprocess, os
from pathlib import Path

def main():
    # Never block twice in a row — lets a stuck session stop and report
    if os.environ.get("stop_hook_active"):
        sys.exit(0)

    # Only enforce when tests directory exists
    if not Path("tests").exists():
        sys.exit(0)

    try:
        config = json.loads(Path(".claude/hooks/hooks.config.json").read_text())
    except Exception:
        sys.exit(0)

    cmd = config.get("test_command", "python -m pytest tests/ -x -q 2>&1")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-3000:]
        print(json.dumps({
            "decision": "block",
            "reason": f"Tests are red — fix before stopping.\n\n{output}"
        }))
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
