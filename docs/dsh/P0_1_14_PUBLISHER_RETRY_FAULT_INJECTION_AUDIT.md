# P0.1.14: Publisher Retry State Machine and Fault Injection

> Historical audit; superseded by P0.1.15. HEAD/CI here are not current.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `6bd0a5c2843050d54ac1a6e318f7d2046b5ad8f1`
Base main: `b558f88337f91377472129ebfb5434acd4d70be0`
Status: **PARTIAL — only listed CLI scenarios are verified**

## 1. State machine

- `FAIL` is no longer a blanket terminal state;
- `REVIEW_PENDING` and `PASS` remain terminal;
- stable recoverable reasons:
  `BUSINESS_PUSH_FAILED`, `PUBLISHING_STATE_PUSH_FAILED`,
  `STATE_PERSIST_FAILED`, `PR_QUERY_FAILED`, `PR_CREATE_FAILED`;
- READY/MULTIPLE PR remain BLOCKED with stable reasons;
- business push failure stores `published_sha` and PUBLISHING state;
- state-push failure preserves the original reason and adds
  `state_persist_failed: true`;
- retries verify source SHA and artifact digest before continuing.

## 2. Real CLI tests

Temporary bare remote + mock gh, actual Publisher CLI:

- `test_business_push_rejected_then_retry`: pre-receive rejects business push,
  state remains PUBLISHING/BUSINESS_PUSH_FAILED; retry pushes once, creates one
  Draft PR, one business commit.
- `test_pr_query_failure_retry`: first query failure -> PUBLISHING; retry
  creates one Draft.
- `test_pr_create_failure_retry`: first create failure -> PUBLISHING; retry
  succeeds.
- `test_draft_pr_modes`: existing Draft reuse, Ready blocked, multiple blocked,
  query failure, create failure.

## 3. Verified status

```text
BUSINESS_PUSH_REJECTED_RETRY_TESTED: PASSED
PR_QUERY_FAILURE_RETRY_TESTED: PASSED
PR_CREATE_FAILURE_RETRY_TESTED: PASSED
DRAFT_REUSE_IDEMPOTENT: PASSED
SINGLE_BUSINESS_COMMIT_ENFORCED: PASSED
SINGLE_DRAFT_PR_ENFORCED: PARTIAL
UNKNOWN_COMMIT_BLOCKED: HELPER_TESTED_NOT_CLI
```

## 4. NOT_VERIFIED

```text
BUSINESS_PUSH_ACCEPTED_CLIENT_ERROR_RETRY_TESTED: NOT_VERIFIED
PUBLISHING_CRASH_RECOVERY_TESTED: NOT_VERIFIED
APPLY_BEFORE_COMMIT_RECOVERY_TESTED: NOT_VERIFIED
BUSINESS_COMMIT_BEFORE_PUSH_RECOVERY_TESTED: NOT_VERIFIED
PUSH_BEFORE_PR_RECOVERY_TESTED: NOT_VERIFIED
DRAFT_BEFORE_STATE_PERSIST_RECOVERY_TESTED: NOT_VERIFIED
STATE_PUSH_FAILURE_TESTED: NOT_VERIFIED
STATE_PUSH_AMBIGUITY_TESTED: NOT_VERIFIED
```

No accepted-but-client-error push test, no full PUBLISHING crash windows, no
state ambiguity test. The Publisher is not claimed as fully crash-recoverable.

## 5. CI and main

Full CI: **1419 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44129844517

Fetched current `origin/main`:

```text
b558f88337f91377472129ebfb5434acd4d70be0
```

Normal merge; no force-push, no main change.
