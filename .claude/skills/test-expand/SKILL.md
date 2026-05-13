---
name: test-expand
description: Expand test coverage for rootlens. Finds untested branches and edge cases, writes new pytest tests. Use when coverage is low or a new feature needs tests.
argument-hint: [module-name]
allowed-tools: Bash(python3 *), Bash(grep *), Bash(find *), Read, Glob, Edit, Write
---

# Test Expand

## Context

- Current coverage: !`python3 -m pytest tests/ --cov=rootlens --cov-report=term-missing -q 2>&1 | tail -20`
- Test files: !`find tests -name "test_*.py" | sort`

## Instructions

Target module: `$ARGUMENTS` (if empty, target the module with lowest coverage)

1. Read the target module source to identify all code paths
2. Check existing tests to find gaps
3. Write new test cases covering:
   - Untested branches (especially error paths)
   - Edge cases (empty input, None, boundary values)
   - Integration between components
4. Add tests to the appropriate existing test file (don't create a new file unless the module has none)
5. Run tests to confirm they pass
6. Report coverage improvement

Follow existing test style in the project (class-based, pytest, no mocks unless necessary).
