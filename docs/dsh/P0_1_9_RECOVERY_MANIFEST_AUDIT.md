# P0.1.9: Publisher Crash Recovery, Manifest Trust and Idempotency Audit

> Historical audit. Superseded by P0.1.10; the HEAD and CI in this file are not
> the current deployment HEAD.

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
HEAD: `d31a6ec12f84a6664d5db4b62544176dec3b3a81`
Base main: `51c427356e8dfce63ef5d8d36466ae9aa6b4d75a`
Status: **CODE_SECURITY_TESTED — CLOUD TASK NOT EXECUTED**

## 1. Publisher recovery

Publisher now records:

```text
agent_source_sha, base_commit_sha, artifact_digest,
branch, base_branch, attempts, published_sha, history
```

On a PUBLISHING resume:

- verifies task_id, branch, base, source SHA and artifact digest;
- verifies source is an ancestor of current HEAD;
- finds a business commit by artifact digest in its commit message;
- if found, skips file application and proceeds to push/PR;
- if only state commits changed, resumes file application;
- any unrecognized branch change -> `BLOCKED`.

No Publisher state commit is ever treated as the Agent source commit.

## 2. Trusted manifest inputs

Publisher requires workflow inputs:

```text
--task-id --branch --base-branch
```

and verifies manifest fields exactly, plus:

- source SHA format;
- actual `origin/<base>` commit equals manifest base SHA;
- status `AGENT_COMPLETE`;
- `timed_out=false`;
- `tests_returncode=0`;
- files/deletes path/hash/size/duplicates.

All checks happen before business file changes.

## 3. Artifact root ancestors

`artifact.py` now walks every ancestor above artifact root and workspace,
rejecting symlinks/broken symlinks before mkdir/copy. Manifest root/workspace
must be regular directories.

## 4. Draft PR idempotency

Publisher queries open PRs by head/base:

- zero -> create Draft and verify URL, `isDraft`, head, base;
- one Draft -> reuse;
- one Ready -> BLOCKED;
- multiple -> BLOCKED;
- query failure -> BLOCKED;
- create failure -> FAIL;
- no auto-Ready, approval or merge.

## 5. State persistence

- PUBLISHING is committed/pushed before business changes;
- state push failures are checked and recorded;
- FAIL/BLOCKED/REVIEW_PENDING check persistence result;
- `STATE_PERSIST_FAILED` is observable;
- existing PR is discoverable on retry;
- terminal REVIEW_PENDING/PASS/FAIL are not overwritten;
- state commit uses temporary credential helper.

## 6. Main sync

Fetched actual latest `origin/main`:

```text
51c427356e8dfce63ef5d8d36466ae9aa6b4d75a
```

and merged with a normal merge commit. No force-push, no main change.

## 7. CI

Local targeted: **37 passed, 4 skipped**.

Full CI: **1394 passed, 1 skipped**.

Jobs:

```text
dsh-install-verify: success
test: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44110636372

## 8. Evidence status

```text
PUBLISHING_CRASH_RECOVERY_VERIFIED
PUBLISHER_RETRY_IDEMPOTENT
MANIFEST_TRUSTED_INPUTS_BOUND
BASE_COMMIT_VERIFIED
ARTIFACT_ROOT_ANCESTORS_SYMLINK_SAFE
DRAFT_PR_REUSE_VERIFIED
NON_DRAFT_PR_BLOCKED
MULTIPLE_PR_BLOCKED
PR_QUERY_FAILURE_BLOCKED
STATE_PERSISTENCE_FAILURE_HANDLED
STATE_RECOVERY_TESTED
DSH_INSTALL_CI_VERIFIED
FULL_CI_PASSED
DSH_CLOUD_TASK_NOT_EXECUTED
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
CHATGPT_REVIEW_PENDING
```

Some PR/state branches are covered by integration tests on Linux CI; local
Windows skipped symlink/POSIX cases.

## 9. Remaining

1. main is unprotected (`protected=false`);
2. full branch protection rules (direct push, force push, required checks,
   human review) still need human verification;
3. no real cloud DSH model task;
4. no real ChatGPT PR review;
5. auto-merge disabled.

## Note

P0.1.8 remains a historical audit at HEAD `da7992bd`; this document is the
current P0.1.9 record.
