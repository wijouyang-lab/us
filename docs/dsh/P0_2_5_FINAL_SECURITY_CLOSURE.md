# P0.2.5: Final Security Closure Audit

> Historical audit; superseded by P0.2.6.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `b5a3e409b5e6fc147a37aeb251b11928ff977d0c`
Base main: `bffda64da5d21edb9e94622ba5c3a82efae31317`

## 1. OIDC trust root

Production `oidc_context()` now:

- fetches token only from `ACTIONS_ID_TOKEN_REQUEST_URL`;
- fetches JWKS only from the fixed GitHub issuer URL;
- ignores `DSH_OIDC_TOKEN` and `DSH_OIDC_JWKS_FILE`;
- verifies RS256 signature, issuer, audience, exp/nbf/iat,
  repository, repository_id, workflow_ref, ref, event_name and dynamic run_id;
- no token/JWKS override path in production.

Pure `verify_token(token, jwks, expected)` is used only by tests.

A direct production CLI with all GITHUB_* variables plus fake
`DSH_OIDC_TOKEN`/`DSH_OIDC_JWKS_FILE` returns
`BLOCKED:WORKFLOW_CONTEXT_UNVERIFIED` before any file/state change.

Tests use a test-only Publisher entry that bypasses gates to exercise publishing
behavior; production entry is still blocked.

## 2. Publisher lock

`python -m tools.automation.publisher` now **always** returns
`BLOCKED:LOCK_NOT_IMPLEMENTED` after OIDC, unless run through the internal test
harness. Distributed lock remains unimplemented; no unlocked production path.

## 3. Process cleanup

HeadlessRunner saves the process-group ID immediately after spawn and uses it
for kill, including after parent exit. It terminates descendants after normal
exit and detects a reader thread that does not stop (return 126,
`cleanup_failed`). Grandchild-specific exit tests were not added.

## 4. CI

Full CI: **1493 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44339182680

## 5. Status

```text
MAIN_SYNC: PASSED (bffda64d)
OIDC_TRUST_ROOT_PROTECTED: PASSED
OIDC_TEST_KEY_ENV_BYPASS: BLOCKED
OIDC_RUN_ID_DYNAMIC_VALIDATION: PASSED
OIDC_REPOSITORY_ID_VALIDATION: PASSED
OIDC_NEGATIVE_CLAIMS: PARTIAL (signature/missing context tested; full matrix not)
PUBLISHER_LOCAL_SPOOF_RESISTANCE: PASSED
PUBLISHER_LOCK_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
BOUNDED_STREAMING_MEMORY: PASSED
PROCESS_TREE_TERMINATION: PARTIAL
GRANDCHILD_EXIT_TEST: NOT_VERIFIED
READER_THREAD_CLEANUP: PARTIAL
PYTHON_LOCK_HASHES: BLOCKED (exact pins only)
NPM_LOCKFILE_NPM_CI: PASSED
ACTIONS_SHA_PINNING: PASSED
LOG_PRIVACY: PASSED
DRY_RUN_NO_MODEL: PASSED
PUBLISHER_RECOVERY: PASSED
FULL_CI: PASSED (1493 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
