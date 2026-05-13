"""Tests for decision.py — full engine integration, path normalization, Q2."""
import pytest
from rootlens.decision import DecisionEngine
from rootlens.models import BuildContext


@pytest.fixture
def engine():
    return DecisionEngine()


class TestQ1StateFilter:
    def test_merged_returns_close(self, engine):
        ctx = BuildContext(build_log="some error", change_status="merged")
        r = engine.evaluate(ctx)
        assert r.decision == "CLOSE"
        assert r.rule_name == "Q1_STATE_FILTER"

    def test_abandoned_returns_close(self, engine):
        ctx = BuildContext(build_log="error", change_status="abandoned")
        r = engine.evaluate(ctx)
        assert r.decision == "CLOSE"

    def test_open_passes_through(self, engine):
        ctx = BuildContext(build_log="normal log no errors")
        r = engine.evaluate(ctx)
        assert r.decision == "ESCALATE"


class TestQ15Integration:
    def test_infra_failure_returns_close(self, engine):
        ctx = BuildContext(build_log="MANIFEST_INIT_ERROR: failed")
        r = engine.evaluate(ctx)
        assert r.decision == "CLOSE"
        assert r.rule_name == "PRE_APPLY_FAILURE"
        assert r.proof  # Must have proof

    def test_normal_log_escalates(self, engine):
        ctx = BuildContext(build_log="Build succeeded with warnings")
        r = engine.evaluate(ctx)
        assert r.decision == "ESCALATE"


COMPILE_LOG = "error: cannot find symbol\nsrc/auth/Login.java:42: error"


class TestQ2FileIntersection:
    def test_no_changed_files_escalates(self, engine):
        ctx = BuildContext(build_log=COMPILE_LOG, changed_files=[])
        r = engine.evaluate(ctx)
        assert r.decision == "ESCALATE"
        assert "changed_files" in r.reason

    def test_multi_change_batch_escalates(self, engine):
        ctx = BuildContext(
            build_log=COMPILE_LOG,
            changed_files=["src/auth/Login.java"],
            change_count=3,
        )
        r = engine.evaluate(ctx)
        assert r.decision == "ESCALATE"
        assert "Multi-change" in r.reason

    def test_no_file_intersection_escalates(self, engine):
        ctx = BuildContext(
            build_log=COMPILE_LOG,
            changed_files=["src/other/Unrelated.java"],
        )
        r = engine.evaluate(ctx)
        assert r.decision == "ESCALATE"
        assert "intersection" in r.reason

    def test_non_deterministic_error_type_escalates(self, engine):
        # Log matches a pattern but error_type is not in _DETERMINISTIC_TYPES
        ctx = BuildContext(
            build_log="warning: something suspicious",
            changed_files=["src/foo.java"],
        )
        r = engine.evaluate(ctx)
        assert r.decision == "ESCALATE"


class TestPathNormalization:
    """C5 fix: paths with ./ and / prefixes must still match."""

    def test_dot_slash_normalized(self, engine):
        ctx = BuildContext(
            build_log="x", changed_files=["./src/foo.cpp"]
        )
        assert "src/foo.cpp" in ctx.changed_files

    def test_absolute_path_normalized(self, engine):
        ctx = BuildContext(
            build_log="x", changed_files=["/workspace/src/bar.h"]
        )
        assert "workspace/src/bar.h" in ctx.changed_files


class TestGateOrder:
    """Q1 -> Q1.5 -> Q2 must be strictly enforced."""

    def test_merged_skips_infra_check(self, engine):
        # Log has infra signal but status is merged — Q1 should fire first
        log = "MANIFEST_INIT_ERROR: fail\nslave went offline"
        ctx = BuildContext(build_log=log, change_status="merged")
        r = engine.evaluate(ctx)
        assert r.rule_name == "Q1_STATE_FILTER"  # Q1 first, not Q1.5

    def test_infra_prevents_q2(self, engine):
        # Log has both infra signal and compile error
        log = "slave went offline\nsrc/foo.cpp:1: error: x"
        ctx = BuildContext(build_log=log, changed_files=["src/foo.cpp"])
        r = engine.evaluate(ctx)
        assert r.rule_name == "BUILD_NODE_OFFLINE"  # Q1.5, not Q2
