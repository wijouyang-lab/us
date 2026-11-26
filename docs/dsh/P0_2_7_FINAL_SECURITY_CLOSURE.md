# P0.2.7: Final Security Closure Audit

> Historical audit; superseded by P0.2.8.

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `f4af6fa83bf3996d280c3c61df028d38abbac0fc`
Base main: `67d5a7ba8ba39235e428f69903bce2b0e62ee051`

## 1. Publisher bypass removal

- removed `_TEST_HARNESS` and `globals()` bypass from production;
- `main()` always checks OIDC, then always blocks on unimplemented lock;
- publish logic is `_publish_main()`; tests use `tests/publisher_cli.py` to call
  it directly, without setting any production module variable or env flag;
- production CLI with all fake env + fake OIDC blocks with
  `BLOCKED:WORKFLOW_CONTEXT_UNVERIFIED`;
- valid context still blocks with `BLOCKED:LOCK_NOT_IMPLEMENTED`.

## 2. OIDC

- only fixed GitHub OIDC endpoint/JWKS; no token/JWKS env overrides;
- request URL restricted to HTTPS `pipelines.actions.githubusercontent.com`,
  no userinfo, port 443/None;
- redirect handler refuses redirects;
- 17 negative claim cases + endpoint negative cases pass;
- dynamic run_id validated.

## 3. Process cleanup

- PGID saved at spawn; kill uses saved PGID;
- `_kill_tree()` returns success/failure; PermissionError is reported;
- grandchild test passes;
- kill-failure injection test passes on POSIX;
- reader thread cleanup failure maps to return 126.

## 4. Python lock

Exact pins only; hashes are NOT present. CI installs the lock and full tests
pass, but `--require-hashes` is not enabled.

## 5. CI

Full CI: **1499 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44351111734

## 6. Status

```text
MAIN_SYNC: PASSED (67d5a7ba)
OIDC_ENDPOINT_ORIGIN_PROTECTION: PASSED
OIDC_NEGATIVE_MATRIX: PASSED (17 + endpoint cases)
OIDC_TRUST_ROOT: PASSED
PUBLISHER_GLOBAL_BYPASS_REMOVED: PASSED
PUBLISHER_TEST_ENTRY_ISOLATED: PASSED (static)
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
PROCESS_TREE_NORMAL_CLEANUP: PASSED (grandchild test)
PROCESS_TREE_FAILURE_CLEANUP: PASSED (POSIX kill failure injection)
READER_THREAD_CLEANUP: PARTIAL
PYTHON_LOCK_HASHES: BLOCKED (exact pins only)
CLEAN_PYTHON_INSTALL: PASSED (CI lock install)
NPM_LOCKFILE_NPM_CI: PASSED
ACTIONS_SHA_PINNING: PASSED
LOG_PRIVACY: PASSED
DRY_RUN_NO_MODEL: PASSED
MOCK_DSH_INTEGRATION: PARTIAL (scrub probe, no full mock Agent integration)
FULL_DSH_SERVICE_SPAWN: PARTIAL
FULL_CI: PASSED (1499 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
