# P0.1.23: Remote Ancestry and State Integrity Tests Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `f3a86b905839ce42a3908fb393e4532dd25e185f`
Base main: `18cfb1869d08106dd382e7acfde803287140793f`

## 1. Results

- remote-advanced two-clone positive test implemented, but XFAIL:
  `test_state_push_client_error_remote_advanced_contains_commit`;
- remote JSON negative tests implemented for malformed JSON, top array,
  tasks missing, task missing, identity mismatch, bad status, missing PR URL;
- `push_state(force_remote_check=True)` test hook used to exercise the
  remote-advanced branch;
- four old fresh-clone tests still pass;
- transition matrix and URL/SHA unit tests pass.

## 2. Status

```text
REMOTE_ANCESTRY_BRANCH_EXERCISED: NOT_VERIFIED (xfail)
REMOTE_JSON_NEGATIVE_CASES: PARTIAL (7 cases passed; full list not covered)
REMOTE_TASK_IDENTITY_VALIDATION: PARTIAL
REMOTE_STATE_ROLLBACK_BLOCKED: NOT_VERIFIED
PUBLISHED_SHA_BRANCH_REACHABILITY: NOT_VERIFIED
FETCH_FAILURE_CLOSED: NOT_VERIFIED
SHOW_FAILURE_CLOSED: NOT_VERIFIED
REV_LIST_FAILURE_CLOSED: NOT_VERIFIED
MERGE_BASE_FAILURE_CLOSED: NOT_VERIFIED
CAT_FILE_FAILURE_CLOSED: NOT_VERIFIED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1445 passed, 1 skipped, 1 xfailed)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (18cfb186)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 3. NOT_VERIFIED

The positive remote-advanced branch test is XFAIL, not PASSED. Git command
failure injection and unknown-commit fresh-clone CLI tests were not added.
The full remote JSON negative matrix (published_sha removal/replacement/format,
pr_url replacement/format, rollback, merge/copy/empty follow-ups) is not
covered.

## 4. CI

Full CI: **1445 passed, 1 skipped, 1 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44233923172
