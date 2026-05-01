# Contributing to RootLens

Thank you for your interest in improving RootLens!

## Adding a New Q1.5 Rule

Q1.5 rules must satisfy **causal impossibility** — the failure *cannot* be caused by any code change.

### Admission criteria (all required)

1. **Existential negation**: `P(Failure ⊥ CR) = 1` — not a probability judgment
2. **Counterexample reasoning**: explicitly answer "Can any CR cause this error?"
3. **Real case validation**: at least one production CI case as evidence

### Steps

1. Add the check function in `src/engine/q1_5.py`
2. Register it in `Q15Filter.evaluate()` with a descriptive `Verdict.reason`
3. Write at least two test cases in `benchmarks/dataset.json`:
   - One that triggers the rule → expected `CLOSE`
   - One adversarial case that should *not* trigger → expected `ESCALATE`
4. Run the benchmark: `python benchmarks/evaluate.py`
5. Confirm 0% false blame rate

### What does NOT belong in Q1.5

- Patterns where a CR *could* cause the error (even if unlikely)
- Heuristic / probabilistic matches
- Patterns that require semantic reasoning about code changes

These belong in V2 (hint layer), not Q1.5.

## Adding an Error Pattern

Error patterns live in `configs/error_patterns.yaml`.

1. Add the pattern with `regex`, `type`, and `description`
2. Verify it does not overlap with existing patterns (check `docs/q1_5_rules.md`)
3. Add a test log in `examples/logs/` if the pattern covers a new failure mode

## Code Style

- Python 3.9+
- Type hints on all function signatures
- `flake8` clean (line length 120)
- No dependencies beyond `pyyaml`

## Running Tests

```bash
python benchmarks/evaluate.py
```

All 40 cases must pass with 0% false blame rate before merging.

## Reporting Issues

Open a GitHub Issue with:
- The CI log snippet (anonymized if needed)
- Expected vs actual RootLens verdict
- Your CI system context (Jenkins, GitHub Actions, etc.)
