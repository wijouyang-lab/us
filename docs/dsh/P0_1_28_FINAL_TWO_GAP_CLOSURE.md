# P0.1.28: Final Two-Gap Closure Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
Test code HEAD: `68b353854bf11a5ab88388de641df32251661fd6`
PR HEAD at test time: `68b353854bf11a5ab88388de641df32251661fd6`
Main at audit time: `f0783d05332e699658ef941708ccc4f7ded3de95`

## 1. Copy follow-up

`test_remote_advanced_followup_commit_checks[copy-False]` PASSED.

`git diff-tree --name-status -M -C --find-copies-harder` output is parsed into
rows; the test asserts at least one status field starts with `C`. Publisher
still rejects the copy follow-up on the remote-advanced path.

## 2. Unknown commit fresh-clone CLI

`test_unknown_commit_after_artifact_blocked_fresh_clone` PASSED.

Verified:

- Publisher CLI prints `BLOCKED:UNKNOWN_COMMIT_AFTER_ARTIFACT`;
- no `STATE_PERSIST_FAILED:REMOTE_NOT_SAVED` in output;
- fresh clone fetches `origin/fix/t`;
- bare-remote `automation/state/tasks.json` has status `BLOCKED` and reason
  `UNKNOWN_COMMIT_AFTER_ARTIFACT`;
- local state agrees;
- remote log has exactly one `automation: DSH task` commit;
- unknown business commit remains;
- at least one allowed state-only commit persisted BLOCKED;
- no second artifact business commit;
- mock `pr create` count remains 1.

The mock gh result is a mock GitHub CLI test, not a real GitHub API Draft PR
count.

## 3. CI

Full CI: **1475 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44246719950

## 4. Main

Latest main observed:

```text
f0783d05332e699658ef941708ccc4f7ded3de95
```

It is an automatic Dashboard market-data refresh. Per instruction, the branch
was not repeatedly merged for this data-only commit. `behind_by` may be 1; no
DSH code conflict was identified.

## 5. Status

```text
COPY_FOLLOWUP_REMOTE_ADVANCED: PASSED
UNKNOWN_COMMIT_FRESH_CLONE_CLI_BLOCKED: PASSED
REMOTE_BLOCKED_STATE_PERSISTED: PASSED
ARTIFACT_BUSINESS_COMMIT_COUNT: 1
STATE_ONLY_BLOCKED_COMMIT_PERSISTED: PASSED
MOCK_PR_CREATE_COUNT: 1
FULL_CI: PASSED (1475 passed, 1 skipped, 0 xfailed)
DSH_INSTALL_VERIFY: PASSED
MAIN_SYNCED: NO (data-only main refresh not chased)
AUTO_MERGE: DISABLED
REAL_DSH_TASK_EXECUTED: NO
MAIN_MODIFIED: NO
PR_STATUS: DRAFT / OPEN
CHATGPT_REVIEW_PENDING
```
