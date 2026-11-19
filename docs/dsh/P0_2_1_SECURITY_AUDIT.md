# P0.2.1: DSH Headless Automation Security Audit

> Historical audit; superseded by P0.2.2.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `1f6b12afab1ac52e668726bae8a3ee2728eb693b`
Base main: `da2ac196d0ce3d3764bcdfe745af83a5c2f4316f`

## P0-A: Log privacy and artifact

- removed `Upload DSH log` artifact step;
- agent no longer puts raw `final` or `tests_tail` in the manifest;
- diagnostic summary is redacted and length-limited;
- Headless output is capped at 200k characters;
- common KEY/TOKEN/SECRET/PASSWORD values and `sk-`/`gh*_` values are redacted.

Tests:

```text
test_redact_removes_credentials_and_limits_length
test_artifact_has_no_raw_prompt_or_output
test_workflow_has_no_raw_log_upload_and_dry_gate
```

## P0-B: Main protection

- `validate_base()` accepts only `main`;
- preflight rejects non-main, repo identity failure, branch API failure,
  `.protected != true`, and protection-rules API failure;
- full rules require required checks, required reviews, no force push, and
  admin enforcement; otherwise `PROTECTION_RULES_UNVERIFIED`.

Tests:

```text
test_base_branch_only_main
test_preflight_fails_closed_on_api_errors
test_preflight_protected_without_rules_blocks
```

Main currently reports `protected=false`, so real tasks remain blocked.

## P0-C: Dry run

- `agent` job has `if: inputs.dry_run == false`;
- `publisher` retains `if: inputs.dry_run == false`;
- dry-run preflight only validates inputs/protection and prints
  `DRY_RUN_VALIDATION_ONLY`;
- no DSH agent, model call, commit, push or PR is performed.

## P1-D: Concurrency

Concurrency group was changed from task_id to target branch. This is **not** a
reliable infinite FIFO queue and no remote task lock/TTL/owner-token mechanism
was implemented. Same-branch concurrency safety is NOT_VERIFIED.

## P1-E: Real DSH subprocess isolation

No test against the installed `@deepseek-ai/dsh@0.2.0-rc.2` subprocess runtime
was added. NOT_VERIFIED.

## P2: Supply chain

No npm lockfile, Python lockfile, or Actions SHA pinning was added. NOT_VERIFIED.

## CI

Full CI: **1481 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44302705676

## Status

```text
LOG_ARTIFACT_PRIVACY: PASSED
DRY_RUN_TRUE_NO_MODEL: PASSED (workflow contract)
DRY_RUN_FALSE_PREFLIGHT: PASSED
BASE_BRANCH_MAIN_ONLY: PASSED
PROTECTION_FAIL_CLOSED: PASSED
P1D_CONCURRENCY_LOCK: NOT_VERIFIED
P1E_REAL_DSH_SUBPROCESS_TEST: NOT_VERIFIED
P2_SUPPLY_CHAIN_LOCK: NOT_VERIFIED
FULL_CI: PASSED (1481 passed, 1 skipped)
DSH_INSTALL_VERIFY: PASSED
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_MERGED: NO
PR_STATUS: DRAFT / OPEN
```
