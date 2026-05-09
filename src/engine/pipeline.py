"""
pipeline.py — Public API for RootLens decision engine.

Supports both module-level convenience function and dependency injection.
"""
import logging
from typing import Optional

from .decision import DecisionEngine
from .models import BuildContext, DecisionResult

logger = logging.getLogger("rootlens")


def create_engine() -> DecisionEngine:
    """Factory function for creating a new engine instance (testable)."""
    return DecisionEngine()


# Module-level convenience instance (can be replaced for testing)
_default_engine: Optional[DecisionEngine] = None


def _get_engine() -> DecisionEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = create_engine()
    return _default_engine


def reset_engine() -> None:
    """Reset the default engine (useful for testing)."""
    global _default_engine
    _default_engine = None


def analyze(
    build_log: str,
    changed_files: Optional[list] = None,
    change_status: str = "open",
    change_count: int = 1,
    build_stage: str = "",
) -> DecisionResult:
    """Analyze a build failure and return causal decision.

    This is the primary public API.

    Raises:
        ValueError: If build_log is not a non-empty string.
    """
    if not isinstance(build_log, str) or not build_log.strip():
        raise ValueError("build_log must be a non-empty string")

    ctx = BuildContext(
        build_log=build_log,
        changed_files=changed_files or [],
        change_status=change_status,
        change_count=change_count,
        build_stage=build_stage,
    )
    engine = _get_engine()
    result = engine.evaluate(ctx)
    logger.info(
        "Decision: %s | Rule: %s | Confidence: %.1f",
        result.decision, result.rule_name or "none", result.confidence,
    )
    return result
