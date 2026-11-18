# P0.1.16: Remote State Ambiguity and Draft Terminal Recovery Audit

> Historical audit; superseded by P0.1.17.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `5929c1dd0f0ef91de42c6dbdb066788cae9af5ca`
Base main: `639ef43a32157f031e110bc9b29d30ba1f13aa31`
Status: **PARTIAL — remote ref verification implemented; ambiguity CLI tests NOT_VERIFIED**

## 1. State persistence semantics

`push_state()` now:

- writes local state;
- commits it;
- pushes;
- if push returns non-zero, checks `git ls-remote origin refs/heads/<branch>`;
- treats the push as successful only when the remote ref exactly equals the
  local state commit.

This separates:

```text
LOCAL_STATE
REMOTE_STATE
REMOTE_GIT_HEAD
```

A local REVIEW_PENDING is not treated as terminal unless the remote state
commit is confirmed.

## 2. Verified

- ambiguous push detection is implemented and compiles;
- existing fresh-clone business push recovery from P0.1.15 remains;
- stable retry reasons and Draft reuse rules remain;
- per-commit state validation remains;
- Full CI passes.

## 3. NOT_VERIFIED

The four required real CLI ambiguity/fresh-clone tests were not implemented:

```text
test_state_push_accepted_but_client_error_fresh_clone: NOT_VERIFIED
test_publishing_state_push_rejected_fresh_clone: NOT_VERIFIED
test_review_pending_state_push_rejected_fresh_clone: NOT_VERIFIED
test_review_pending_state_push_accepted_client_error_fresh_clone: NOT_VERIFIED
```

No git wrapper was used to return false client errors after a real accepted
push. No fresh clone was used for these state-push scenarios.

Other NOT_VERIFIED:

```text
STATE_PUSH_ACCEPTED_CLIENT_ERROR_FRESH_CLONE
PUBLISHING_STATE_PUSH_REJECTED_FRESH_CLONE
REVIEW_PENDING_STATE_PUSH_REJECTED_FRESH_CLONE
REVIEW_PENDING_STATE_PUSH_ACCEPTED_CLIENT_ERROR_FRESH_CLONE
DRAFT_BEFORE_STATE_PERSIST_FRESH_CLONE
UNKNOWN_COMMIT_BLOCKED: HELPER_TESTED_NOT_CLI
```

## 4. Main sync

Fetched current `origin/main`:

```text
639ef43a32157f031e110bc9b29d30ba1f13aa31
```

Normal merge; no force-push, no main change.

## 5. CI

Full CI: **1420 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44139367351
