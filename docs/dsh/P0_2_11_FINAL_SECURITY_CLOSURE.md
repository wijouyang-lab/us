# P0.2.11: Final Security Closure Audit

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `d54dffbd4929fa8e82b0757c0cbfaafc56427597`
Base main: `42d3a19ee205713fdfa9d959ff04d1fd79d3b65b`

## 1. Main sync

Latest actual `origin/main` fetched and merged; dashboard/data retained. No main
modification, no force push.

## 2. Publisher adapters

Added `publisher_core.py` with `GitPort`, `GitHubPort`, `StatePort` and an
injectable `publish()` decision core. Fake-adapter tests cover:

- create Draft PR;
- reuse Draft;
- Ready PR blocked;
- multiple PR blocked;
- PR query failure;
- PR creation failure;
- state persistence failure;
- terminal skip.

The production `_publish_main` legacy path does NOT yet call this core, so full
Adapter injection into production remains PARTIAL. Production `main()` still
OIDC-checks then returns `BLOCKED:LOCK_NOT_IMPLEMENTED`.

## 3. OIDC

17 claim-negative cases and 302/307/308 local HTTP redirect tests pass. Source
receives exactly one Bearer request; target receives none. Trusted JWKS/origin
unchanged.

## 4. Process cleanup

POSIX PGID/grandchild/kill-failure tests pass. Windows CI job passes normal
cleanup; taskkill failure/permission/lingering-descendant paths remain PARTIAL.
Reader blocked-timeout test remains PARTIAL; cleanup-failure propagation test
passes.

## 5. Python lock

Exact pins only; no hashes. `--require-hashes` not enabled.

## 6. Real model gate

Agent requires `dry_run == false && vars.DSH_REAL_MODEL_ENABLED == 'true'`.
No real model call/key read.

## 7. CI

Full CI: **1511 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
dsh-process-cleanup-windows: success
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44465081190

## 8. Status

```text
MAIN_SYNC: PASSED (42d3a19e)
PUBLISHER_FAKE_GIT_ADAPTER: PARTIAL (core tested, production not wired)
PUBLISHER_FAKE_GITHUB_ADAPTER: PARTIAL
PUBLISHER_FAKE_STATE_ADAPTER: PARTIAL
PUBLISHER_NO_REAL_GITHUB_WRITE_IN_TESTS: PASSED
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
OIDC_TRUST_ROOT: PASSED
OIDC_NEGATIVE_MATRIX: PASSED
OIDC_REDIRECT_302: PASSED
OIDC_REDIRECT_307: PASSED
OIDC_REDIRECT_308: PASSED
OIDC_BEARER_NOT_FORWARDED: PASSED
PROCESS_TREE_POSIX: PASSED
PROCESS_TREE_WINDOWS_NORMAL: PASSED
PROCESS_TREE_WINDOWS_FAILURE: PARTIAL
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
FULL_CI: PASSED (1511 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
