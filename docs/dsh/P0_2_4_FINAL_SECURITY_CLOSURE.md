# P0.2.4: Final Security Closure Audit

> Historical audit; superseded by P0.2.5. Final P0.2.4 PR HEAD was aa902409; CI 44328763595.

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `748265dc3434939afbb696305ca0f7c6507dbdf1`
Base main: `73b422fd59b8bb3738d58e67ddd4b0e6121afd23`

## 1. OIDC Publisher identity

Publisher now requires a real GitHub Actions OIDC JWT:

- `id-token: write` only on Publisher;
- token fetched from Actions OIDC endpoint or test token env;
- RS256 signature verified with JWKS;
- issuer, audience (`dsh-publisher`), expiry, repository, workflow_ref, ref,
  event_name and run_id checked;
- missing/invalid OIDC -> `BLOCKED:WORKFLOW_CONTEXT_UNVERIFIED`.

Tests use a locally generated RSA key and JWT; no real API key or model call.
Environment-only spoofing is rejected because OIDC is required.

## 2. Output bounding

`HeadlessRunner` now:

- reads stdout/stderr in 4096-byte chunks;
- keeps at most `max_output_bytes` (default 200k);
- kills the process group/tree when the limit is exceeded;
- returns `returncode=125` and `output_limit_exceeded=True`;
- timeout returns 124 and kills the tree;
- never calls `communicate()` or retains unbounded output.

Tests: big stdout, big stderr, timeout, normal output, explicit extra env.

## 3. Python lock

`requirements-production.lock` contains exact pins for the production and test
environment (85 packages); CI installs it instead of range-resolving.
No hashes are present; exact versions only.

## 4. DSH runtime

Locked npm runtime with `npm ci`; real `dsh-subprocess` scrub probe runs in CI
and emits `DSH_SUBPROCESS_ENV_OK`. Project `child_env(extra)` drops credentials
from explicit extra maps. Full DSH service spawn remains PARTIAL.

## 5. CI

Full CI: **1492 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44327655191

## 6. Status

```text
MAIN_SYNC: PASSED (73b422fd)
OIDC_SIGNATURE_VALIDATION: PASSED
PUBLISHER_LOCAL_SPOOF_RESISTANCE: PASSED
PUBLISHER_DEFAULT_FAIL_CLOSED: PASSED
BRANCH_CONCURRENCY: PARTIAL (static contract; no cloud queue test)
PUBLISHER_LOCK: BLOCKED
BOUNDED_STREAMING_MEMORY: PASSED
PROCESS_TREE_TERMINATION: PARTIAL (process group kill, no grandchild test)
FULL_DSH_SERVICE_SPAWN: PARTIAL
EXPLICIT_EXTRA_ENV_FILTERING: PASSED (project boundary)
PYTHON_PRODUCTION_LOCKFILE: PASSED (exact pins, no hashes)
PYTHON_TEST_LOCKFILE: PASSED (same lock)
NPM_LOCKFILE_NPM_CI: PASSED
ACTIONS_SHA_PINNING: PASSED
LOG_PRIVACY: PASSED
DRY_RUN_NO_MODEL: PASSED (workflow contract)
PUBLISHER_RECOVERY: PASSED
FULL_CI: PASSED (1492 passed, 1 skipped)
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_APPROVED: NO
PR_MERGED: NO
AUTO_MERGE: DISABLED
PR_STATUS: DRAFT / OPEN / NOT MERGED
```

## 7. Remaining

- reliable distributed/queue lock with TTL/owner/fencing is BLOCKED; Publisher
  still refuses publication via `DSH_REQUIRE_LOCK=1`;
- full DSH service spawn and service-level extra-env behavior is PARTIAL;
- Python lock has no hashes;
- cloud Actions queue capacity/ordering is not empirically tested.
