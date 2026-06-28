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

    # Skip during TDD RED/GREEN phase — tests are intentionally failing.
    # Use git --git-common-dir to find the real project root even from a worktree,
    # since __file__ resolves to the worktree's copy of this hook.
    try:
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, cwd=str(Path(__file__).parent),
        ).stdout.strip()
        project_root = (Path(__file__).parent / git_common).resolve().parent
        phase_file = project_root / ".claude" / "state" / "phase"
    except Exception:
        phase_file = Path(__file__).parent.parent / "state" / "phase"
    if phase_file.exists() and phase_file.read_text().strip() == "implement":
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
