# RootLens — Causal Decision Engine for CI Failure Triage

> **This is not a log analyzer. It is a decision system based on causal reasoning.**

Most CI systems answer: *"What error happened?"*
RootLens answers: **"Can this failure be caused by the code change?"**

- If provably **NO** → `CLOSE` (zero blame)
- If provably **YES** → `TRUE_REJECT` (100% blame with evidence)
- If unknown → `ESCALATE` (refuse to guess)

## The Problem

30–40% of CI failures are infrastructure issues (disk full, network timeout, node crash) that get **misattributed to code changes**. This causes:

- Developers waste time investigating failures they didn't cause
- Real bugs get delayed because triage is overwhelmed with false signals
- Trust in the CI system erodes

RootLens eliminates false blame through **deterministic causal reasoning**.

## Impact (Internal Validation)

Validated on an internal production CI system (dataset not publicly available):

| Metric                     | Value                            |
| -------------------------- | -------------------------------- |
| Internal dataset           | 159 labeled CI failure cases     |
| Decision precision         | ~100% (deterministic subset)     |
| Infrastructure false-blame | reduced from 30–40% to **0%**    |
| Auto-resolution coverage   | 60–70% of cases                  |
| Remainder                  | Safely escalated to human review |

Reproducible benchmark (included): 41 cases, 100% accuracy, 0% false blame. See `benchmarks/`.

## Architecture

```
                ┌─────────────┐
                │  Build Log  │
                └──────┬──────┘
                       │
                ┌──────▼──────┐
                │  Q1: State  │──── MERGED/ABANDONED → CLOSE
                └──────┬──────┘
                       │ open
                ┌──────▼──────┐
                │ Q1.5: Infra │──── causal impossibility → CLOSE + proof
                │  (10 rules) │
                └──────┬──────┘
                       │ not infra
                ┌──────▼──────┐
                │ Q2: Compile │──── error ∩ changed_files → TRUE_REJECT
                │ + file match│
                └──────┬──────┘
                       │ no match
                ┌──────▼──────┐
                │  ESCALATE   │──── "I don't know"
                └─────────────┘
```

### Three Layers

| Layer    | Purpose                                  | Output                    |
| -------- | ---------------------------------------- | ------------------------- |
| **Q1**   | Change state filter                      | CLOSE if merged/abandoned |
| **Q1.5** | Causal negation (proof of impossibility) | CLOSE + causal_proof      |
| **Q2**   | Causal confirmation (file intersection)  | TRUE_REJECT with evidence |

### Why Three Classes, Not Two?

Binary (blame/no-blame) forces guessing when evidence is insufficient:
- False blame → developer wastes time on infra issues
- False acquittal → real bugs escape review

`ESCALATE` is **not failure** — it is honest admission that causality cannot be established.

## Q1.5: The Core Innovation

Q1.5 is NOT a pattern matcher. Each rule must prove:

> "No plausible code change can be on the causal chain for this failure."

Each rule contains:
- `pattern` — what to match
- `counterexample` — why no code change can trigger this
- `causal_proof` — formal reasoning for the decision

See [docs/q1_5_rules.md](docs/q1_5_rules.md) for all 10 rules.

## Quick Start

```bash
pip install rootlens
python examples/demo.py
```

Or from source:

```bash
git clone https://github.com/zhangbin0027/rootlens.git
cd rootlens
pip install -e .
python examples/demo.py
```

### Demo Output

```
[Scenario 1] Infrastructure Failure — Disk Full
  decision:       CLOSE
  reason:         Infrastructure failure: DISK_FULL
  confidence:     1.0
  proof:          Disk capacity is a build node resource constraint...
  rule_name:      DISK_FULL
  matched_signal: No space left on device

[Scenario 2] Compilation Error — File Intersection Match
  decision:       TRUE_REJECT
  reason:         Compilation error in changed file: src/auth/login_handler.cpp
  confidence:     1.0
  rule_name:      Q2_SMOKING_GUN
  matched_signal: error: cannot find symbol

[Scenario 3] Repo Sync Failure — Pre-Apply
  decision:       CLOSE
  reason:         Infrastructure failure: PRE_APPLY_FAILURE
  confidence:     1.0
  proof:          Error in repo initialization phase, before code checkout...
  rule_name:      PRE_APPLY_FAILURE
  matched_signal: MANIFEST_INIT_ERROR
```

## Benchmark

```bash
python benchmarks/evaluate.py
```

Results (41 cases, adversarial included):

| Metric           | RootLens | Naive Baseline |
| ---------------- | -------- | -------------- |
| Accuracy         | **100%** | ~66%           |
| False Blame Rate | **0%**   | ~15%           |

## Project Structure

```
rootlens/
├── README.md
├── requirements.txt
├── docs/
│   ├── decision-model.md
│   └── q1_5_rules.md
├── src/
│   └── engine/
│       ├── models.py      # BuildContext, DecisionResult, RuleVerdict, ErrorSignal
│       ├── q1_5.py        # 10 hardcoded causal rules (Python, NOT YAML)
│       ├── classifier.py  # YAML pattern loader → ErrorSignal (no decisions)
│       ├── decision.py    # Q1→Q1.5→Q2 enforced order
│       └── pipeline.py    # analyze() public API
├── configs/
│   └── error_patterns.yaml
├── examples/
│   ├── logs/
│   │   ├── compile_error.log
│   │   ├── infra_failure.log
│   │   └── repo_sync_failure.log
│   └── demo.py
└── benchmarks/
    ├── dataset.json       # 41 cases with adversarial samples
    └── evaluate.py        # baseline comparison
```

## API Usage

```python
from rootlens import analyze

result = analyze(
    build_log="error: No space left on device",
    changed_files=["src/main.cpp"],
)

print(result.decision)    # "CLOSE"
print(result.confidence)  # 1.0
print(result.proof)       # "Disk capacity is a build node resource..."
```

### Parameters

| Parameter       | Required | Description                                     |
| --------------- | -------- | ----------------------------------------------- |
| `build_log`     | Yes      | Raw build log text (must be non-empty string)   |
| `changed_files` | No       | Files modified by the change                    |
| `change_status` | No       | "open" (default), "merged", or "abandoned"      |
| `change_count`  | No       | Number of changes in batch (default 1)          |
| `build_stage`   | No       | Informational only — not used in decision logic |

## Design Principles

1. **Q1.5 is Python code, not YAML** — causal rules require logic, not patterns
2. **Classifier never decides** — it returns signals, decisions are in decision.py
3. **Gate order is hardcoded** — Q1→Q1.5→Q2 cannot be reordered
4. **Empty input = safe default** — missing changed_files → ESCALATE, not silent failure
5. **Zero false blame** — the system will ESCALATE rather than wrongly blame
6. **Exact path matching** — Q2 uses exact path comparison only. If your CI logs report absolute paths but changed_files are relative, Q2 will ESCALATE (safe default). Normalize paths before input for best coverage.

## License

MIT
