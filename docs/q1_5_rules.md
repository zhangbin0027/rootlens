# Q1.5 Rules — Causal Impossibility Gate

## Admission Criterion

A rule may enter Q1.5 **ONLY** if the answer to this question is "no":

> "Can ANY plausible code change trigger this exact failure?"

## Anti-Patterns (MUST NOT enter Q1.5)

| Pattern            | Why Rejected                              |
| ------------------ | ----------------------------------------- |
| Test timeout       | Code can introduce infinite loops         |
| Compile error      | Code directly causes compilation failures |
| Repo sync conflict | Code can conflict with another change     |
| Flaky test         | Code can trigger race conditions          |
| Missing dependency | Code can remove a dependency declaration  |

## Rules (10 total, hardcoded Python)

### Rule 1: PRE_APPLY_FAILURE
- **Pattern**: `MANIFEST_INIT_ERROR`
- **Counterexample**: Code change not yet applied when error fires
- **Causal Proof**: Error in repo initialization phase, before code checkout

### Rule 2: VCS_TOOL_INTERNAL_FAILURE
- **Pattern**: `suppress-dest-branch` + error context, `repo: command not found`
- **Counterexample**: Code cannot modify VCS tool binary or its CLI
- **Causal Proof**: VCS tool errors originate in the CI toolchain layer

### Rule 3: ENVIRONMENT_UNREACHABLE
- **Pattern**: `bazel/output_user_root/` + `No such file or directory`
- **Counterexample**: Code cannot modify CI node local paths
- **Causal Proof**: Build cache is CI node physical state

### Rule 4: DISK_FULL
- **Pattern**: `No space left on device`
- **Counterexample**: Code cannot alter disk capacity on build node
- **Causal Proof**: Disk is build node resource constraint at OS level

### Rule 5: BUILD_NODE_OFFLINE
- **Pattern**: `slave went offline`, `node is offline`, `ChannelClosedException`
- **Counterexample**: Code cannot crash a build node
- **Causal Proof**: Node availability is infrastructure state

### Rule 6: GIT_REMOTE_UNREACHABLE
- **Pattern**: `Could not read from remote repository`, `Connection refused` (git context)
- **Counterexample**: Code cannot affect network infrastructure
- **Causal Proof**: Git remote is external network dependency

### Rule 7: ARTIFACT_UPLOAD_FAILURE
- **Pattern**: `upload failed`, `put object failed`
- **Counterexample**: Code cannot affect artifact storage service
- **Causal Proof**: Storage service is external post-build dependency

### Rule 8: FILE_TRANSFER_FAILURE
- **Pattern**: `scp: connection lost`, `ssh: connect to host`, `connection timed out` (SSH/SCP/git context only)
- **Guard**: `connection timed out` only fires when SSH/SCP/git context is present in the log. Without SSH context, it could be a test-level HTTP timeout caused by code (e.g., too-short timeout constant).
- **Counterexample**: Code cannot affect SSH infrastructure
- **Causal Proof**: SSH/SCP is CI network layer

### Rule 9: GIT_RESET_FAILURE
- **Pattern**: `git reset --hard failed`, `unable to reset`, `during git-reset`
- **Guard**: Excludes cherry-pick/revert/conflict context where reset failure may be caused by code change conflicts.
- **Counterexample**: Code cannot corrupt CI workspace git state
- **Causal Proof**: Git reset runs BEFORE code checkout

### Rule 10: BUILD_OOM_KILLED
- **Pattern**: `oom-kill` or `oom_kill` (OS/container OOM killer signal only)
- **Excluded**: `Killed` alone (ambiguous — could be timeout SIGKILL), `Out of memory` alone (ambiguous — could be compiler OOM from template expansion)
- **Counterexample**: Code cannot set build node memory limits
- **Causal Proof**: Memory limits are CI infrastructure config

## Rule Output Contract

Every Q1.5 rule returns a `RuleVerdict`:
```python
@dataclass
class RuleVerdict:
    rule_name: str        # identifier
    causal_proof: str     # WHY CR cannot cause this
    counterexample: str   # what would need to be true for CR to cause this
    matched_signal: str   # the specific log line that triggered
```
