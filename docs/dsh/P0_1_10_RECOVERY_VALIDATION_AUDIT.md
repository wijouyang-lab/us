# P0.1.10: Publisher Recovery Tests and Strict Agent-Result Audit

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
HEAD: `91e54368d2ffc99fc9d0aa2d80e6f98ec4ba2e8f`
Base main: `88eeee5a8b62bddcff74485d666268c5ae8083fd`
Status: **CODE_SECURITY_TESTED — PARTIAL SCENARIO COVERAGE**

## 1. Strict manifest fields

`timed_out` and `tests_returncode` are now required:

- `timed_out` must be exactly `bool` and `False`;
- `tests_returncode` must be exactly `int` (not bool) and `0`;
- missing fields fail;
- wrong types fail;
- nonzero exit fails.

Tests:

- `test_missing_timed_out_rejected`
- `test_wrong_tests_returncode_type_rejected`

All checks run before business file changes.

## 2. Artifact root ancestors

Code walks every ancestor, rejects symlinks and broken symlinks before mkdir or
copy. Manifest and workspace are checked as regular directories.

Tests cover root symlink, workspace symlink, target symlink, traversal, `.git`,
and manifest schema. **Parent-ancestor symlink tests were not added in this
round**, so that specific status is NOT_VERIFIED.

## 3. Publisher recovery

Implementation now:

- stores `agent_source_sha`, `base_commit_sha`, `artifact_digest`, `published_sha`, attempts/history;
- detects a business commit by `artifact <digest>` in the commit message;
- distinguishes state-only commits from business commits;
- skips re-apply when the business commit already exists;
- blocks on unrecognized branch changes;
- reuses only confirmed Draft PRs;
- verifies URL, isDraft, head, base after create;
- checks state push results and records `STATE_PERSIST_FAILED`.

No integration test was added for the seven crash windows in this round. Those
statuses are NOT_VERIFIED below.

## 4. Draft PR idempotency

Code handles:

- no PR -> create Draft + verify;
- one Draft -> reuse;
- one Ready -> BLOCKED;
- multiple -> BLOCKED;
- query failure -> BLOCKED;
- create failure -> FAIL.

Only the no-PR create + terminal skip path is exercised by the existing
integration test. Draft reuse, Ready, multiple and query-failure tests are
NOT_VERIFIED.

## 5. State persistence

`push_state` catches command exceptions and returns failure; `mark` reports
`STATE_PERSIST_FAILED:REMOTE_NOT_SAVED` and saves local evidence. Callers now
continue only with explicit status, but not every failure window has an
integration test. State push failure/recovery is NOT_VERIFIED.

## 6. Main sync

Fetched current `origin/main`:

```text
88eeee5a8b62bddcff74485d666268c5ae8083fd
```

Normal merge used; no force-push, no main change.

## 7. CI

Local targeted: **39 passed, 3 skipped** (before final doc commit; Windows
platform skips).

Full CI: **1396 passed, 1 skipped**.

Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44114182392

## 8. Status table

```text
MANIFEST_TIMED_OUT_STRICTLY_VALIDATED
MANIFEST_TEST_RETURN_CODE_STRICTLY_VALIDATED
PUBLISHING_CRASH_RECOVERY_TESTED: NOT_VERIFIED
BUSINESS_COMMIT_RECOVERY_TESTED: NOT_VERIFIED
DRAFT_PR_REUSE_TESTED: NOT_VERIFIED
NON_DRAFT_PR_BLOCKED_TESTED: NOT_VERIFIED
MULTIPLE_PR_BLOCKED_TESTED: NOT_VERIFIED
PR_QUERY_FAILURE_TESTED: NOT_VERIFIED
STATE_PUSH_FAILURE_TESTED: NOT_VERIFIED
STATE_RECOVERY_TESTED: NOT_VERIFIED
ARTIFACT_ROOT_ANCESTOR_SYMLINK_TESTED: NOT_VERIFIED
PUBLISHER_RETRY_IDEMPOTENT_TESTED: PARTIAL (terminal skip only)
DSH_INSTALL_CI_VERIFIED
FULL_CI_PASSED
MAIN_SYNCED_TO_CURRENT_ORIGIN
DSH_CLOUD_TASK_NOT_EXECUTED
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
CHATGPT_REVIEW_PENDING
```

## 9. Remaining blockers

1. main protection is false;
2. no cloud DSH model task;
3. no real ChatGPT PR review;
4. crash-window/PR/state integration tests are still missing;
5. full branch-protection policy needs human verification;
6. auto-merge disabled.
