# P0.1.11: Publisher Recovery, Unknown Commit and Fault-Injection Audit

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
HEAD: `dfd62af5a7b61f30c1ab12d1192205217bda0e18`
Base main: `a0c7bb0a6b6a2d1f4d40e0d7562f165ed00cf553`

## 1. Code fixes

- PUBLISHING state push failure now records `PUBLISHING_STATE_PUSH_FAILED`;
  the next run treats this BLOCKED reason as recoverable, not terminal.
- Recovery validates stored `agent_source_sha` and artifact digest.
- A found business commit is accepted only if every following commit is an
  expected `automation: persist task state` commit, has no merge commit, and
  changes only `automation/state/`.
- Unexpected file changes, merge commits and unknown commits after the artifact
  commit return BLOCKED.

## 2. Tests added

- `test_recovery_allows_expected_state_commits`
- `test_recovery_blocks_unknown_commit_after_artifact`
- `test_recovery_rejects_unrecognized_file_changes`
- `test_recovery_rejects_unexpected_merge_commit`
- strict invalid manifest matrix (`timed_out`/`tests_returncode`)
- root parent symlink, workspace symlink, manifest symlink tests (POSIX)

Local result before final CI:

```text
tests/test_dsh_publisher.py + tests/test_publisher_recovery.py
11 passed, 5 skipped
```

## 3. Verification status

```text
MANIFEST_TIMED_OUT_STRICTLY_VALIDATED
MANIFEST_TEST_RETURN_CODE_STRICTLY_VALIDATED
UNKNOWN_COMMIT_AFTER_ARTIFACT_BLOCKED
MANIFEST_ALL_INVALID_CASES_TESTED
ARTIFACT_ROOT_ANCESTOR_SYMLINK_TESTED: PASSED IN LINUX CI
PUBLISHING_PUSH_FAILURE_RECOVERABLE: NOT_VERIFIED
STATE_PUSH_AMBIGUITY_RECOVERABLE: NOT_VERIFIED
STATE_RECOVERY_IDEMPOTENT: NOT_VERIFIED
BUSINESS_COMMIT_RECOVERY_TESTED: NOT_VERIFIED
PUBLISHING_CRASH_RECOVERY_TESTED: NOT_VERIFIED
DRAFT_PR_REUSE_TESTED: NOT_VERIFIED
NON_DRAFT_PR_BLOCKED_TESTED: NOT_VERIFIED
MULTIPLE_PR_BLOCKED_TESTED: NOT_VERIFIED
PR_QUERY_FAILURE_TESTED: NOT_VERIFIED
PUBLISHER_RETRY_IDEMPOTENT_TESTED: PARTIAL
DSH_INSTALL_CI_VERIFIED
FULL_CI_PASSED: 1404 passed, 1 skipped
MAIN_SYNCED_TO_CURRENT_ORIGIN
DSH_CLOUD_TASK_NOT_EXECUTED
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
CHATGPT_REVIEW_PENDING
```

## 4. Not yet verified

The full seven crash-window integration tests, Draft reuse/non-Draft/multiple/
query-failure tests, and state push failure/recovery tests are still not
implemented. They must remain NOT_VERIFIED until actual temporary-remote tests
exist; code presence is not evidence.

## 5. Main sync

Fetched current `origin/main`:

```text
a0c7bb0a6b6a2d1f4d40e0d7562f165ed00cf553
```

Normal merge completed. No force-push, no main change.
