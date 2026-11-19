# P0.1.18: Remote State Integrity Audit

> Historical audit; superseded by P0.1.19.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `e841d5aa7e00fa359151ba860d0df53493dea150`
Base main: `5b056794896f866d67fd649763f7315ea358cbd7`

## 1. Code changes

`push_state()` now:

- fetches remote when push returns non-zero;
- requires local state commit ancestor of remote HEAD;
- parses remote `automation/state/tasks.json` with `json.loads()`;
- requires target task_id;
- verifies agent_source_sha, artifact_digest, base_commit_sha, branch,
  base_branch;
- rejects status rollback;
- rejects conflicting published_sha or PR URL;
- validates every follow-up commit as an exact state-only commit.

## 2. Verified

The four P0.1.17 fresh-clone CLI tests still pass:

```text
test_publishing_state_push_accepted_client_error_fresh_clone  PASSED
test_publishing_state_push_rejected_fresh_clone               PASSED
test_review_pending_state_push_rejected_fresh_clone           PASSED
test_review_pending_state_push_accepted_client_error_fresh_clone PASSED
```

Each uses a new clone and checks one business commit / one Draft PR.

```text
REMOTE_JSON_FULLY_PARSED: CODE_IMPLEMENTED
TARGET_TASK_RECORD_VERIFIED: CODE_IMPLEMENTED
REMOTE_STATE_IDENTITY_MATCHED: CODE_IMPLEMENTED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
ONE_DRAFT_PR_ENFORCED: PASSED
FULL_CI: PASSED (1424 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
```

## 3. NOT_VERIFIED

No real ancestry-advanced branch test, no malformed/empty/mismatched remote
JSON CLI tests, no rollback test, and no unknown-commit fresh-clone CLI test
were added. These remain NOT_VERIFIED:

```text
REMOTE_ANCESTRY_BRANCH_EXERCISED: NOT_VERIFIED
REMOTE_STATE_JSON_NEGATIVE_CASES: NOT_VERIFIED
REMOTE_STATE_ROLLBACK_BLOCKED: NOT_VERIFIED
REMOTE_UNKNOWN_COMMIT_BLOCKED: NOT_VERIFIED
UNKNOWN_COMMIT_CLI_BLOCKED: NOT_VERIFIED
```

Content validation is implemented but not independently exercised beyond the
four existing fresh-clone tests.

## 4. Main and CI

Current `origin/main`:

```text
5b056794896f866d67fd649763f7315ea358cbd7
```

Normal merge, no force-push, no main change.

Full CI: **1424 passed, 1 skipped**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44218839516
