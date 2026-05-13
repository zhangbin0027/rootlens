"""Tests for Q1.5 — Causal impossibility rules + anti-injection."""
import pytest
from rootlens.q1_5 import InfraGuard, _in_error_context


class TestAntiInjection:
    """C3 fix: log injection must NOT produce false CLOSE."""

    def test_signal_in_test_output_rejected(self):
        log = '''Running test: test_disk_error_display
Verifying user sees "No space left on device" message
ASSERTION FAILED: dialog not shown
BUILD FAILED: 1 test failed'''
        assert _in_error_context(log, "No space left on device") is False

    def test_signal_in_quotes_rejected(self):
        log = 'Expected output: "ssh: connect to host" but got timeout'
        assert _in_error_context(log, "ssh: connect to host") is False

    def test_signal_in_genuine_context_accepted(self):
        log = "ERROR: No space left on device while writing /tmp/cache"
        assert _in_error_context(log, "No space left on device") is True

    def test_signal_with_assert_keyword_rejected(self):
        log = "assert error_msg == 'slave went offline'"
        assert _in_error_context(log, "slave went offline") is False

    def test_genuine_node_offline(self):
        log = "FATAL: slave went offline during build step 3"
        assert _in_error_context(log, "slave went offline") is True


class TestDiskFullGuard:
    """C2 fix: DISK_FULL only fires in infra context, not build output."""

    def test_disk_full_in_tmp_fires(self):
        log = "ERROR: No space left on device writing /tmp/repo_cache"
        result = InfraGuard.evaluate(log)
        assert result is not None
        assert result.rule_name == "DISK_FULL"

    def test_disk_full_in_build_output_does_not_fire(self):
        log = "ERROR: No space left on device writing /out/gen/large_file.o"
        result = InfraGuard.evaluate(log)
        assert result is None

    def test_disk_full_in_test_string_does_not_fire(self):
        log = '''Testing error handling...
Expected: "No space left on device"
Actual: different error
FAILED'''
        result = InfraGuard.evaluate(log)
        assert result is None


class TestOOMGuard:
    """S5 fix: OOM only fires when NOT in compilation context."""

    def test_oom_in_ci_setup_fires(self):
        log = "workspace setup\ndownloading deps\noom-kill: process killed"
        result = InfraGuard.evaluate(log)
        assert result is not None
        assert result.rule_name == "BUILD_OOM_KILLED"

    def test_oom_during_compilation_does_not_fire(self):
        log = "compiling src/heavy_template.cpp\ncc1plus: internal error\noom-kill: killed"
        result = InfraGuard.evaluate(log)
        assert result is None


class TestPreApplyFailure:
    def test_manifest_init_error(self):
        log = "Starting repo sync...\nMANIFEST_INIT_ERROR: cannot parse manifest"
        result = InfraGuard.evaluate(log)
        assert result is not None
        assert result.rule_name == "PRE_APPLY_FAILURE"


class TestBuildNodeOffline:
    def test_slave_offline(self):
        log = "Build step 5/10\nslave went offline\nBuild aborted"
        result = InfraGuard.evaluate(log)
        assert result is not None
        assert result.rule_name == "BUILD_NODE_OFFLINE"

    def test_slave_in_test_assertion(self):
        log = 'assert msg == "slave went offline"'
        result = InfraGuard.evaluate(log)
        assert result is None


class TestGitRemote:
    def test_could_not_read_remote(self):
        log = "fatal: Could not read from remote repository\nPlease check access"
        result = InfraGuard.evaluate(log)
        assert result is not None
        assert result.rule_name == "GIT_REMOTE_UNREACHABLE"


class TestNoMatch:
    def test_normal_compile_error_not_matched(self):
        log = "src/main.cpp:42: error: undefined reference to 'foo'"
        result = InfraGuard.evaluate(log)
        assert result is None

    def test_empty_log(self):
        result = InfraGuard.evaluate("")
        assert result is None
