"""
decision.py — The Decision Engine (Layer 1: Deterministic Core)

Enforced gate order: Q1 -> Q1.5 -> Q2 (hardcoded, not configurable).
"""
import logging
import re
from typing import Optional, Set

from .classifier import classify, extract_files
from .models import BuildContext, DecisionResult, normalize_path
from .q1_5 import InfraGuard

logger = logging.getLogger("rootlens")

_INVALID_STATES = {"merged", "abandoned"}
_DETERMINISTIC_TYPES = {"COMPILATION", "SYNTAX", "LINKER"}


class DecisionEngine:
    """Deterministic causal decision engine.

    Q1:   change_status filter
    Q1.5: causal impossibility (InfraGuard)
    Q2:   compilation smoking gun (file intersection)
    """

    def evaluate(self, ctx: BuildContext) -> DecisionResult:
        """Run Q1 -> Q1.5 -> Q2. Returns DecisionResult."""
        r = self._q1_state(ctx)
        if r:
            logger.info("Q1 fired: %s", r.rule_name)
            return r
        r = self._q15_infra(ctx)
        if r:
            logger.info("Q1.5 fired: %s", r.rule_name)
            return r
        r = self._q2_compile(ctx)
        if r:
            logger.info("Q2 fired: %s -> %s", r.rule_name, r.decision)
            return r
        logger.info("All gates passed — ESCALATE")
        return DecisionResult(
            decision="ESCALATE",
            reason="Causality undetermined - insufficient evidence",
            confidence=0.0,
        )

    def _q1_state(self, ctx: BuildContext) -> Optional[DecisionResult]:
        if ctx.change_status in _INVALID_STATES:
            return DecisionResult(
                decision="CLOSE",
                reason=f"Change is {ctx.change_status} (not active)",
                confidence=1.0,
                rule_name="Q1_STATE_FILTER",
                matched_signal=f"status={ctx.change_status}",
            )
        return None

    def _q15_infra(self, ctx: BuildContext) -> Optional[DecisionResult]:
        verdict = InfraGuard.evaluate(ctx.build_log)
        if verdict:
            return DecisionResult(
                decision="CLOSE",
                reason=f"Infrastructure failure: {verdict.rule_name}",
                confidence=1.0,
                proof=verdict.causal_proof,
                rule_name=verdict.rule_name,
                matched_signal=verdict.matched_signal,
            )
        return None

    def _q2_compile(self, ctx: BuildContext) -> Optional[DecisionResult]:
        signal = classify(ctx.build_log)
        if signal is None:
            return None
        if signal.error_type not in _DETERMINISTIC_TYPES:
            return None
        if not ctx.changed_files:
            return DecisionResult(
                decision="ESCALATE",
                reason="File intersection requires changed_files (not provided)",
                confidence=0.0,
                matched_signal=signal.matched_pattern,
            )
        if ctx.change_count > 1:
            return DecisionResult(
                decision="ESCALATE",
                reason=f"Multi-change batch ({ctx.change_count}) - cannot isolate",
                confidence=0.0,
                matched_signal=signal.matched_pattern,
            )
        err_files = signal.error_files if signal.error_files else extract_files(ctx.build_log)
        # Normalize extracted error files for consistent comparison
        err_files_norm = {normalize_path(f) for f in err_files}
        hit = self._intersect(set(ctx.changed_files), err_files_norm)
        if not hit:
            return DecisionResult(
                decision="ESCALATE",
                reason="Compile error but no file intersection with changed files",
                confidence=0.0,
                matched_signal=signal.matched_pattern,
            )
        return DecisionResult(
            decision="TRUE_REJECT",
            reason=f"Compilation error in changed file: {sorted(hit)[0]}",
            confidence=1.0,
            rule_name="Q2_SMOKING_GUN",
            matched_signal=signal.matched_pattern,
        )

    def _intersect(self, changed: Set[str], error: Set[str]) -> Set[str]:
        """File intersection using EXACT path match only.

        Strict matching prevents false blame in monorepos where
        different directories contain files with the same name
        (e.g., src/auth/handler.java vs vendor/auth/handler.java).

        Trade-off: if CI logs report absolute paths but changed_files
        are relative, this will not match (safe ESCALATE).
        Callers should normalize paths before input for best coverage.
        """
        return changed & error
