"""Tests for models.py — validation, enums, path normalization."""
import pytest
from rootlens.models import (
    BuildContext, Decision, DecisionResult, RuleVerdict, normalize_path
)


class TestDecisionEnum:
    def test_valid_values(self):
        assert Decision.CLOSE.value == "CLOSE"
        assert Decision.TRUE_REJECT.value == "TRUE_REJECT"
        assert Decision.ESCALATE.value == "ESCALATE"

    def test_no_extra_values(self):
        assert len(Decision) == 3


class TestDecisionResult:
    def test_valid_creation(self):
        r = DecisionResult(decision="CLOSE", reason="test", confidence=1.0)
        assert r.decision == "CLOSE"

    def test_invalid_decision_raises(self):
        with pytest.raises(ValueError, match="decision must be one of"):
            DecisionResult(decision="MAYBE", reason="x", confidence=0.5)

    def test_empty_reason_raises(self):
        with pytest.raises(ValueError, match="reason must be non-empty"):
            DecisionResult(decision="CLOSE", reason="", confidence=1.0)


class TestRuleVerdict:
    def test_valid_creation(self):
        v = RuleVerdict(
            rule_name="TEST", causal_proof="proof",
            counterexample="counter", matched_signal="sig"
        )
        assert v.rule_name == "TEST"

    def test_empty_proof_raises(self):
        with pytest.raises(ValueError, match="causal_proof required"):
            RuleVerdict(rule_name="X", causal_proof="",
                        counterexample="c", matched_signal="s")

    def test_empty_counterexample_raises(self):
        with pytest.raises(ValueError, match="counterexample required"):
            RuleVerdict(rule_name="X", causal_proof="p",
                        counterexample="", matched_signal="s")

    def test_empty_signal_raises(self):
        with pytest.raises(ValueError, match="matched_signal required"):
            RuleVerdict(rule_name="X", causal_proof="p",
                        counterexample="c", matched_signal="")


class TestBuildContext:
    def test_default_values(self):
        ctx = BuildContext(build_log="test log")
        assert ctx.change_status == "open"
        assert ctx.change_count == 1
        assert ctx.changed_files == []

    def test_status_normalization(self):
        ctx = BuildContext(build_log="x", change_status="MERGED ")
        assert ctx.change_status == "merged"

    def test_invalid_status_defaults_to_open(self):
        ctx = BuildContext(build_log="x", change_status="bogus")
        assert ctx.change_status == "open"

    def test_none_status_defaults_to_open(self):
        ctx = BuildContext(build_log="x", change_status=None)
        assert ctx.change_status == "open"

    def test_invalid_change_count_raises(self):
        with pytest.raises(ValueError):
            BuildContext(build_log="x", change_count=0)

    def test_path_normalization_in_changed_files(self):
        ctx = BuildContext(build_log="x", changed_files=["./src/foo.cpp", "/abs/bar.h"])
        assert ctx.changed_files == ["src/foo.cpp", "abs/bar.h"]

    def test_log_truncation(self):
        big = "x" * (11 * 1024 * 1024)
        ctx = BuildContext(build_log=big)
        assert len(ctx.build_log) == 10 * 1024 * 1024


class TestNormalizePath:
    def test_strip_dot_slash(self):
        assert normalize_path("./src/foo.cpp") == "src/foo.cpp"

    def test_strip_leading_slash(self):
        assert normalize_path("/workspace/src/foo.cpp") == "workspace/src/foo.cpp"

    def test_backslash_to_forward(self):
        assert normalize_path("src\\foo.cpp") == "src/foo.cpp"

    def test_strip_whitespace(self):
        assert normalize_path("  src/foo.cpp  ") == "src/foo.cpp"

    def test_multiple_dot_slash(self):
        assert normalize_path("././src/foo.cpp") == "src/foo.cpp"
