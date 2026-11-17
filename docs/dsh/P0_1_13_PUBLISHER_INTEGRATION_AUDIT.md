# P0.1.13: Publisher CLI Integration and Strict Recovery Tests

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `02acc3cb28d3d7547ff144edcc96070531983c82`
Base main: `abce6a67d4b8c5662edf5637d5f05ebfe27833e7`

## 1. Strict recovery tests

- state commit subject is exact:
  `automation: persist task state [skip ci]`;
- empty state commits are rejected;
- rename and copy statuses are rejected;
- transient add-then-delete files are rejected by per-commit path checks;
- net-empty non-state commits are rejected.

Tests:

```text
test_recovery_rejects_transient_forbidden_file
test_state_only_rejects_non_state_commit_even_if_net_empty
test_recovery_rejects_empty_state_commit
test_recovery_rejects_invalid_state_subject
test_recovery_rejects_rename_paths
test_recovery_rejects_copy_paths
test_recovery_allows_expected_state_commits
test_recovery_blocks_unknown_commit_after_artifact
test_recovery_rejects_unrecognized_file_changes
test_recovery_rejects_unexpected_merge_commit
```

## 2. Publisher CLI Draft PR modes

`test_publisher_cli_modes.py` runs the real Publisher CLI against a temporary
bare remote and mock gh:

```text
EXISTING_DRAFT_REUSE      -> REVIEW_PENDING, no create
READY_PR_BLOCKED          -> BLOCKED, no create
MULTIPLE_PR_BLOCKED       -> BLOCKED, no create
PR_QUERY_FAILURE_BLOCKED  -> BLOCKED, no create
PR_CREATE_FAILURE         -> FAIL, one create attempt
```

PR creation counts are asserted from the mock gh log, not just final state.
Linux CI passed all modes.

## 3. Dry-run semantics

Input description now states:

```text
Run DSH and generate artifacts without publishing (still makes model calls)
```

Publisher is gated by `if: inputs.dry_run == false`; Agent remains read-only.
Dry-run is a publishing gate, not a no-model or zero-API-cost mode.
No cloud dry-run task was triggered.

## 4. Unverified

Full Publisher CLI crash-window recovery (PUBLISHING state commit, business
commit before push, push succeeded/no PR, state push ambiguity) and state push
failure/ambiguity tests remain NOT_VERIFIED. Only the Draft PR modes and helper
range checks are covered.

## 5. Main sync

Fetched current `origin/main`:

```text
abce6a67d4b8c5662edf5637d5f05ebfe27833e7
```

Normal merge, no force-push, no main change.

## 6. CI

Full CI: **1416 passed, 1 skipped**.

Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44124822330

## 7. Status

```text
TRANSIENT_FORBIDDEN_FILE_TEST_VALID
EMPTY_NET_DIFF_BLOCKED
RECOVERY_COMMIT_SUBJECT_STRICT
RECOVERY_RENAME_COPY_TESTED
PUBLISHING_CRASH_RECOVERY_TESTED: NOT_VERIFIED
BUSINESS_COMMIT_RECOVERY_TESTED: NOT_VERIFIED
STATE_PUSH_FAILURE_TESTED: NOT_VERIFIED
STATE_PUSH_AMBIGUITY_TESTED: NOT_VERIFIED
STATE_RECOVERY_IDEMPOTENT: NOT_VERIFIED
DRAFT_PR_REUSE_TESTED
READY_PR_BLOCKED_TESTED
MULTIPLE_PR_BLOCKED_TESTED
PR_QUERY_FAILURE_TESTED
PR_CREATE_FAILURE_TESTED
PUBLISHER_RETRY_IDEMPOTENT_TESTED: PARTIAL
DRY_RUN_PUBLISH_GATE_TESTED
DRY_RUN_MODEL_CALL_SEMANTICS_DOCUMENTED
DSH_INSTALL_CI_VERIFIED
FULL_CI_PASSED
MAIN_SYNCED_TO_CURRENT_ORIGIN
DSH_CLOUD_TASK_NOT_EXECUTED
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
CHATGPT_REVIEW_PENDING
```
