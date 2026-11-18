# P0.2.9: Final Security Closure Audit

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `4b353b850675fcceee050dfa52706569056496a1`
Base main: `ae066c3183f849835348d0ad180fbca6111ee9e6`

## 1. Publisher test entry

- deleted `tests/publisher_cli.py`;
- no executable test Publisher entry remains;
- tests invoke `publisher._publish_main()` in-process with temp bare repos and
  mock `gh`; no production global/env bypass;
- production `main()` still OIDC-checks then returns
  `BLOCKED:LOCK_NOT_IMPLEMENTED`.

Full dependency injection for Git/GitHub/state adapters is not implemented; the
in-process tests still use real git against temp repos and mock gh. PARTIAL.

## 2. OIDC HTTP redirect

Added a real local HTTP redirect test:

- source server returns 302 to a second local server;
- redirect handler refuses it;
- second server records zero requests, so Authorization Bearer is not forwarded;
- endpoint origin whitelist and 17 claim-negative cases remain.

## 3. Process cleanup

POSIX grandchild and kill-failure tests pass. Windows tree cleanup and
reader-thread timeout failure remain PARTIAL; no Windows runner was available.

## 4. Python lock

Exact pins only; no hashes. CI clean install passes but `--require-hashes` is not
enabled. PYTHON_LOCK_HASHES remains BLOCKED.

## 5. Real model gate

Agent requires `vars.DSH_REAL_MODEL_ENABLED == 'true'` and `dry_run == false`;
otherwise preflight prints `BLOCKED:REAL_MODEL_EXECUTION_DISABLED`.
No real model call, no key read.

## 6. CI

Full CI: **1503 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44362148473

## 7. Status

```text
MAIN_SYNC: PASSED (ae066c31)
PUBLISHER_TEST_ENTRY_REMOVED: PASSED
PUBLISHER_FAKE_ADAPTERS: PARTIAL
PUBLISHER_NO_REAL_GITHUB_WRITE_IN_TESTS: PASSED (mock gh/temp git)
PUBLISHER_GLOBAL_BYPASS_REMOVED: PASSED
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
OIDC_TRUST_ROOT: PASSED
OIDC_NEGATIVE_MATRIX: PASSED
OIDC_REAL_REDIRECT_TEST: PASSED
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
FULL_CI: PASSED (1503 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
