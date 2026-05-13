"""Tests for pipeline.py — public API, engine lifecycle, input validation."""
import pytest
from rootlens import analyze, create_engine, reset_engine
from rootlens.pipeline import _get_engine


class TestAnalyzePublicAPI:
    def setup_method(self):
        reset_engine()

    def test_infra_log_returns_close(self):
        r = analyze("No space left on device", ["src/main.py"])
        assert r.decision == "CLOSE"

    def test_compile_error_with_match_returns_true_reject(self):
        r = analyze(
            "src/auth/Login.java:42: error: cannot find symbol",
            changed_files=["src/auth/Login.java"],
        )
        assert r.decision == "TRUE_REJECT"

    def test_ambiguous_log_escalates(self):
        r = analyze("something went wrong", ["src/main.py"])
        assert r.decision == "ESCALATE"

    def test_no_changed_files_defaults_to_empty(self):
        r = analyze("No space left on device")
        assert r.decision == "CLOSE"

    def test_change_status_merged_closes(self):
        r = analyze("error: something", change_status="merged")
        assert r.decision == "CLOSE"

    def test_change_count_batch_escalates(self):
        r = analyze(
            "src/foo.py:1: error: x",
            changed_files=["src/foo.py"],
            change_count=5,
        )
        assert r.decision == "ESCALATE"

    def test_build_stage_passed_through(self):
        r = analyze("No space left on device", build_stage="compile")
        assert r.decision == "CLOSE"


class TestInputValidation:
    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            analyze("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            analyze("   \n  ")

    def test_none_raises(self):
        with pytest.raises((ValueError, TypeError)):
            analyze(None)  # type: ignore


class TestEngineLifecycle:
    def setup_method(self):
        reset_engine()

    def test_create_engine_returns_new_instance(self):
        e1 = create_engine()
        e2 = create_engine()
        assert e1 is not e2

    def test_get_engine_returns_same_instance(self):
        e1 = _get_engine()
        e2 = _get_engine()
        assert e1 is e2

    def test_reset_engine_clears_instance(self):
        e1 = _get_engine()
        reset_engine()
        e2 = _get_engine()
        assert e1 is not e2

    def test_analyze_after_reset_works(self):
        reset_engine()
        r = analyze("No space left on device")
        assert r.decision == "CLOSE"
