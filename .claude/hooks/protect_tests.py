#!/usr/bin/env python3
"""PreToolUse: block writes to test files during implement phase."""
import sys, json, fnmatch, subprocess
from pathlib import Path

# Resolve project root from the script's own location (worktree-safe), NOT cwd —
# the hook may run with cwd set to any subdir (e.g. DJAnalyzer/), so cwd-relative
# paths silently fail-open. git-common-dir points at the main repo's .git even from
# a linked worktree, matching tdd_gate.py.
def _project_root():
    try:
        common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, cwd=str(Path(__file__).parent),
        ).stdout.strip()
        if common:
            return (Path(__file__).parent / common).resolve().parent
    except Exception:
        pass
    return Path(__file__).resolve().parents[2]

_ROOT = _project_root()

def main():
    phase_file = _ROOT / ".claude" / "state" / "phase"
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
        config = json.loads((_ROOT / ".claude" / "hooks" / "hooks.config.json").read_text())
    except Exception:
        config = {}

    test_globs = config.get("test_globs", ["tests/**/*.py"])
    p = Path(file_path)
    # Normalize to a repo-relative path so globs match regardless of whether the
    # harness sends an absolute or relative file_path.
    try:
        rel = p.resolve().relative_to(_ROOT)
    except Exception:
        rel = p

    # Intent: a .py file anywhere under a `tests/` directory is frozen. This is
    # robust across Python versions where PurePath ** semantics differ.
    is_test = rel.suffix == ".py" and "tests" in rel.parts
    glob_hit = any(
        rel.match(pattern)
        or fnmatch.fnmatch(str(rel), pattern)
        or fnmatch.fnmatch(rel.name, pattern)
        for pattern in test_globs
    )

    if is_test or glob_hit:
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
