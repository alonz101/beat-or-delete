# /plan-feature

Usage: `/plan-feature docs/specs/<feature>/SPEC.md`

## What this does
1. Reads the SPEC at the given path
2. Delegates to the `planner` subagent to produce a PLAN.md alongside the SPEC
3. Presents the plan to you with any open questions
4. On your approval, creates a git worktree at `.claude/worktrees/<slug>` on branch `feat/<slug>`

## Steps

Read the SPEC file. Then invoke the planner agent with:
- The full SPEC content
- The current source structure (read `core/` directory listing)
- Instruction to write PLAN.md next to the SPEC

Present the plan. Ask the human to resolve any open questions. Do not create the worktree until the human approves the plan.

On approval:
```bash
git worktree add .claude/worktrees/<slug> -b feat/<slug>
```

Then update TASKS.md with the new feature's task table (all tasks TODO).
