# P0.1.12: Dry-run Gate and Per-Commit Recovery Audit

> Historical audit; superseded by P0.1.13.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `2ac54babcb3597ac9a8d02131f3acc1bf2a0719f`
Base main: `8896d8dac761e82c953f2d3088975a6499d2310e`

## 1. Dry-run gate

- Publisher job now has `if: inputs.dry_run == false`;
- no Publisher step runs on dry_run=true;
- Agent still runs and emits the artifact;
- `DRY_RUN_COMPLETE` step reports no publish;
- preflight allows dry-run when main protection is unverified, but blocks
  non-dry-run execution;
- `max_attempts` input removed because it was not wired into execution.

Tests:

```text
test_dry_run_gate_and_no_max_attempts
test_dry_run_workflow_gate_and_no_max_attempts
```

No actual GitHub dry-run task was triggered; this is workflow/static validation,
not cloud execution.

## 2. Per-commit recovery

`recovery_range_ok()` and `state_only_ok()` now inspect every commit:

- exactly one parent;
- no merge commit;
- subject must be `automation: persist task state`;
- per-commit `diff-tree` against parent;
- reject rename/copy status;
- every changed path must be `automation/state/`.

Tests:

```text
test_recovery_allows_expected_state_commits
test_recovery_blocks_unknown_commit_after_artifact
test_recovery_rejects_unrecognized_file_changes
test_recovery_rejects_unexpected_merge_commit
test_recovery_rejects_transient_forbidden_file
test_state_only_rejects_non_state_commit_even_if_net_empty
```

## 3. Manifest and artifact

Strict `timed_out`/`tests_returncode` cases and artifact root/workspace/manifest
symlink tests remain. Linux CI executes symlink tests.

## 4. Not verified

No full bare-remote Publisher CLI crash-window integration suite, no Draft PR
reuse/Ready/multiple/query-failure tests, and no state push failure/ambiguity
recovery tests. These remain NOT_VERIFIED.

## 5. Main sync

Fetched current `origin/main`:

```text
8896d8dac761e82c953f2d3088975a6499d2310e
```

Normal merge, no force-push, no main change.

## 6. CI

Full CI: **1407 passed, 1 skipped**.

Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44121279115

## 7. Status

```text
DRY_RUN_TRUE_NEVER_PUBLISHES: WORKFLOW_GATE_TESTED_NOT_CLOUD_RUN
DRY_RUN_FALSE_REQUIRES_PREFLIGHT: WORKFLOW_GATE_TESTED
WORKFLOW_DRY_RUN_GATE_TESTED
MAX_ATTEMPTS_INPUT_ACCURATE: REMOVED
RECOVERY_EACH_COMMIT_VALIDATED
TRANSIENT_FORBIDDEN_FILES_BLOCKED
STATE_ONLY_EACH_COMMIT_VALIDATED
PUBLISHING_CRASH_RECOVERY_TESTED: NOT_VERIFIED
BUSINESS_COMMIT_RECOVERY_TESTED: NOT_VERIFIED
STATE_PUSH_FAILURE_TESTED: NOT_VERIFIED
STATE_PUSH_AMBIGUITY_TESTED: NOT_VERIFIED
DRAFT_PR_REUSE_TESTED: NOT_VERIFIED
NON_DRAFT_PR_BLOCKED_TESTED: NOT_VERIFIED
MULTIPLE_PR_BLOCKED_TESTED: NOT_VERIFIED
PR_QUERY_FAILURE_TESTED: NOT_VERIFIED
PUBLISHER_RETRY_IDEMPOTENT_TESTED: PARTIAL
ARTIFACT_ROOT_ANCESTOR_SYMLINK_TESTED: LINUX_CI
DSH_INSTALL_CI_VERIFIED
FULL_CI_PASSED
MAIN_SYNCED_TO_CURRENT_ORIGIN
DSH_CLOUD_TASK_NOT_EXECUTED
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
CHATGPT_REVIEW_PENDING
```
