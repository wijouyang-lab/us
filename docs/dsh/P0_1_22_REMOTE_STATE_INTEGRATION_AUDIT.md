# P0.1.22: Remote State Integration Test Completion Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `217a065c40f1683ead9bbda5476fc31a08571769`
Base main: `a31fd552655e5e1dde862a81d362c88f1681fadb`

## 1. Unit-tested

- complete 8x8 state transition matrix;
- FAIL -> FAIL allowed, FAIL -> PUBLISHING/RUNNING rejected;
- PASS/REVIEW_PENDING rollback rejected;
- strict URL scheme/hostname/port validation;
- published_sha 40-hex format.

## 2. Code-implemented, not integration-tested

- remote tasks.json recursive ancestry/content validation;
- published_sha commit existence and remote-branch ancestry;
- fetch/show/rev-list/merge-base failure handling.

## 3. Status

```text
COMPLETE_STATE_TRANSITION_MATRIX: PASSED (unit)
REMOTE_ANCESTRY_BRANCH_EXERCISED: NOT_VERIFIED
REMOTE_JSON_NEGATIVE_CASES: NOT_VERIFIED
REMOTE_TASK_IDENTITY_VALIDATION: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
REMOTE_STATE_ROLLBACK_BLOCKED: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
PUBLISHED_SHA_FORMAT_VALIDATED: PASSED (unit)
PUBLISHED_SHA_BRANCH_REACHABILITY: CODE_IMPLEMENTED_NOT_TESTED
PR_URL_FORMAT_VALIDATED: PASSED (unit)
FETCH_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
SHOW_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
REV_LIST_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
MERGE_BASE_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1438 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (a31fd552)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. NOT_VERIFIED

No remote-advanced two-clone ancestry test, remote JSON negative CLI suite, Git
command failure injection, or unknown-commit fresh-clone CLI test was added in
this round. The code paths exist but are not reported as integration-tested.

## 5. CI

Full CI: **1438 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44230728806
