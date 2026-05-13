#!/usr/bin/env python3
"""Benchmark guard: run evaluate.py and warn if accuracy drops below baseline.

Exit codes:
  0 — all thresholds met
  1 — accuracy regression detected (prints REGRESSION warning)
"""
import subprocess
import sys
import re

# Thresholds — update these when you intentionally improve the baseline
HOLDOUT_ACCURACY_MIN = 97.0   # % — warn if holdout accuracy drops below this
FALSE_BLAME_MAX = 5.0          # % — warn if false blame rate exceeds this

def main():
    result = subprocess.run(
        [sys.executable, "benchmarks/evaluate.py"],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    # Print summary lines
    for line in output.splitlines():
        if re.search(r"Accuracy|False Blame|ZERO|TARGET|mismatches", line):
            print(line)

    # Parse scores
    holdout_match = re.search(r"Accuracy\s+([\d.]+)%\s+([\d.]+)%", output)
    false_blame_match = re.search(r"False Blame Rate\s+([\d.]+)%", output)

    holdout = float(holdout_match.group(1)) if holdout_match else None
    false_blame = float(false_blame_match.group(1)) if false_blame_match else None

    regressions = []
    if holdout is not None and holdout < HOLDOUT_ACCURACY_MIN:
        regressions.append(
            f"HOLDOUT ACCURACY {holdout:.1f}% < {HOLDOUT_ACCURACY_MIN:.1f}% threshold"
        )
    if false_blame is not None and false_blame > FALSE_BLAME_MAX:
        regressions.append(
            f"FALSE BLAME RATE {false_blame:.1f}% > {FALSE_BLAME_MAX:.1f}% threshold"
        )

    if regressions:
        print()
        print("⚠️  REGRESSION DETECTED — consider /rewind before committing:")
        for r in regressions:
            print(f"   ❌ {r}")
        print("   Run: /rewind  (Esc+Esc) to restore last good state")
        sys.exit(1)
    else:
        print("✅ Benchmark thresholds met")
        sys.exit(0)


if __name__ == "__main__":
    main()
