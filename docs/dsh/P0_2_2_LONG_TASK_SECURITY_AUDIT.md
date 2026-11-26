# P0.2.2: Long-Task Security Audit

Date: 2026-11-18
Branch: `deploy/dsh-automation-p0`
HEAD: `0e572ae650a4f157dec39a28dfd5da920fab0838`
Base main: `d1144df1fb0f60bba5faa97f3041f96e3bf56b8d`

## PASSED

- raw DSH log artifact upload removed;
- redacted, length-limited diagnostic summary (no raw prompt/final/tests);
- DSH output capped at 200k characters;
- main-only base branch;
- preflight fails closed on API/format/rule errors; protected=true without full
  rules -> `PROTECTION_RULES_UNVERIFIED`;
- dry-run gates Agent and Publisher; static validation only;
- branch-level Actions concurrency group;
- Publisher has a fail-closed `DSH_REQUIRE_LOCK=1` gate because no reliable
  TTL/owner/fencing lock is implemented;
- real `@deepseek-ai/dsh@0.2.0-rc.2` subprocess environment scrub verified in a
  dedicated CI job (`DSH_SUBPROCESS_ENV_OK`);
- npm lockfile + `npm ci` verified in CI;
- third-party Actions pinned to commit SHAs for DSH workflows;
- existing Publisher recovery/state tests pass.

## NOT_VERIFIED / BLOCKED

```text
RELIABLE_CROSS_TASK_LOCK: BLOCKED (Publisher safely refuses publishing)
LOCK_TTL_OWNER_FENCING: BLOCKED
LOCK_CRASH_RECOVERY: BLOCKED
PYTHON_LOCKFILE: NOT_VERIFIED
STREAMING_MEMORY_BOUND: NOT_VERIFIED (output is capped after communicate)
```

The lock gate intentionally blocks real publishing; no false claim of
same-branch concurrency safety.

## CI

Full CI: **1483 passed, 1 skipped, 0 xfailed**.
Jobs:

```text
test: success
dsh-install-verify: success
dsh-subprocess-isolation: success (DSH_SUBPROCESS_ENV_OK)
```

CI: https://github.com/wijouyang-lab/us/actions/runs/44307433223

## Safety

```text
REAL_DSH_MODEL_CALL: NO
REAL_API_KEY_READ: NO
RAW_LOG_UPLOAD: NO
MAIN_MODIFIED: NO
PR_MERGED: NO
PR_STATUS: DRAFT / OPEN
```
