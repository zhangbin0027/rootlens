---
name: review
description: Run 3-stage review (spec → quality → compliance) on current changes. Use when user asks to review, run review, or check before pushing.
allowed-tools: Bash(git *), Bash(python3 *), Bash(grep *), Read, Glob
---

# 3-Stage Review

## Context

- Changed files: !`git diff --name-only HEAD`
- Diff summary: !`git diff HEAD --stat`

## Instructions

Run the 3 review stages in sequence. Stop and report if any stage fails.

### Stage 1 — Spec Review
Check: does the change match what was asked? Is anything missing or out of scope?
- Read the changed files
- Verify logic correctness
- Flag any missing edge cases

### Stage 2 — Quality Review
Check: code quality, test coverage, no dead code introduced.
- Run tests: !`python3 -m pytest tests/ -q --tb=short 2>&1 | tail -10`
- Check benchmark: !`python3 benchmarks/guard.py 2>&1`
- Flag any test failures or accuracy regressions

### Stage 3 — Compliance Review
Scan for sensitive information in changed files:
- Credentials: `ghp_`, `AKIA`, `password=`, `token=`, `secret=`
- Internal system names: `amazon.com`, `gerrit`, `labcollab`, `kbits`, `midway`
- Personal identifiers: `@amazon.com`, `/home/zhangbn/`, `/local/home/`
- Local machine paths in source files

## Output Format

Report as:
```
STAGE 1 (Spec):     PASSED / FAILED — <reason>
STAGE 2 (Quality):  PASSED / FAILED — <reason>  
STAGE 3 (Compliance): PASSED / FAILED — <reason>

Overall: APPROVED / BLOCKED
```

If APPROVED, suggest the commit command to run next.
If BLOCKED, suggest using `/rewind` (Esc+Esc) to restore last good state, or `/plan` to re-approach the change.
