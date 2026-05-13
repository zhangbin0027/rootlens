#!/usr/bin/env python3
"""
demo.py — RootLens demonstration

Shows three scenarios:
1. Infrastructure failure (CLOSE) — disk full
2. Compilation error with file match (TRUE_REJECT)
3. Repo sync failure before checkout (CLOSE)

Usage: python examples/demo.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rootlens import analyze


def main():
    print("=" * 60)
    print("  RootLens — Causal Decision Engine Demo")
    print("=" * 60)

    logs_dir = Path(__file__).parent / "logs"

    # Scenario 1: Infrastructure failure
    print("\n[Scenario 1] Infrastructure Failure — Disk Full")
    print("-" * 50)
    log = (logs_dir / "infra_failure.log").read_text()
    result = analyze(
        build_log=log,
        changed_files=["src/core/main.cpp"],
    )
    _print_result(result)

    # Scenario 2: Compilation error with file match
    print("\n[Scenario 2] Compilation Error — File Intersection Match")
    print("-" * 50)
    log = (logs_dir / "compile_error.log").read_text()
    result = analyze(
        build_log=log,
        changed_files=["src/auth/login_handler.cpp"],
    )
    _print_result(result)

    # Scenario 3: Repo sync failure (pre-apply)
    print("\n[Scenario 3] Repo Sync Failure — Pre-Apply")
    print("-" * 50)
    log = (logs_dir / "repo_sync_failure.log").read_text()
    result = analyze(
        build_log=log,
        changed_files=["src/feature/new_api.py"],
    )
    _print_result(result)

    # Scenario 4: Ambiguous failure (ESCALATE)
    print("\n[Scenario 4] Ambiguous Failure — Test Timeout (ESCALATE)")
    print("-" * 50)
    log = (logs_dir / "ambiguous_failure.log").read_text()
    result = analyze(
        build_log=log,
        changed_files=["src/com/example/NetworkClient.java"],
    )
    _print_result(result)

    print("\n" + "=" * 60)
    print("  All scenarios completed.")
    print("=" * 60)


def _print_result(r):
    print(f"  decision:       {r.decision}")
    print(f"  reason:         {r.reason}")
    print(f"  confidence:     {r.confidence}")
    if r.proof:
        print(f"  proof:          {r.proof}")
    if r.rule_name:
        print(f"  rule_name:      {r.rule_name}")
    if r.matched_signal:
        print(f"  matched_signal: {r.matched_signal}")


if __name__ == "__main__":
    main()
