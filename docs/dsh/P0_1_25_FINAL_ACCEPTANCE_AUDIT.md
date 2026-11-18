# P0.1.25: Final State Integrity Acceptance Audit

> Historical audit; superseded by P0.1.26.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `042834d667b6bc9f9c531aeefcf7b94564e0429d`
Base main: `13fbfb521fb03e55cbd31e658f2450aa23cf4a8d`

## 1. PASSED

- positive remote-advanced two-clone ancestry test;
- 19 remote JSON/identity negative cases:
  malformed, top array, tasks missing, task missing, task_id mismatch,
  artifact/source/base/branch/base_branch mismatch, bad status, rollback,
  published_sha deleted/replaced/bad format/missing, pr_url replaced/bad
  format/missing (7 original + new cases);
- git failure injection: fetch, show, rev-list, merge-base;
- four fresh-clone state tests;
- transition matrix and URL/SHA unit tests.

## 2. NOT_VERIFIED

```text
published_sha exists but not in remote history
cat-file failure injection
merge/empty/transient/rename/copy follow-up commits
fork-history rejection
unknown-commit fresh-clone CLI blocked
```

These were not added in this round and are not claimed as passed.

## 3. Status

```text
REMOTE_ANCESTRY_BRANCH_EXERCISED: PASSED
REMOTE_JSON_NEGATIVE_CASES: PARTIAL (19 cases passed; full matrix incomplete)
REMOTE_TASK_IDENTITY_VALIDATION: PARTIAL
REMOTE_STATE_ROLLBACK_BLOCKED: PASSED
PUBLISHED_SHA_FORMAT_VALIDATED: PASSED
PUBLISHED_SHA_BRANCH_REACHABILITY: NOT_VERIFIED
PR_URL_FORMAT_VALIDATED: PASSED
FETCH_FAILURE_CLOSED: PASSED
SHOW_FAILURE_CLOSED: PASSED
REV_LIST_FAILURE_CLOSED: PASSED
MERGE_BASE_FAILURE_CLOSED: PASSED
CAT_FILE_FAILURE_CLOSED: NOT_VERIFIED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1462 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (13fbfb52)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. CI

Full CI: **1462 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44238811821
