# P0.1.7: Publisher Filesystem, Artifact and Source-Bound Audit

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
Base main: `33affb0d15afaf9f2f0973b40d542f6304f4e634`
Status: **PUBLISHER_SYMLINK_SAFE — CLOUD NOT EXECUTED**

## 1. Publisher symlink safety

`publisher.py` now validates every target before any write:

- rejects absolute paths / `..` / paths outside allowed dirs;
- checks every parent from repository root, rejecting any symlink;
- checks the target itself, including broken symlinks;
- checks resolved containment under repository root;
- validates all artifact files/hashes before applying any;
- writes through a same-directory temp file and uses `os.replace`;
- deletes use the same parent/target checks;
- no check-then-write ordering bug.

Deletion paths are validated identically.

## 2. Artifact schema

`artifact.py` now:

- rejects manifest symlinks and non-regular manifests;
- requires schema keys and source/base commit SHA;
- rejects duplicate file paths;
- rejects files/deletes conflicts;
- requires exact byte size and SHA256;
- checks every parent and target symlink;
- resolves workspace files inside `workspace/`, not just artifact root;
- rejects broken symlinks as artifacts;
- only allows regular files.

## 3. Source commit binding

Agent manifest now carries:

```text
source_commit_sha
base_branch
base_commit_sha
```

Agent workflow chooses:

- existing `origin/task_branch`, if present;
- otherwise `origin/base_branch`.

Publisher verifies current HEAD equals `source_commit_sha`; mismatch returns:

```text
BLOCKED / SOURCE_COMMIT_MISMATCH
```

No auto-rebase or source guessing.

## 4. State and PR idempotency

Publisher:

- persists `PUBLISHING`, `FAIL`, `BLOCKED`, `REVIEW_PENDING`;
- pushes FAIL state after PR failure;
- reports `STATE_PERSIST_FAILED` if state push fails;
- queries existing PR for same head/base before creating;
- reuses an existing Draft PR;
- skips terminal `REVIEW_PENDING`/`PASS` tasks;
- keeps task_id, PR URL, source SHA, history.

## 5. DSH install CI

A separate `dsh-install-verify` job was added:

- read-only permissions;
- no secrets;
- pinned `@deepseek-ai/dsh@0.2.0-rc.2`;
- `--version`, headless help, subprocess scrub marker checks;
- no model request.

## 6. Tests

Local targeted:

```text
37 passed, 3 skipped
```

Skips are Windows-only POSIX symlink/process-group tests.

Full CI to be recorded on final commit.

## 7. Remaining blockers

1. main protection is false;
2. no cloud DSH/model run;
3. no real ChatGPT PR review;
4. DSH install CI job must be observed in Actions;
5. full branch protection rules need human verification;
6. no auto-merge/auto-approval.

## Final state

```text
PUBLISHER_SYMLINK_SAFE
ARTIFACT_SCHEMA_VERIFIED
SOURCE_COMMIT_BOUND
PUBLISHER_STATE_DURABLE
PR_CREATION_IDEMPOTENT
DSH_INSTALL_CI_VERIFIED: PENDING
CODE_SECURITY_TESTED
DSH_CLOUD_TASK_NOT_EXECUTED
CHATGPT_REVIEW_PENDING
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
```
