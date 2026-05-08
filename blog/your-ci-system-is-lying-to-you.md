# Your CI System Is Lying to You

Your CI system is lying to you.

In 30–40% of failures, it blames the wrong developer.

Not because the logs are unclear — but because the system is asking the wrong question.

It asks: *"What error happened?"*

The right question is: **"Can this failure be caused by the code change?"**

These are fundamentally different questions. The first classifies symptoms. The second establishes causality. And the gap between them is where every false blame lives.

This is the design behind [RootLens](https://github.com/zhangbin0027/rootlens).

---

## The Failure of Pattern Matching

Traditional CI triage works like this:

```
Log contains "error:" → blame the code change
Log contains "timeout" → maybe infra?
Log contains both → ¯\_(ツ)_/¯
```

This is **keyword voting**, not reasoning. It produces two catastrophic failure modes:

- **False blame**: `No space left on device` appears alongside `error: cannot find symbol` → system blames the developer for a disk-full issue. Developer spends 2 hours investigating a failure they didn't cause.
- **False acquittal**: A real compilation error gets dismissed because the log also contains infra-looking keywords. The bug ships.

The root cause: pattern matching answers "what does this *look like*?" instead of "what can *physically cause* this?"

---

## Three Gates, Not One Classifier

RootLens uses a three-gate architecture. Each gate asks a different causal question. The order is hardcoded and cannot be reordered.

```
Input → Q1 → Q1.5 → Q2 → ESCALATE (default)
         ↓      ↓      ↓
       CLOSE  CLOSE  TRUE_REJECT
```

### Gate 1 (Q1): "Is this change still active?"

If the code change is already merged or abandoned, there is nothing to reject. Immediate CLOSE. Trivial, but eliminates noise.

### Gate 2 (Q1.5): "Is it even *possible* for the change to cause this?"

This is the core innovation.

RootLens does not ask: *"Is this likely caused by the change?"*

It asks: **"Is it even possible for the change to cause this?"**

If not, the developer is **provably innocent**.

Each rule proves impossibility through causal reasoning:

| Rule | Signal | Why code can't cause it |
|------|--------|------------------------|
| DISK_FULL | `No space left on device` | Code cannot alter disk capacity on the build node |
| BUILD_NODE_OFFLINE | `slave went offline` | Code cannot crash a build node or sever its network |
| PRE_APPLY_FAILURE | `MANIFEST_INIT_ERROR` | Error fires before code is even checked out |
| BUILD_OOM_KILLED | `oom-kill` (OS signal) | Code cannot set build node memory limits |

There are 10 rules total. Each one carries:
- A **causal proof**: why the code change cannot be on the causal chain
- A **counterexample test**: "can I construct a code change that triggers this?" — if yes, the rule is **rejected**

Rules that **failed** the counterexample test and were rejected:
- Test timeout — code CAN introduce infinite loops
- Compile error — code directly causes this
- Flaky test — code CAN trigger race conditions
- Missing dependency — code CAN remove a dependency declaration

This admission criterion is what separates Q1.5 from a keyword list. Keywords match on *appearance*. Q1.5 rules match on *mechanism*.

### Gate 3 (Q2): "Did the code change break compilation?"

Q2 does not infer causality. It proves it.

When a compilation error points to a file that was modified by exactly one change, there is only one possible cause.

```
IF error is compilation/syntax/linker
   AND error references file X
   AND file X is in the changed files
   AND only one change in the batch
THEN → TRUE_REJECT
```

No heuristics. No probability. No guess.

---

## ESCALATE: The Safety Guarantee

Most systems fail because they always give an answer.

RootLens is designed to **refuse answering** when causality cannot be proven.

| Decision | Meaning | Confidence |
|----------|---------|------------|
| CLOSE | Proven: code cannot cause this | 100% |
| TRUE_REJECT | Proven: code caused this | 100% |
| **ESCALATE** | **Unknown: needs human review** | **0%** |

There are no intermediate confidence values. The system either *knows* or *admits ignorance*.

ESCALATE is not a fallback. It is a safety guarantee.

A system that says "I don't know" is more trustworthy than one that always has an answer.

---

## What This System Refuses To Do

1. **LLM classification** — non-deterministic. Same input can produce different outputs. No causal guarantees.
2. **Probability scoring** — trades precision for coverage. "70% likely infra" invites threshold tuning, which invites false blame.
3. **Historical frequency** — "this error is usually infra" is correlation, not causation. The one time it isn't, you blame the wrong person.
4. **Keyword voting** — counting error keywords is not causality. A log with 10 infra keywords and 1 compile error is still a compile error.

---

## The Metric That Matters

The system is evaluated on **false blame rate**, not accuracy.

- A missed CLOSE (classified as ESCALATE) is **safe** — a human reviews it
- A false TRUE_REJECT (blaming innocent code) is **never acceptable**

40 adversarial cases designed to break naive classifiers:
- Mixed infra + compile signals in the same log
- Misleading keyword combinations
- Edge cases where correlation fails but causality holds

```
Result:
  RootLens:  100% accuracy, 0% false blame
  Baseline:   67% accuracy, 12.5% false blame
```

The baseline is a naive regex classifier — which is what most real CI systems actually use.

---

## Try It

```bash
pip install pyyaml
git clone https://github.com/zhangbin0027/rootlens
cd rootlens
python examples/demo.py
python benchmarks/evaluate.py
```

```python
from src.engine.pipeline import analyze

result = analyze(
    build_log="error: No space left on device",
    changed_files=["src/main.cpp"],
)
print(result.decision)    # "CLOSE"
print(result.proof)       # "Disk capacity is a build node resource constraint..."
```

---

## The Difference

Most CI systems classify errors.

**RootLens assigns responsibility.**

The first is a guess. The second is a proof.

---

*[RootLens](https://github.com/zhangbin0027/rootlens) is open source (Apache 2.0). Contributions welcome.*
