"""Extended tests for q1_5.py — covering rules not hit by test_q1_5.py."""
from rootlens.q1_5 import InfraGuard, _get_adjacent_lines, _in_error_context


class TestHelpers:
    def test_get_adjacent_lines_found(self):
        log = "line1\nline2\ntarget\nline4\nline5"
        result = _get_adjacent_lines(log, "target", window=1)
        assert "target" in result
        assert "line2" in result
        assert "line4" in result

    def test_get_adjacent_lines_not_found(self):
        log = "line1\nline2"
        result = _get_adjacent_lines(log, "nothere", window=2)
        assert result == ["nothere"]

    def test_in_error_context_true(self):
        log = "error: something\ntarget signal"
        assert _in_error_context(log, "target signal") is True

    def test_in_error_context_false_when_in_assertion(self):
        log = (
            'expected: "target signal"\n'
            'assert output contains target signal'
        )
        assert _in_error_context(log, "target signal") is False


class TestRuleVcsToolFailure:
    def test_suppress_dest_branch_error(self):
        log = "error: --suppress-dest-branch not recognized\naborting"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "VCS_TOOL_INTERNAL_FAILURE"

    def test_suppress_dest_branch_with_continue(self):
        log = "--suppress-dest-branch\ncontinue as usual"
        r = InfraGuard.evaluate(log)
        # should not fire — "continue as usual" guards it
        if r is not None:
            assert r.rule_name != "VCS_TOOL_INTERNAL_FAILURE"

    def test_repo_command_not_found(self):
        log = "error: something\nrepo: command not found"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "VCS_TOOL_INTERNAL_FAILURE"


class TestRuleEnvironmentUnreachable:
    def test_bazel_output_root_missing(self):
        log = "error: bazel/output_user_root/abc: No such file or directory"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "ENVIRONMENT_UNREACHABLE"


class TestRuleOomKilled:
    def test_oom_kill_kernel_signal(self):
        log = "Killed process 1234 (cc1plus)\noom_kill: victim=cc1plus"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "BUILD_OOM_KILLED"

    def test_oom_dash_kill(self):
        log = "oom-kill action=kill, victim process: cc1plus"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "BUILD_OOM_KILLED"

    def test_bare_killed_does_not_fire(self):
        log = "Killed\nBuild failed"
        r = InfraGuard.evaluate(log)
        if r is not None:
            assert r.rule_name != "BUILD_OOM_KILLED"

    def test_out_of_memory_compiler_does_not_fire(self):
        log = "cc1plus: out of memory allocating 65536 bytes"
        r = InfraGuard.evaluate(log)
        if r is not None:
            assert r.rule_name != "BUILD_OOM_KILLED"


class TestRuleGitResetFailure:
    def test_git_reset_fails_not_cherry_pick(self):
        log = "error: Your local changes would be overwritten by merge.\ngit reset --hard failed"
        r = InfraGuard.evaluate(log)
        # no cherry-pick/revert context — may fire
        if r is not None:
            assert r.causal_proof is not None

    def test_cherry_pick_context_excluded(self):
        log = "cherry-pick in progress\ngit reset --hard HEAD failed"
        r = InfraGuard.evaluate(log)
        if r is not None:
            assert r.rule_name != "GIT_RESET_FAILURE"


class TestRuleGitRemoteUnreachable:
    def test_connection_refused_with_git_context(self):
        log = "error: Connection refused\ngit fetch origin failed"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "GIT_REMOTE_UNREACHABLE"

    def test_could_not_read_remote(self):
        log = "error: Could not read from remote repository\ngit clone failed"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "GIT_REMOTE_UNREACHABLE"

    def test_connection_refused_without_git_context_no_fire(self):
        log = "Connection refused\nHTTP server error"
        r = InfraGuard.evaluate(log)
        if r is not None:
            assert r.rule_name != "GIT_REMOTE_UNREACHABLE"


class TestRuleArtifactUploadFailure:
    def test_upload_failed(self):
        log = "error uploading artifact\nupload failed: connection reset"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "ARTIFACT_UPLOAD_FAILURE"

    def test_put_object_failed(self):
        log = "put object failed: S3 timeout\nerror storing artifact"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "ARTIFACT_UPLOAD_FAILURE"


class TestRuleFileTransferFailure:
    def test_ssh_connect_to_host(self):
        log = "error\nscp transfer: ssh: connect to host artifacts.ci port 22: No route to host"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name in ("FILE_TRANSFER_FAILURE", "GIT_REMOTE_UNREACHABLE")

    def test_scp_connection_lost(self):
        log = "error\nscp: connection lost during transfer"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "FILE_TRANSFER_FAILURE"

    def test_connection_timed_out_with_ssh(self):
        log = "error\nssh transfer: connection timed out"
        r = InfraGuard.evaluate(log)
        assert r is not None
        assert r.rule_name == "FILE_TRANSFER_FAILURE"


class TestInErrorContextQuoteGuard:
    def test_signal_in_quoted_string_ignored(self):
        # Signal inside a string literal should not count as genuine context
        log = 'assert error_msg == "upload failed"\ntest passed'
        r = InfraGuard.evaluate(log)
        # upload failed in quoted assertion context — should not fire
        if r is not None:
            assert r.rule_name != "ARTIFACT_UPLOAD_FAILURE"


class TestNoFalsePositives:
    """Adversarial: logs that look like infra but are code-caused."""

    def test_compile_error_only_escalates(self):
        log = "src/main.cpp:10: error: 'Foo' was not declared"
        r = InfraGuard.evaluate(log)
        assert r is None

    def test_test_failure_escalates(self):
        log = "FAILED tests/test_auth.py::test_login - AssertionError"
        r = InfraGuard.evaluate(log)
        assert r is None

    def test_empty_log_returns_none(self):
        assert InfraGuard.evaluate("") is None

    def test_clean_log_returns_none(self):
        assert InfraGuard.evaluate("Build successful. 0 errors.") is None
