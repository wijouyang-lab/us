# P0.1.15: Cross-Run Publisher Recovery Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `c81ea0958914bb54705b636ebd244ebeaa3fd8dc`
Base main: `a1f312426ef0f448f94cf6b37f52ade54f896a82`
Status: **PARTIAL — one fresh-clone scenario verified**

## 1. Fresh clone recovery

`test_business_push_rejected_then_fresh_clone_retry`:

- first Publisher CLI run reached PUBLISHING state and business commit;
- pre-receive rejected the business push after accepting the PUBLISHING state push;
- the original working clone was discarded;
- a clean clone was created from the bare remote and checked out at the
  remote `fix/t` state commit;
- the second Publisher CLI run used the same task_id and artifact;
- it recovered the PUBLISHING state, applied the artifact once, produced one
  business commit, pushed, and created one Draft PR.

Assertions:

```text
FRESH_CLONE_RECOVERY: PASSED
REMOTE_TASK_STATE_RECOVERABLE: PASSED
SINGLE_BUSINESS_COMMIT_ENFORCED: PASSED
SINGLE_DRAFT_PR_ENFORCED: PASSED (one create attempt in this scenario)
ARTIFACT_DIGEST_UNCHANGED: PASSED
```

Remote HEAD, remote state JSON, new clone initial HEAD, business commit count,
PR create count and final REVIEW_PENDING were checked in the test.

## 2. NOT_VERIFIED

```text
BUSINESS_PUSH_ACCEPTED_CLIENT_ERROR_FRESH_CLONE: NOT_VERIFIED
PUBLISHING_STATE_PUSH_REJECTED_FRESH_CLONE: NOT_VERIFIED
PUBLISHING_STATE_PUSH_AMBIGUITY_FRESH_CLONE: NOT_VERIFIED
REVIEW_PENDING_STATE_PUSH_REJECTED_FRESH_CLONE: NOT_VERIFIED
REVIEW_PENDING_STATE_PUSH_AMBIGUITY_FRESH_CLONE: NOT_VERIFIED
PR_QUERY_FAILURE_FRESH_CLONE: NOT_VERIFIED
PR_CREATE_FAILURE_FRESH_CLONE: NOT_VERIFIED
DRAFT_BEFORE_STATE_PERSIST_FRESH_CLONE: NOT_VERIFIED
APPLY_BEFORE_COMMIT_CRASH_RECOVERY: NOT_VERIFIED
BUSINESS_COMMIT_BEFORE_PUSH_CRASH_RECOVERY: NOT_VERIFIED
PUSH_BEFORE_PR_CRASH_RECOVERY: NOT_VERIFIED
UNKNOWN_COMMIT_BLOCKED: HELPER_TESTED_NOT_CLI
```

State-push rejection/ambiguity and PR retry tests currently run in one clone,
not a fresh clone. They are not claimed as cross-run verified.

## 3. State machine retained

- stable reason codes;
- REVIEW_PENDING/PASS terminal;
- source SHA + artifact digest checks;
- per-commit state-only validation;
- exact state subject, empty/rename/copy rejection;
- Draft reuse and Ready/multiple blocking.

## 4. Main sync

Fetched current `origin/main`:

```text
a1f312426ef0f448f94cf6b37f52ade54f896a82
```

Normal merge; no force-push, no main change.

## 5. CI

Full CI: **1420 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44136347681
