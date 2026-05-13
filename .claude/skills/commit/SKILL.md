---
name: commit
description: Create a git commit for rootlens with benchmark validation and conventional commit format. Use when user asks to commit changes.
argument-hint: [message]
allowed-tools: Bash(git *), Read
---

# Commit

## Context

- Branch: !`git branch --show-current`
- Status: !`git status --short`
- Diff: !`git diff HEAD --stat`
- Recent commits: !`git log --oneline -5`

## Instructions

1. Check that tests pass: !`python3 -m pytest tests/ -q --tb=no 2>&1 | tail -3`
2. Stage relevant files (not .claude/settings.json, not *.pyc, not __pycache__)
3. Write commit message in conventional commits format:
   - `feat:` new feature
   - `fix:` bug fix
   - `test:` adding tests
   - `refactor:` code change without feature/fix
   - `docs:` documentation only
   - `chore:` maintenance
4. Include `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer

If `$ARGUMENTS` is provided, use it as the commit message subject.

Never commit: `.claude/settings.json`, `*.pyc`, `__pycache__/`, `.env`
