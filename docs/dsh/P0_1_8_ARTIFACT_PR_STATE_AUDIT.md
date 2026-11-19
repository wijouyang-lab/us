# P0.1.8: Artifact Root, Manifest, Draft PR and State Durability Audit

Date: 2026-11-17
Branch: `deploy/dsh-automation-p0`
HEAD: `9d7304cddf470e4ae3b9d7101083140eb7a69e37`
Base main: `d055deea539434cf9c3b67572682ac584e05b23a`
Status: **CODE_SECURITY_TESTED — CLOUD TASK NOT EXECUTED**

## 1. Artifact root and workspace safety

`artifact.py` now checks:

- artifact root is a regular directory, not symlink;
- `workspace/` is a regular directory, not symlink;
- every parent from root/workspace is regular;
- target and broken-symlink targets rejected;
- final resolved path is strictly under the expected root;
- manifest is a regular file, not symlink.

`build_artifact()` and `read_manifest()` both enforce root checks.

## 2. Strict manifest schema

Required fields:

```text
task_id, branch, base_branch, source_commit_sha, base_commit_sha,
status, files, deletes
```

Validation:

- `REQUIRED.issubset(m)`;
- unknown fields rejected explicitly;
- task_id/branch/base schema validation;
- 40-hex source/base commit SHAs;
- files/deletes arrays;
- path strings;
- SHA256 64-hex;
- non-negative integer bytes;
- duplicate paths rejected;
- files/deletes conflicts rejected;
- source commit binding retained.

Missing `base_branch` plus an extra field is rejected before any target write.

## 3. Draft PR idempotency

Publisher:

- queries all open PRs for head/base;
- zero -> create Draft, then verify `isDraft`;
- one Draft -> reuse;
- one non-Draft -> BLOCKED;
- multiple -> BLOCKED;
- query failure -> BLOCKED;
- only confirmed Draft -> REVIEW_PENDING;
- never converts Ready to Draft, approves, or merges.

## 4. Durable state

- PUBLISHING is committed and pushed before file modification;
- state push failure stops publishing;
- FAIL/BLOCKED/REVIEW_PENDING persistence is checked;
- state failure records `STATE_PERSIST_FAILED`;
- source SHA, PR URL, attempts and history retained;
- terminal REVIEW_PENDING/PASS/FAIL tasks are not overwritten;
- temporary credential helper only; no `.git/config` token.

## 5. DSH install CI

`dsh-install-verify` job remains and passed:

```text
542 packages
0.2.0-rc.2
SENSITIVE_ENV_PATTERN present
```

No secrets, no model request.

## 6. Main sync

```text
origin/main: d055deea539434cf9c3b67572682ac584e05b23a
merge --no-edit origin/main
```

No force-push, no main modification. PR diff remains DSH files only.

## 7. Tests

Local:

```text
37 passed, 4 skipped
```

Full CI:

```text
1394 passed, 1 skipped
```

Jobs:

```text
test: success
dsh-install-verify: success
```

## 8. Remaining

1. main is unprotected (`protected=false`); cloud DSH remains blocked;
2. full branch protection rules need human verification;
3. no cloud DSH model task;
4. no real ChatGPT PR review;
5. auto-merge disabled.

## Final state

```text
ARTIFACT_ROOT_SYMLINK_SAFE
MANIFEST_SCHEMA_STRICT
DRAFT_PR_ONLY_ENFORCED
PUBLISHING_STATE_DURABLE
FAIL_STATE_DURABLE
PUBLISHER_RECOVERY_TESTED
PR_IDEMPOTENCY_VERIFIED
DSH_INSTALL_CI_VERIFIED
CODE_SECURITY_TESTED
DSH_CLOUD_TASK_NOT_EXECUTED
CHATGPT_REVIEW_PENDING
AUTO_MERGE_DISABLED
MAIN_MODIFIED_NO
```
