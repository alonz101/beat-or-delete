#!/usr/bin/env python3
"""PreToolUse: block writes to test files during implement phase."""
import sys, json, fnmatch
from pathlib import Path

def main():
    phase_file = Path(".claude/state/phase")
    if not phase_file.exists() or phase_file.read_text().strip() != "implement":
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    try:
        config = json.loads(Path(".claude/hooks/hooks.config.json").read_text())
    except Exception:
        config = {}

    test_globs = config.get("test_globs", ["tests/**/*.py"])
    p = Path(file_path)

    for pattern in test_globs:
        if p.match(pattern) or fnmatch.fnmatch(str(p), pattern):
            print(json.dumps({
                "decision": "block",
                "reason": (
                    f"PHASE=implement — test files are frozen.\n"
                    f"File: {file_path}\n"
                    "If the test is genuinely wrong, stop and escalate to the human. Never edit around it."
                )
            }))
            sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
