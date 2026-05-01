# Decision Model — RootLens

## Core Principle

RootLens is a **causal decision engine**, not a pattern classifier.

The key distinction:
- Pattern classifier: "This log *looks like* an infrastructure failure"
- Causal engine: "No code change can *physically produce* this failure mode"

## Three-Gate Architecture

```
Input → Q1 → Q1.5 → Q2 → ESCALATE (default)
         ↓      ↓      ↓
       CLOSE  CLOSE  TRUE_REJECT
```

### Q1: State Gate
**Question**: Is this change still active?

If the code change is already merged or abandoned, there is nothing to reject.
Immediate CLOSE.

### Q1.5: Causal Impossibility Gate
**Question**: Can ANY code change produce this failure?

This is the core innovation. Each rule proves:
1. The error occurs at an infrastructure layer (disk, network, node)
2. No code change can reach that layer
3. Therefore, blaming the code is logically impossible

Rules are **hardcoded in Python** because:
- Causal proofs require conditional logic (not just regex)
- Each rule needs counterexample analysis
- YAML cannot express "if X then Y is impossible because Z"

### Q2: Smoking Gun Gate
**Question**: Does the error occur IN a file that was changed?

Requirements (ALL must be true):
1. Compilation/syntax error detected (from classifier)
2. Error references a specific file path
3. That file path intersects with changed_files
4. change_count == 1 (single change, not batch)

If all true → TRUE_REJECT (the code demonstrably broke compilation)

## Why ESCALATE Exists

Many failures are ambiguous:
- Test timeout: code CAN introduce infinite loops
- Flaky test: code CAN trigger race conditions
- Linker error without file path: cannot determine intersection
- Batch changes: cannot isolate which change is responsible

In these cases, the correct answer is "I don't know" — not a guess.

## Confidence Model

| Decision     | Confidence | Meaning                             |
| ------------ | ---------- | ----------------------------------- |
| CLOSE (Q1)   | 1.0        | State is deterministic fact         |
| CLOSE (Q1.5) | 1.0        | Causal proof eliminates code        |
| TRUE_REJECT  | 1.0        | File intersection is deterministic  |
| ESCALATE     | 0.0        | Insufficient evidence for any claim |

Note: There are no intermediate confidence values. This is deliberate.
The system either *knows* or it *admits ignorance*.

## Anti-Design: What This System Does NOT Do

1. **Probability scoring** — no "70% likely infra"
2. **LLM classification** — no neural network guessing
3. **Historical frequency** — "usually infra" is not proof
4. **Keyword voting** — counting error keywords is not causality
5. **Team routing** — who to assign is a separate problem

## Evaluation Methodology

The system is evaluated on **false blame rate**, not accuracy:
- A missed CLOSE (classified as ESCALATE) is safe — human reviews it
- A false TRUE_REJECT (blaming innocent code) is **never acceptable**

Target: **0% false blame rate** on all evaluated datasets.
