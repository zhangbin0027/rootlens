#!/usr/bin/env python3
"""
evaluate.py — Benchmark evaluation for RootLens

Compares RootLens against a naive baseline (regex-only, no causal reasoning).
Key metric: false_blame_rate MUST be 0%.

Usage: python benchmarks/evaluate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine.pipeline import analyze


def naive_classify(log, changed_files):
    """Naive baseline: regex-only, no causal reasoning."""
    infra_kw = ["No space left", "Connection refused", "offline",
                "Could not read from remote", "upload failed"]
    compile_kw = ["error:", "cannot find symbol", "undefined reference",
                  "Unresolved reference"]
    for kw in infra_kw:
        if kw in log:
            return "CLOSE"
    for kw in compile_kw:
        if kw in log:
            return "TRUE_REJECT"
    return "ESCALATE"


def main():
    dataset_path = Path(__file__).parent / "dataset.json"
    with open(dataset_path) as f:
        cases = json.load(f)

    rootlens_correct = 0
    baseline_correct = 0
    rootlens_false_blame = 0
    baseline_false_blame = 0
    details = []

    for case in cases:
        log = case["log"]
        files = case.get("changed_files", [])
        label = case["label"]
        # change_count = number of CRs/PRs in the CI batch, NOT number of files.
        # Each benchmark case represents a single CR unless explicitly marked.
        count = case.get("change_count", 1)

        # RootLens
        result = analyze(build_log=log, changed_files=files, change_count=count)
        rl_pred = result.decision
        rl_ok = rl_pred == label

        # Baseline
        bl_pred = naive_classify(log, files)
        bl_ok = bl_pred == label

        # False blame: predicted TRUE_REJECT when actual != TRUE_REJECT
        rl_fb = (rl_pred == "TRUE_REJECT" and label != "TRUE_REJECT")
        bl_fb = (bl_pred == "TRUE_REJECT" and label != "TRUE_REJECT")

        if rl_ok:
            rootlens_correct += 1
        if bl_ok:
            baseline_correct += 1
        if rl_fb:
            rootlens_false_blame += 1
        if bl_fb:
            baseline_false_blame += 1

        details.append({
            "id": case["id"],
            "label": label,
            "rootlens": rl_pred,
            "baseline": bl_pred,
            "rootlens_correct": rl_ok,
            "baseline_correct": bl_ok,
        })

    total = len(cases)
    print("=" * 60)
    print("  RootLens Benchmark Results")
    print("=" * 60)
    print(f"\n  Dataset: {total} cases")
    print(f"  CLOSE: {sum(1 for c in cases if c['label']=='CLOSE')}")
    print(f"  TRUE_REJECT: {sum(1 for c in cases if c['label']=='TRUE_REJECT')}")
    print(f"  ESCALATE: {sum(1 for c in cases if c['label']=='ESCALATE')}")
    print()
    print(f"  {'Metric':<25} {'RootLens':>10} {'Baseline':>10}")
    print(f"  {'-'*25} {'-'*10} {'-'*10}")
    print(f"  {'Accuracy':<25} {rootlens_correct/total*100:>9.1f}% {baseline_correct/total*100:>9.1f}%")
    print(f"  {'False Blame Rate':<25} {rootlens_false_blame/total*100:>9.1f}% {baseline_false_blame/total*100:>9.1f}%")
    print(f"  {'Correct':<25} {rootlens_correct:>10} {baseline_correct:>10}")
    print()

    # Show mismatches
    mismatches = [d for d in details if not d["rootlens_correct"]]
    if mismatches:
        print(f"  RootLens mismatches ({len(mismatches)}):")
        for m in mismatches:
            print(f"    {m['id']}: expected={m['label']} got={m['rootlens']}")
    else:
        print("  ✓ RootLens: ZERO mismatches")

    bl_mismatches = [d for d in details if not d["baseline_correct"]]
    if bl_mismatches:
        print(f"\n  Baseline mismatches ({len(bl_mismatches)}):")
        for m in bl_mismatches[:5]:
            print(f"    {m['id']}: expected={m['label']} got={m['baseline']}")
        if len(bl_mismatches) > 5:
            print(f"    ... and {len(bl_mismatches)-5} more")

    print()
    if rootlens_false_blame == 0:
        print("  ✓ FALSE BLAME RATE = 0% (target met)")
    else:
        print(f"  ✗ FALSE BLAME RATE = {rootlens_false_blame/total*100:.1f}% (TARGET MISSED)")
    print("=" * 60)


if __name__ == "__main__":
    main()
