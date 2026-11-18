# P0.2.3: Final Security Closure Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `3a622bf65bd115476082e78d5808dd6cc8f9f4bf`
Base main: `0a2af8d860162db40502bf0d8bda8c35205c0c3b`

## 1. Branch queue

Workflow-level concurrency:

```yaml
group: dsh-task-${{ inputs.branch }}
queue: max
cancel-in-progress: false
```

This serializes the whole workflow for the same branch; different branches may
run in parallel. GitHub `queue: max` is limited (up to 100 pending); it is not
an infinite FIFO and waiting order is not guaranteed. Static contract tested;
no cloud scheduler test was performed.

## 2. Publisher fail-closed context

Publisher now requires:

```text
GITHUB_ACTIONS=true
GITHUB_REPOSITORY=wijouyang-lab/us
GITHUB_WORKFLOW=DSH Headless Task
GITHUB_JOB=publisher
GITHUB_EVENT_NAME=workflow_dispatch
GITHUB_REF=refs/heads/deploy/dsh-automation-p0...
GITHUB_RUN_ID numeric
DSH_WORKFLOW_CONTEXT=publisher
```

Missing/mismatched context returns `BLOCKED:WORKFLOW_CONTEXT_UNVERIFIED` before
any file/state change. This is an environment contract, not cryptographic
attestation; tests use a trusted fixture.

## 3. Real DSH subprocess probe

CI job `dsh-subprocess-isolation` installs locked `@deepseek-ai/dsh@0.2.0-rc.2`
via `npm ci`, imports the real `dsh-subprocess` `scrubbedParentEnv`, spawns a
local Node child, and verifies fake keys/tokens are absent while
`NORMAL_TEST_VAR=visible` remains. Output: `DSH_SUBPROCESS_ENV_OK`.

This is not a full DSH agent/service spawn; explicit `extra` environment
override at the DSH service layer was not exercised end-to-end. PARTIAL.

## 4. Streaming output

Status: NOT_VERIFIED. Current `HeadlessRunner` still uses `communicate()` with a
post-read 200k cap; it is not a true bounded streaming reader.

## 5. Lock / Python lockfile

- no reliable remote lock with TTL/owner/fencing; Publisher remains blocked by
  `DSH_REQUIRE_LOCK=1`;
- no Python transitive lockfile;
- npm lockfile and npm ci are verified.

## 6. Actions pinning

Both DSH-related workflows now pin all third-party actions to commit SHAs with
`# vN` comments.

## 7. CI

Full CI: **1484 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44317723603

## 8. Status

```text
WORKFLOW_BRANCH_QUEUE: PASSED (static contract)
SAME_BRANCH_WORKFLOW_SERIALIZATION: PARTIAL (no cloud scheduler test)
QUEUE_CAPACITY_HANDLING: PARTIAL (documented 100 pending limit)
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED (context gate)
WORKFLOW_CONTEXT_VALIDATION: PASSED (environment contract)
FULL_DSH_SUBPROCESS_SPAWN: PARTIAL
EXPLICIT_EXTRA_ENV_FILTERING: NOT_VERIFIED
STREAMING_MEMORY_BOUND: NOT_VERIFIED
PROCESS_GROUP_TERMINATION: NOT_VERIFIED
PYTHON_PRODUCTION_LOCKFILE: NOT_VERIFIED
PYTHON_TEST_LOCKFILE: NOT_VERIFIED
NPM_LOCKFILE_NPM_CI: PASSED
DSH_WORKFLOW_ACTIONS_SHA: PASSED
TEST_WORKFLOW_ACTIONS_SHA: PASSED
LOG_PRIVACY_REGRESSION: PASSED
DRY_RUN_NO_MODEL_REGRESSION: PASSED
PUBLISHER_RECOVERY_REGRESSION: PASSED
MAIN_SYNCED: 0a2af8d8
FULL_CI: PASSED (1484 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
