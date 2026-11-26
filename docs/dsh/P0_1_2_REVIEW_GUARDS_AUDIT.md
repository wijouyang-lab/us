# P0.1.2: Rename Guard and Reviewer Timeout Audit

> Superseded by P0.1.3 single-agent mode: Codex CLI is no longer required; the
> terminal automation state after a Draft PR is REVIEW_PENDING.

Date: 2026-11-17
Base: `fix/dsh-p0-1-1-guardrails` @ `16e731aa0bd01d99aa318f87c70e3739b11195da`
Branch: `fix/dsh-p0-1-2-review-guards`
Status: **HARDENED_LOCAL — CLOUD STILL BLOCKED BY MAIN PROTECTION**

## 1. Rename path security

`changed_paths()` now consumes both NUL fields for a rename/copy:

```text
XY NEW_PATH\0OLD_PATH\0
```

Both paths enter `validate_paths()`. If either side is outside:

```text
docs/research
data/research
tools/research
tests
```

the result is `UNAUTHORIZED_PATH`, and the task becomes `BLOCKED`.

Tests:

- allowed -> forbidden rename;
- forbidden -> allowed rename;
- staged in-directory rename keeps both paths;
- ordinary new/modified file staging still matches the commit diff.

The old path is never silently skipped.

## 2. Reviewer timeout

`run_review()` now accepts a timeout and catches
`subprocess.TimeoutExpired`:

```text
status: BLOCKED
reason: REVIEWER_TIMEOUT
```

No output is parsed after timeout, no PASS is possible, and no secret is logged.
The Orchestrator persists `BLOCKED`/`NEEDS_REVISION` and never leaves a task in
`RUNNING`.

Real test:

- reviewer script sleeps 5s;
- timeout 0.2s;
- result `BLOCKED / REVIEWER_TIMEOUT`.

Task timeout test:

- fake headless returns `124 / timed_out=true / no final`;
- persisted state is not `RUNNING`.

## 3. Test count

```text
tests/test_dsh_automation.py
tests/test_dsh_hardening.py
tests/test_dsh_runtime_guardrails.py

24 passed, 1 skipped locally
```

The skipped test is POSIX process-group cleanup on Windows; Linux CI runs it.

## 4. Cloud status

Main protection was checked previously:

```text
HTTP 404 Branch not protected
```

This branch does not change repository settings. Real cloud DSH remains
`BLOCKED / MAIN_PROTECTION_UNVERIFIED`.

Codex:

```text
interface: implemented
mock tests: pass
real local CLI: not available
cloud real review: not executed
```

## 5. Remaining blockers

1. main branch protection not enabled;
2. `DEEPSEEK_API_KEY` not configured;
3. `CODEX_CMD` has no real reviewer;
4. no cloud DSH/Codex run;
5. auto-merge disabled.

## Final state

```text
P0_1_2_STATUS: HARDENED_LOCAL
RENAME_BOTH_PATHS_CHECKED: YES
REVIEWER_TIMEOUT: BLOCKED
TASK_TIMEOUT_PERSISTED: YES
STAGED_DIFF_CONSISTENCY: TESTED
MAIN_PROTECTION: NOT_PROTECTED
CLOUD_DSH_RUN: NOT_EXECUTED
AUTO_MERGE: DISABLED
MAIN_MODIFIED: NO
```
