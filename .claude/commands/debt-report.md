# /debt-report

Produces a summary of all tracked debt.

## Steps
1. Read DEBT.md
2. Read all source files and grep for `STUB(D-NNN)` references
3. Cross-check: every STUB in code has a row in DEBT.md (flag orphans)
4. Report:
   - Open debt items (with file locations)
   - Any orphan STUBs not in DEBT.md
   - Paid items (for reference)
   - Suggested next paydown (highest severity open item)
