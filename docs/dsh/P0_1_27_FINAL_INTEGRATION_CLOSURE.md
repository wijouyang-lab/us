# P0.1.27: Final Integration Closure Audit

> Historical audit; superseded by P0.1.28.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `7661e77db89864ece74dc4f03aa7817f06c22128`
Base main: `e55750fddd5dae9f79da43610aeed8fc6f0231e0`

## 1. PASSED

- published_sha object exists but is not in the task branch history: rejected;
- follow-up commit checks with Clone A/B and bare remote:
  - valid state-only: accepted;
  - empty: rejected;
  - non-state file: rejected;
  - bad subject: rejected;
  - transient non-state: rejected;
  - merge commit: rejected;
  - rename: rejected;
- fork history: rejected;
- 20 remote JSON/task identity cases (including task_id missing/mismatch);
- task_id strict, PR URL strict;
- fetch/show/rev-list/merge-base/cat-file failure injection;
- four fresh-clone tests and recovery tests.

## 2. NOT_VERIFIED

```text
copy follow-up commit
unknown-commit fresh-clone Publisher CLI end-to-end
```

No copy case was added. The unknown-commit CLI test was not added.

## 3. Status

```text
PUBLISHED_SHA_OBJECT_NOT_IN_HISTORY: PASSED
FOLLOWUP_COMMIT_CHECKS: PARTIAL (no copy case)
FORK_HISTORY_REJECTED: PASSED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: NOT_VERIFIED
REMOTE_JSON_NEGATIVE_CASES: PASSED (20 cases)
REMOTE_ANCESTRY_BRANCH_EXERCISED: PASSED
TASK_ID_STRICT: PASSED
PR_URL_REPOSITORY_STRICT: PASSED
FETCH/SHOW/REV_LIST/MERGE_BASE/CAT_FILE FAILURES: PASSED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1473 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (e55750fd)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. CI

Full CI: **1473 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44242761473
