# P0.2.10: Final Security Closure Audit

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `db61e833fe8d9b1d3498c1f31943004cb59a2a25`
Base main: `369b59f97c9681cf61fd842465bfe50d653e8b33`

## 1. Main sync

Latest actual `origin/main` fetched and merged; dashboard/data updates retained.
No main modification, no force push.

## 2. Publisher

- executable test entry removed;
- tests call `_publish_main()` in-process with temp bare repo and mock gh;
- production `main()` always OIDC-checks then
  `BLOCKED:LOCK_NOT_IMPLEMENTED`;
- no global/env bypass;
- explicit Git/GitHub/State Adapter injection is NOT implemented; this remains
  PARTIAL. Tests still use real git against temp repos and mock gh.

## 3. OIDC

- 17 claim-negative cases pass;
- local HTTP 302/307/308 source tests pass;
- source receives exactly one Bearer request; target receives zero requests;
- endpoint origin whitelist/redirect refusal retained.

## 4. Process cleanup

- POSIX grandchild and kill-failure tests pass;
- Windows CI job `dsh-process-cleanup-windows` passed;
- Windows taskkill failure/permission paths are not fully injected; PARTIAL;
- reader blocked-timeout deterministic test is not implemented; PARTIAL;
  cleanup-failure propagation test passes.

## 5. Python lock

Exact pins only; no hashes. `PYTHON_LOCK_HASHES` BLOCKED.

## 6. Real model gate

Agent requires `dry_run == false && vars.DSH_REAL_MODEL_ENABLED == 'true'`;
otherwise `BLOCKED:REAL_MODEL_EXECUTION_DISABLED`. No model call/key read.

## 7. CI

Full CI: **1506 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
dsh-process-cleanup-windows: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44458970240

## 8. Status

```text
MAIN_SYNC: PASSED (369b59f9)
PUBLISHER_FAKE_GIT_ADAPTER: PARTIAL
PUBLISHER_FAKE_GITHUB_ADAPTER: PARTIAL
PUBLISHER_FAKE_STATE_ADAPTER: PARTIAL
PUBLISHER_NO_REAL_GITHUB_WRITE_IN_TESTS: PASSED (temp git/mock gh)
PUBLISHER_TEST_ENTRY_REMOVED: PASSED
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
OIDC_TRUST_ROOT: PASSED
OIDC_NEGATIVE_MATRIX: PASSED
OIDC_SOURCE_REQUEST_CONFIRMED: PASSED
OIDC_REDIRECT_302: PASSED
OIDC_REDIRECT_307: PASSED
OIDC_REDIRECT_308: PASSED
OIDC_BEARER_NOT_FORWARDED: PASSED
PROCESS_TREE_POSIX: PASSED
PROCESS_TREE_WINDOWS: PARTIAL
READER_THREAD_FAILURE: PARTIAL
PYTHON_LOCK_HASHES: BLOCKED
CLEAN_PYTHON_INSTALL: PASSED
NPM_LOCKFILE_NPM_CI: PASSED
ACTIONS_SHA_PINNING: PASSED
LOG_PRIVACY: PASSED
DRY_RUN_NO_MODEL: PASSED
REAL_MODEL_EXECUTION_DEFAULT_DISABLED: PASSED
MOCK_DSH_INTEGRATION: PARTIAL
FULL_DSH_SERVICE_SPAWN: PARTIAL
FULL_CI: PASSED (1506 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
