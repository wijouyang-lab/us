# P0.1.26: Final Security Acceptance Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `a2f487ef8678ca740bf72c8aae146389dfea75a1`
Base main: `4f951be66beff990ca117710be8c5dfae5a61f49`

## 1. PASSED

- task_id is required, non-empty string and must match exactly;
- remote negative cases task_id missing/mismatch pass;
- PR URL is restricted to `https://github.com/wijouyang-lab/us/pull/<positive int>`;
- external domain, other repo, issue, repo page, http and pull/0 rejected;
- cat-file failure injection passes;
- fetch/show/rev-list/merge-base failure injection passes;
- positive remote-advanced two-clone test passes;
- 19 remote JSON/identity cases pass;
- four fresh-clone tests pass;
- transition matrix and recovery tests pass.

## 2. NOT_VERIFIED

```text
published_sha exists but not in remote history
merge/empty/transient/rename/copy follow-up commits
fork-history rejection
unknown-commit fresh-clone CLI blocked
```

## 3. Status

```text
TASK_ID_STRICT: PASSED
PR_URL_REPOSITORY_STRICT: PASSED
REMOTE_ANCESTRY_BRANCH_EXERCISED: PASSED
REMOTE_JSON_NEGATIVE_CASES: PARTIAL (19 cases)
REMOTE_TASK_IDENTITY_VALIDATION: PARTIAL
PUBLISHED_SHA_BRANCH_REACHABILITY: NOT_VERIFIED
FETCH_FAILURE_CLOSED: PASSED
SHOW_FAILURE_CLOSED: PASSED
REV_LIST_FAILURE_CLOSED: PASSED
MERGE_BASE_FAILURE_CLOSED: PASSED
CAT_FILE_FAILURE_CLOSED: PASSED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1464 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (4f951be6)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. CI

Full CI: **1464 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44240937958
