# P0.1.28: Final Two-Gap Closure Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `5a25a20da4a9308293636d16bb962631c2299eb8`
Base main: `fb63b63e19305bd609159923f22c6d07ed53a947`

## 1. Copy follow-up

`test_remote_advanced_followup_commit_checks[copy-False]` PASSED.

- Clone B adds a tracked source under `automation/state/`;
- copies it to a second file and commits both as state commits;
- `git diff-tree ... -M -C --find-copies-harder` identifies a `C` status;
- push to bare remote;
- Clone A `push_state(force_remote_check=True)` enters remote-advanced;
- Publisher rejects the copy commit.

## 2. Unknown commit CLI

`test_unknown_commit_after_artifact_blocked_fresh_clone` PASSED.

- first Publisher CLI creates one artifact business commit and a recoverable
  PUBLISHING state;
- Clone B adds an unknown business commit and pushes;
- original workspace is deleted;
- fresh clone runs Publisher CLI;
- output contains `BLOCKED:UNKNOWN_COMMIT_AFTER_ARTIFACT`;
- state status is BLOCKED with that reason;
- one business commit remains, one `pr create` call remains.

## 3. Status

```text
COPY_FOLLOWUP_REMOTE_ADVANCED: PASSED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: PASSED
REMOTE_JSON_NEGATIVE_CASES: PASSED (20)
REMOTE_ANCESTRY_BRANCH_EXERCISED: PASSED
FORK_HISTORY_REJECTED: PASSED
PUBLISHED_SHA_OBJECT_NOT_IN_HISTORY: PASSED
FETCH/SHOW/REV_LIST/MERGE_BASE/CAT_FILE FAILURES: PASSED
TASK_ID_STRICT: PASSED
PR_URL_REPOSITORY_STRICT: PASSED
FOUR_FRESH_CLONE_TESTS: PASSED
ONE_BUSINESS_COMMIT_ENFORCED: PASSED
DRAFT_CREATE_IDEMPOTENCY: PASSED
FULL_CI: PASSED (1475 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: YES (fb63b63e)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
```

## 4. CI

Full CI: **1475 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44244943243
