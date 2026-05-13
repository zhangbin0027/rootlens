---
name: optimize
description: Analyze rootlens code for performance issues and suggest optimizations. Use when asked to optimize, improve performance, or profile.
argument-hint: [file-or-module]
allowed-tools: Bash(python3 *), Bash(grep *), Read, Glob
---

# Optimize

## Context

- Target: `$ARGUMENTS`
- Benchmark baseline: !`python3 benchmarks/evaluate.py 2>&1 | grep -E 'Accuracy|False Blame|ZERO|TARGET|took'`

## Instructions

Analyze `$ARGUMENTS` (or all of `src/rootlens/` if not specified) for:

1. *Performance bottlenecks* — O(n²) loops, repeated regex compilation, unnecessary I/O
2. *Memory usage* — large objects held in memory, missing `lru_cache` opportunities
3. *Redundant work* — same computation repeated across calls
4. *Classifier hot path* — `classify()` is called per log line; any savings there compound

For each issue found:
- Severity: Critical / High / Medium / Low
- Location: file:line
- Explanation of the problem
- Proposed fix with code snippet

After analysis, run benchmark to establish baseline, then estimate expected improvement.
