"""
models.py — Data models for RootLens causal decision engine.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List

logger = logging.getLogger("rootlens")

MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
VALID_STATUSES = {"open", "merged", "abandoned"}


class Decision(Enum):
    """Three-class decision output. No other values are permitted."""
    CLOSE = "CLOSE"
    TRUE_REJECT = "TRUE_REJECT"
    ESCALATE = "ESCALATE"


@dataclass
class BuildContext:
    """Input context for the decision engine."""
    build_log: str
    changed_files: List[str] = field(default_factory=list)
    change_status: str = "open"
    change_count: int = 1
    build_stage: str = ""

    def __post_init__(self):
        if self.change_count < 1:
            raise ValueError(f"change_count must be >= 1, got {self.change_count}")
        if self.change_status is None:
            self.change_status = "open"
        self.change_status = self.change_status.strip().lower()
        if self.change_status not in VALID_STATUSES:
            logger.warning("Unknown change_status '%s', treating as 'open'", self.change_status)
            self.change_status = "open"
        if len(self.build_log) > MAX_LOG_SIZE:
            logger.warning("build_log exceeds %d bytes, truncating", MAX_LOG_SIZE)
            self.build_log = self.build_log[:MAX_LOG_SIZE]
        self.changed_files = [normalize_path(f) for f in self.changed_files]


@dataclass
class DecisionResult:
    """Output of the decision engine. Three-class: CLOSE / TRUE_REJECT / ESCALATE."""
    decision: str
    reason: str
    confidence: float
    proof: str = ""
    rule_name: str = ""
    matched_signal: str = ""

    def __post_init__(self):
        valid = {d.value for d in Decision}
        if self.decision not in valid:
            raise ValueError(f"decision must be one of {valid}, got '{self.decision}'")
        if not self.reason:
            raise ValueError("reason must be non-empty")


@dataclass
class RuleVerdict:
    """Output of a Q1.5 causal rule. All fields MUST be non-empty."""
    rule_name: str
    causal_proof: str
    counterexample: str
    matched_signal: str

    def __post_init__(self):
        if not self.rule_name:
            raise ValueError("rule_name must be non-empty")
        if not self.causal_proof:
            raise ValueError(f"causal_proof required for rule '{self.rule_name}'")
        if not self.counterexample:
            raise ValueError(f"counterexample required for rule '{self.rule_name}'")
        if not self.matched_signal:
            raise ValueError(f"matched_signal required for rule '{self.rule_name}'")


@dataclass
class ErrorSignal:
    """Output of the classifier (Layer 2). Signal only, not a decision."""
    error_type: str
    matched_pattern: str
    error_files: List[str] = field(default_factory=list)


def normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison."""
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p.lstrip("/")
    return p
