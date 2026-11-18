# P0.2.8: Final Security Closure Audit

> Historical audit; superseded by P0.2.9.

Date: 2026-11-19
Branch: `deploy/dsh-automation-p0`
HEAD: `656b711da2937c05944a9507fb4f7c2abbcf2601`
Base main: `1a99a6ff32d14278db209e3e9d5fee12c14b9061`

## 1. Real model execution gate

Agent Job now requires BOTH:

```text
inputs.dry_run == false
vars.DSH_REAL_MODEL_ENABLED == 'true'
```

Preflight exits with `BLOCKED:REAL_MODEL_EXECUTION_DISABLED` otherwise.
`DEEPSEEK_API_KEY` exists only in Agent; no key in preflight/Publisher.
Dry-run remains model-free.

## 2. Publisher entry

Production `main()` always checks OIDC then returns
`BLOCKED:LOCK_NOT_IMPLEMENTED`; no `_TEST_HARNESS`/global bypass.

Test entry is confined to a repo and `gh` both under the system temporary
directory; it cannot run against a real checkout/gh. It still calls
`_publish_main()` directly rather than injected adapters; dependency-injection
refactor is PARTIAL.

## 3. OIDC

- fixed HTTPS origin `pipelines.actions.githubusercontent.com`, port 443/None,
  no userinfo;
- redirect handler refuses redirects;
- missing token/URL, bad origin, and failed request fail closed;
- 17 claim-negative cases + endpoint cases pass;
- production has no `DSH_OIDC_TOKEN`/`DSH_OIDC_JWKS_FILE` override.

## 4. Process cleanup

POSIX grandchild cleanup and kill-failure injection pass. Reader-thread timeout
failure is only partially induced/tested. Windows tree cleanup remains PARTIAL.

## 5. Python lock

Exact pins; no hashes. CI clean install passes, but `--require-hashes` is not
enabled. PYTHON_LOCK_HASHES remains BLOCKED.

## 6. CI

Full CI: **1501 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44358683979

## 7. Status

```text
MAIN_SYNC: PASSED (1a99a6ff)
PUBLISHER_TEST_ENTRY_NO_REAL_WRITE: PASSED (temp/mocked guard)
PUBLISHER_DEPENDENCY_INJECTION: PARTIAL
PUBLISHER_GLOBAL_BYPASS_REMOVED: PASSED
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
DISTRIBUTED_LOCK: BLOCKED
OIDC_TRUST_ROOT: PASSED
OIDC_NEGATIVE_MATRIX: PASSED
OIDC_HTTP_MISSING_TOKEN: PASSED
OIDC_REDIRECT_REFUSED: PASSED
OIDC_BEARER_NOT_FORWARDED: PASSED
PROCESS_TREE_POSIX: PASSED
PROCESS_TREE_WINDOWS: PARTIAL
READER_THREAD_FAILURE: PARTIAL
PYTHON_LOCK_HASHES: BLOCKED
CLEAN_PYTHON_INSTALL: PASSED (exact-pin lock)
NPM_LOCKFILE_NPM_CI: PASSED
ACTIONS_SHA_PINNING: PASSED
LOG_PRIVACY: PASSED
DRY_RUN_NO_MODEL: PASSED
REAL_MODEL_EXECUTION_DEFAULT_DISABLED: PASSED (workflow gate; no var set)
MOCK_DSH_INTEGRATION: PARTIAL
FULL_DSH_SERVICE_SPAWN: PARTIAL
FULL_CI: PASSED (1501 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```
