# P0.2.6: Final Security Closure Audit

> Historical audit; superseded by P0.2.7.

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `f6ac525dbf3b4ccc5daaa341e2ca8cdfe1890fec`
Base main: `185c46378f78bbdad6fa056e47d64b619b096a09`

## 1. OIDC

Production `oidc_context()` uses only the Actions OIDC request endpoint and
fixed GitHub JWKS. It ignores `DSH_OIDC_TOKEN`/`DSH_OIDC_JWKS_FILE`.

Negative claim matrix passes (17 cases): issuer, audience, repository,
repository_id, workflow_ref, ref, event_name, missing/expired exp, future nbf,
bad iat, non-numeric/foreign run_id, unknown kid, tampered signature, wrong alg,
missing required claim.

Dynamic run_id is compared to `GITHUB_RUN_ID`; no fixed `123456` in production
verifier.

## 2. Publisher isolation

Production `python -m tools.automation.publisher`:

- requires production OIDC;
- then always returns `BLOCKED:LOCK_NOT_IMPLEMENTED`;
- no environment-variable lock bypass remains.

`tests/publisher_cli.py` is a test-only entry setting `_TEST_HARNESS`; it is not
referenced by workflow or Agent. Static tests enforce that.

## 3. Process cleanup

HeadlessRunner saves PGID at spawn and kills it on limit/timeout/exit. A
grandchild test passes: parent exits while grandchild writes; grandchild is
killed and PID is no longer alive. Reader thread is bounded and a non-exiting
reader returns 126 (`cleanup_failed`).

## 4. Python lock

`requirements-production.lock` has exact pins but no hashes. CI installs it and
all tests pass; `--require-hashes` is NOT enabled.

## 5. CI

Full CI: **1496 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44345544133

## 6. Status

```text
MAIN_SYNC: PASSED (185c4637)
OIDC_NEGATIVE_CLAIMS: PASSED (17 cases)
OIDC_TRUST_ROOT_PROTECTED: PASSED
PUBLISHER_TEST_ENTRY_ISOLATION: PASSED (static isolation)
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
GRANDCHILD_EXIT_TEST: PASSED
PROCESS_TREE_TERMINATION: PARTIAL (grandchild tested; kill-failure path not)
READER_THREAD_CLEANUP: PARTIAL
PYTHON_LOCK_HASHES: BLOCKED (exact pins only)
CLEAN_PYTHON_INSTALL: PASSED (CI lock install)
NPM_LOCKFILE_NPM_CI: PASSED
ACTIONS_SHA_PINNING: PASSED
LOG_PRIVACY: PASSED
DRY_RUN_NO_MODEL: PASSED
PUBLISHER_RECOVERY: PASSED
FULL_CI: PASSED (1496 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
