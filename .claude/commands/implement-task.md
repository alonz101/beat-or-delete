# /implement-task

Usage: `/implement-task <PLAN.md> <T-1> [T-2 T-3 ...]`

## What this does
Runs the full RED → GREEN → REVIEW cycle for one or more tasks.

Tasks in the same wave with disjoint file ownership run in parallel (up to 3 subagents).
Tasks in different waves must be sequential.

## Steps per task

1. **Mark IN_PROGRESS** in TASKS.md
2. **Set phase**: `echo "implement" > .claude/state/phase`
3. **RED** — invoke `test-writer` subagent with the task's test plan from PLAN.md
   - Confirm tests fail before proceeding
   - Commit: `test(T-x): red tests for <title>`
4. **GREEN** — invoke `implementor` subagent
   - Confirm all tests pass
5. **REVIEW** — invoke `code-reviewer` subagent
   - If BLOCK: implementor fixes, re-review (track rounds in TASKS.md)
   - If APPROVE: commit `feat(T-x): <title>  Reviewed-by: code-reviewer`
6. **Clear phase**: `rm .claude/state/phase`
7. **Mark DONE** in TASKS.md

## Abort / stuck
If a task gets stuck (test truly wrong, missing ownership): clear phase, mark BLOCKED(reason) in TASKS.md, report to human.
