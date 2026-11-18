# P0.1.17: Remote State Fresh-Clone Verification Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `7ad4f1f17c1a6763403c28b25f2329b25b8c016f`
Base main: `97b430409aa918a8c843f3685a324c3754b79982`

## 1. State push verification

`push_state()` now:

- exact remote ref equality -> success;
- if remote contains the local state commit as an ancestor, fetch and verify
  `automation/state/tasks.json` exists and is valid JSON before accepting;
- unrelated/no remote branch/query failure -> not persisted;
- no force-push.

## 2. Real fresh-clone CLI tests

`tests/test_publisher_state_fresh_clone.py`:

```text
test_publishing_state_push_accepted_client_error_fresh_clone  PASSED
test_publishing_state_push_rejected_fresh_clone               PASSED
test_review_pending_state_push_rejected_fresh_clone           PASSED
test_review_pending_state_push_accepted_client_error_fresh_clone PASSED
```

Each test:

- runs actual Publisher CLI;
- destroys the first clone and clones the bare remote again;
- checks remote HEAD and remote tasks.json;
- asserts one business commit and one Draft PR;
- verifies no duplicate PR creation where applicable.

## 3. Status

```text
PUBLISHING_STATE_ACCEPTED_CLIENT_ERROR_FRESH_CLONE: PASSED
PUBLISHING_STATE_REJECTED_FRESH_CLONE: PASSED
REVIEW_PENDING_STATE_REJECTED_FRESH_CLONE: PASSED
REVIEW_PENDING_STATE_ACCEPTED_CLIENT_ERROR_FRESH_CLONE: PASSED
REMOTE_ANCESTRY_VERIFICATION: PASSED
REMOTE_STATE_CONTENT_VERIFICATION: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
ONE_DRAFT_PR_ENFORCED: PASSED
UNKNOWN_COMMIT_BLOCKED: HELPER_TESTED_NOT_CLI
```

`UNKNOWN_COMMIT_BLOCKED` remains helper-tested, not a fresh-clone CLI test.

## 4. Main sync

Fetched current `origin/main`:

```text
97b430409aa918a8c843f3685a324c3754b79982
```

Normal merge; no force-push, no main change.

## 5. CI

Full CI: **1424 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44216464833
