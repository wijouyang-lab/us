# P0.1.21: Publisher State Machine Correction Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `b5bf26697edf22ebb08d617c3e31ab34253b96e3`
Base main: `95b8dae8105dab8d18daaef88823779fa3e07084`

## 1. State transitions

- removed `STATE_RANK` gate;
- legal statuses come from `STATUSES`;
- exact transition matrix for all 8 statuses;
- FAIL -> FAIL, PUBLISHING -> FAIL, RUNNING -> FAIL allowed;
- FAIL -> PUBLISHING/RUNNING rejected;
- PASS/REVIEW_PENDING rollback rejected;
- BLOCKED -> PUBLISHING requires recoverable reason.

Tests: `tests/test_publisher_transitions.py`, complete 8x8 matrix.

## 2. URL and SHA

- URL parsed with `urllib.parse`; requires http(s), hostname and a dot;
- rejects `https://`, `https://?x`, non-string/empty;
- `published_sha` format and Git commit existence/ancestry checked in
  `push_state()`.

## 3. Status

```text
COMPLETE_STATE_TRANSITION_MATRIX: PASSED (unit matrix)
FAIL_STATE_TRANSITIONS: PASSED
STRICT_URL_VALIDATION: PASSED (unit)
PUBLISHED_SHA_FORMAT_VALIDATION: PASSED (unit)
PUBLISHED_SHA_BRANCH_REACHABILITY: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
REMOTE_ANCESTRY_BRANCH_EXERCISED: NOT_VERIFIED
REMOTE_JSON_NEGATIVE_CASES: NOT_VERIFIED
REMOTE_TASK_IDENTITY_VALIDATION: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
REMOTE_STATE_ROLLBACK_BLOCKED: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
REV_LIST_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
FETCH_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1438 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (95b8dae8)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. NOT_VERIFIED

No remote-advanced ancestry integration test, remote JSON negative CLI cases,
Git command failure injection, or unknown-commit fresh-clone CLI test was added.
Code checks are not reported as integration-tested.

## 5. CI

Full CI: **1438 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44228415173
