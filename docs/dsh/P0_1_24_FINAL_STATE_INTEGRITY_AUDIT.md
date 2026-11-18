# P0.1.24: Final State Integrity Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `473011216eda0040e9bb3246e217b9c4f10f17a8`
Base main: `ae28ada2e9f757e898616e25eb480bf1d7bdde6f`

## 1. XFAIL resolved

Root cause: `push_state()` called `store.save(store.load())` unconditionally,
updating `updated_at` and creating a new local state commit even when no state
change existed. That changed local HEAD and prevented the remote-advanced
ancestry branch from matching the test's intended local commit.

Fix: removed the redundant `store.save()` from `push_state()`.

`test_state_push_client_error_remote_advanced_contains_commit` now PASSES with
no xfail marker:

- Clone A local state commit is an ancestor of remote HEAD;
- remote SHA differs from local SHA;
- real fetch/merge-base/rev-list were used;
- remote JSON and task identity validated;
- follow-up clone B commit is state-only;
- `push_state()` accepted the verified remote advance.

## 2. Negative/path tests

Passing:

```text
test_remote_json_negative[malformed]
test_remote_json_negative[top_array]
test_remote_json_negative[tasks_missing]
test_remote_json_negative[task_missing]
test_remote_json_negative[identity]
test_remote_json_negative[bad_status]
test_remote_json_negative[pr_url_missing]
```

Not implemented:

```text
published_sha removal/replacement/format/reachability
pr_url replacement/format variants
state rollback
merge/empty/non-state follow-up commits
git command failure injection
unknown-commit fresh-clone CLI
fork-history rejection
```

## 3. Status

```text
REMOTE_ANCESTRY_BRANCH_EXERCISED: PASSED
REMOTE_JSON_NEGATIVE_CASES: PARTIAL (7 cases)
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
FULL_CI: PASSED (1446 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (ae28ada2)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. CI

Full CI: **1446 passed, 1 skipped** (no xfail).
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44236483588
