# P0.1.19: Remote State Integrity Negative Tests Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `322999176dc9e888041a25ce04d55b24abc991a4`
Base main: `e629bfc568c086d05d5992b0cc811bc08ef3508c`

## 1. Code changes

`push_state()` now:

- validates top-level object and `tasks` object;
- requires target task record object;
- checks optional task_id field against the map key;
- requires identity string fields and exact source/artifact/base/branch match;
- rejects status outside `STATUSES`;
- rejects status rollback;
- if local `published_sha`/`pr_url` exists, remote must retain it;
- requires PR URL for REVIEW_PENDING;
- rejects rev-list command failure or empty output;
- validates each follow-up commit as state-only.

No force-push.

## 2. Verified

The four fresh-clone CLI tests still pass:

```text
test_publishing_state_push_accepted_client_error_fresh_clone      PASSED
test_publishing_state_push_rejected_fresh_clone                   PASSED
test_review_pending_state_push_rejected_fresh_clone               PASSED
test_review_pending_state_push_accepted_client_error_fresh_clone  PASSED
```

```text
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1424 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_UNMODIFIED: YES
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
```

## 3. NOT_VERIFIED

No new remote-advanced ancestry CLI test and no remote JSON negative CLI tests
were added in this round. These remain NOT_VERIFIED:

```text
REMOTE_ANCESTRY_BRANCH_EXERCISED: NOT_VERIFIED
REMOTE_JSON_NEGATIVE_CASES: NOT_VERIFIED
REMOTE_TASK_IDENTITY_VALIDATION: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
REMOTE_STATE_ROLLBACK_BLOCKED: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
PUBLISHED_SHA_REMOVAL_BLOCKED: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
PR_URL_REMOVAL_BLOCKED: CODE_IMPLEMENTED_NOT_INTEGRATION_TESTED
REMOTE_UNKNOWN_COMMIT_BLOCKED: NOT_VERIFIED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
REV_LIST_FAILURE_CLOSED: CODE_IMPLEMENTED_NOT_TESTED
```

Code presence is not reported as test success.

## 4. CI

Full CI: **1424 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44221398347
