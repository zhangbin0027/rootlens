"""
q1_5.py — Causally Impossible Failure Detection (Q1.5 Gate)

10 deterministic rules that prove a code change CANNOT be the cause of a failure.
Each rule includes a causal proof and counterexample analysis.

Anti-injection guard: Rules check that the matched signal appears in an
ERROR CONTEXT (not inside quoted strings, test assertions, or expected output).
"""
import re
from typing import Optional

from .models import RuleVerdict


def _get_adjacent_lines(log: str, target_line: str, window: int = 2) -> list:
    """Return target_line plus up to window lines on each side."""
    lines = log.split("\n")
    for i, line in enumerate(lines):
        if line == target_line:
            return lines[max(0, i - window):i + window + 1]
    return [target_line]


def _in_error_context(log: str, signal: str) -> bool:
    """Verify a signal appears in genuine error context, not test output.

    Returns False if the signal appears only inside quoted strings,
    assertion expectations, or test verification output.
    """
    lines = log.split("\n")
    for line in lines:
        if signal.lower() not in line.lower():
            continue
        low = line.lower().strip()
        # Skip lines that are clearly test expectations or string literals
        if any(marker in low for marker in [
            "expected", "verifying", "assert", "testing",
            'expected output', 'should contain', 'should see',
        ]):
            continue
        # Skip if signal is inside quotes on this line
        before_signal = line[:line.lower().find(signal.lower())]
        open_quotes = before_signal.count('"') + before_signal.count("'")
        if open_quotes % 2 == 1:
            continue
        # Found in genuine context
        return True
    return False


class InfraGuard:
    """Q1.5 Infrastructure Guard — 10 causal impossibility rules."""

    @classmethod
    def evaluate(cls, build_log: str) -> Optional[RuleVerdict]:
        """Evaluate build log against all Q1.5 rules."""
        if not build_log:
            return None
        checks = [
            cls._check_pre_apply_failure,
            cls._check_vcs_tool_internal,
            cls._check_environment_unreachable,
            cls._check_disk_full,
            cls._check_build_node_offline,
            cls._check_git_remote_unreachable,
            cls._check_artifact_upload_failure,
            cls._check_file_transfer_failure,
            cls._check_git_reset_failure,
            cls._check_build_oom_killed,
        ]
        for check in checks:
            result = check(build_log)
            if result is not None:
                return result
        return None

    @staticmethod
    def _check_pre_apply_failure(log: str) -> Optional[RuleVerdict]:
        """Error occurs before code checkout — change not yet applied."""
        if "MANIFEST_INIT_ERROR" in log and _in_error_context(log, "MANIFEST_INIT_ERROR"):
            return RuleVerdict(
                rule_name="PRE_APPLY_FAILURE",
                causal_proof=(
                    "Error in repo initialization phase, before code "
                    "checkout. The code change is not present in the "
                    "workspace when this error occurs."
                ),
                counterexample=(
                    "Code change not yet applied when error fires — "
                    "no plausible code change can trigger manifest "
                    "initialization failure."
                ),
                matched_signal="MANIFEST_INIT_ERROR",
            )
        return None

    @staticmethod
    def _check_vcs_tool_internal(log: str) -> Optional[RuleVerdict]:
        """VCS tool internal error — code cannot alter CLI arguments."""
        lines = log.split("\n")
        for i, line in enumerate(lines):
            low = line.lower()
            if "suppress-dest-branch" not in low:
                continue
            if not re.search(
                r"(?:error|unrecognized|not recognized|unknown option|failed)",
                line, re.IGNORECASE
            ):
                continue
            lookahead = lines[i + 1: i + 4]
            if any("continue as usual" in la.lower() for la in lookahead):
                continue
            return RuleVerdict(
                rule_name="VCS_TOOL_INTERNAL_FAILURE",
                causal_proof=(
                    "VCS tool errors originate in the CI toolchain "
                    "layer. Code changes cannot alter VCS tool CLI "
                    "arguments or internal flag parsing."
                ),
                counterexample=(
                    "Code cannot modify VCS tool binary or its "
                    "command-line interface — these are CI-managed."
                ),
                matched_signal="suppress-dest-branch",
            )
        if "repo: command not found" in log and _in_error_context(log, "repo: command not found"):
            return RuleVerdict(
                rule_name="VCS_TOOL_INTERNAL_FAILURE",
                causal_proof=(
                    "VCS tool not found on CI node. Tool installation "
                    "is managed by CI infrastructure, not source code."
                ),
                counterexample=(
                    "Code cannot uninstall the VCS tool from a CI node."
                ),
                matched_signal="repo: command not found",
            )
        return None

    @staticmethod
    def _check_environment_unreachable(log: str) -> Optional[RuleVerdict]:
        """Build cache path missing — CI node local physical state."""
        if re.search(r"bazel/output_user_root/.*No such file or directory", log):
            signal = "bazel/output_user_root/ No such file"
            if _in_error_context(log, "No such file or directory"):
                return RuleVerdict(
                    rule_name="ENVIRONMENT_UNREACHABLE",
                    causal_proof=(
                        "Build cache is CI node physical state — a local "
                        "directory managed by the build infrastructure, "
                        "not addressable by any source code change."
                    ),
                    counterexample=(
                        "Code cannot modify CI node local paths or build "
                        "cache directories."
                    ),
                    matched_signal=signal,
                )
        return None

    @staticmethod
    def _check_disk_full(log: str) -> Optional[RuleVerdict]:
        """No space left on device — build node resource constraint.

        Guard: Only fires if the error occurs in a CI infrastructure context
        (tmp dirs, cache, workspace prep) — NOT in build output directories
        where code-generated artifacts could exhaust space.
        """
        signal = "No space left on device"
        if signal not in log:
            return None
        if not _in_error_context(log, signal):
            return None
        # Additional guard: check if the failing path is in infrastructure context
        # vs build output (where code could generate excessive artifacts)
        lines = log.split("\n")
        for line in lines:
            if signal not in line:
                continue
            low = line.lower()
            # Infrastructure paths that code cannot influence
            infra_indicators = ["/tmp/", "/cache/", "workspace prep", "repo sync",
                                "/var/", ".git/", "manifest"]
            if any(ind in low for ind in infra_indicators):
                return RuleVerdict(
                    rule_name="DISK_FULL",
                    causal_proof=(
                        "Disk full error in CI infrastructure path. "
                        "Disk capacity is a build node resource constraint "
                        "at the OS/filesystem level, not addressable by code."
                    ),
                    counterexample=(
                        "Code cannot alter disk capacity on the build "
                        "node — disk space is hardware managed by CI."
                    ),
                    matched_signal=signal,
                )
            # If path suggests build output, code COULD have caused it — skip
            build_output_indicators = ["/out/", "/build/", "/obj/", "/gen/"]
            if any(ind in low for ind in build_output_indicators):
                return None
        # Default: still fire but only for lines without path context
        # (bare "No space left on device" is still infrastructure)
        return RuleVerdict(
            rule_name="DISK_FULL",
            causal_proof=(
                "Disk capacity is a build node resource constraint "
                "at the OS/filesystem level. Not addressable by "
                "any code change in the repository."
            ),
            counterexample=(
                "Code cannot alter disk capacity on the build "
                "node — disk space is hardware managed by CI."
            ),
            matched_signal=signal,
        )

    @staticmethod
    def _check_build_node_offline(log: str) -> Optional[RuleVerdict]:
        """Build node disconnected — infrastructure state."""
        # Patterns match verbatim CI system log output (read-only, cannot be changed).
        # "slave went offline" is legacy CI system terminology present in real build logs.
        patterns = [
            "slave went offline",
            "node is offline",
            "ChannelClosedException",
            "connection was broken",
        ]
        _node_ctx = {"slave", "node", "agent", "executor", "worker", "builder", "runner"}
        low = log.lower()
        for pat in patterns:
            if pat.lower() not in low or not _in_error_context(log, pat):
                continue
            if pat == "connection was broken":
                # Guard: require CI node context in the same or adjacent lines
                matched_lines = [
                    line for line in log.split("\n") if pat.lower() in line.lower()
                ]
                if not any(
                    any(ctx in ln.lower() for ctx in _node_ctx)
                    for match_line in matched_lines
                    for ln in _get_adjacent_lines(log, match_line, window=2)
                ):
                    continue
            return RuleVerdict(
                    rule_name="BUILD_NODE_OFFLINE",
                    causal_proof=(
                        "Build node availability is CI infrastructure "
                        "state. Disconnection occurs at the network/"
                        "hardware layer, outside any code change's "
                        "causal reach."
                    ),
                    counterexample=(
                        "Code cannot crash a build node or sever its "
                        "network connection to the CI controller."
                    ),
                    matched_signal=pat,
                )
        return None

    @staticmethod
    def _check_git_remote_unreachable(log: str) -> Optional[RuleVerdict]:
        """Git server unreachable — external network dependency."""
        triggers = [
            "Could not read from remote repository",
            "Connection refused",
        ]
        for trigger in triggers:
            if trigger not in log:
                continue
            if not _in_error_context(log, trigger):
                continue
            if trigger == "Connection refused":
                if "git" not in log.lower() and "ssh" not in log.lower():
                    continue
            return RuleVerdict(
                rule_name="GIT_REMOTE_UNREACHABLE",
                causal_proof=(
                    "Git remote accessibility is a network/server "
                    "state issue. The error occurs at the transport "
                    "layer, outside any code change's causal chain."
                ),
                counterexample=(
                    "Code cannot affect network infrastructure or "
                    "git server availability."
                ),
                matched_signal=trigger,
            )
        return None

    @staticmethod
    def _check_artifact_upload_failure(log: str) -> Optional[RuleVerdict]:
        """Artifact upload/storage failure — post-build infrastructure."""
        triggers = ["upload failed", "put object failed"]
        low = log.lower()
        for trigger in triggers:
            if trigger in low and _in_error_context(log, trigger):
                return RuleVerdict(
                    rule_name="ARTIFACT_UPLOAD_FAILURE",
                    causal_proof=(
                        "Artifact upload occurs in the post-build "
                        "phase. Storage service availability is an "
                        "external infrastructure dependency, not "
                        "addressable by source code changes."
                    ),
                    counterexample=(
                        "Code cannot affect artifact storage service "
                        "availability or network connectivity."
                    ),
                    matched_signal=trigger,
                )
        return None

    @staticmethod
    def _check_file_transfer_failure(log: str) -> Optional[RuleVerdict]:
        """SSH/SCP file transfer failure — CI network layer."""
        low = log.lower()
        ssh_triggers = [
            "scp: connection lost",
            "ssh: connect to host",
        ]
        for trigger in ssh_triggers:
            if trigger in low and _in_error_context(log, trigger):
                return RuleVerdict(
                    rule_name="FILE_TRANSFER_FAILURE",
                    causal_proof=(
                        "SSH/SCP is CI network infrastructure. File "
                        "transfer failures occur at the network layer, "
                        "outside any code change's causal chain."
                    ),
                    counterexample=(
                        "Code cannot affect SSH infrastructure or "
                        "network connectivity between CI nodes."
                    ),
                    matched_signal=trigger,
                )
        if "connection timed out" in low:
            if ("ssh" in low or "scp" in low or "git" in low):
                if _in_error_context(log, "connection timed out"):
                    return RuleVerdict(
                        rule_name="FILE_TRANSFER_FAILURE",
                        causal_proof=(
                            "SSH/SCP/git connection timeout is a CI network "
                            "infrastructure issue at the transport layer, "
                            "outside any code change's causal chain."
                        ),
                        counterexample=(
                            "Code cannot affect SSH/git network connectivity "
                            "between CI nodes."
                        ),
                        matched_signal="connection timed out (ssh/scp/git context)",
                    )
        return None

    @staticmethod
    def _check_git_reset_failure(log: str) -> Optional[RuleVerdict]:
        """git reset failed during workspace preparation (before code apply)."""
        low = log.lower()
        if "cherry-pick" in low or "revert" in low or "conflict" in low:
            return None
        triggers = [
            "git reset --hard failed",
            "unable to reset",
            "during git-reset",
        ]
        for trigger in triggers:
            if trigger in low and _in_error_context(log, trigger):
                return RuleVerdict(
                    rule_name="GIT_RESET_FAILURE",
                    causal_proof=(
                        "git reset is a workspace preparation step that "
                        "executes BEFORE any code change is applied. "
                        "The change is not present when this error fires."
                    ),
                    counterexample=(
                        "Code cannot corrupt CI workspace git state — "
                        "git reset runs before checkout."
                    ),
                    matched_signal=trigger,
                )
        return None

    @staticmethod
    def _check_build_oom_killed(log: str) -> Optional[RuleVerdict]:
        """Build process killed by OS/container OOM killer.

        STRICT: requires oom-kill/oom_kill signal AND non-compilation context.
        If oom-kill occurs during compilation of user code, it COULD be
        caused by template explosion — skip in that case.
        """
        if not re.search(r'oom[_-]kill', log, re.IGNORECASE):
            return None
        if not _in_error_context(log, "oom"):
            return None
        # Guard: if the OOM happens during active compilation of user source
        # files (not just reporting which process was killed), template
        # explosion or massive codegen could be the cause.
        # Note: "oom-kill: process 12345 (cc1plus)" is the OOM killer
        # REPORTING which process it killed — cc1plus is the victim,
        # not evidence that code caused the OOM. Only skip if the
        # PRECEDING lines show active compilation of a specific source file.
        low = log.lower()
        lines = low.split("\n")
        oom_line_idx = None
        for i, line in enumerate(lines):
            if re.search(r'oom[_-]kill', line):
                oom_line_idx = i
                break
        if oom_line_idx is not None:
            # Check preceding lines for active compilation of source files
            # (e.g., "Compiling src/huge_template.cpp...")
            context_window = lines[max(0, oom_line_idx - 5):oom_line_idx]
            context_text = " ".join(context_window)
            # Only skip if we see explicit source file compilation
            if re.search(r'compiling\s+\S+\.(?:cpp|cc|cxx|java|kt|rs)', context_text):
                return None  # Could be code-caused — do not claim infra
        return RuleVerdict(
            rule_name="BUILD_OOM_KILLED",
            causal_proof=(
                "OS/container OOM killer terminated the process. "
                "Memory limits are CI infrastructure config, "
                "not addressable by code changes."
            ),
            counterexample=(
                "Code cannot set build node memory limits — "
                "these are CI infrastructure configuration."
            ),
            matched_signal="oom-kill",
        )
