# P0.1: DSH Automation Hardening Audit

Date: 2026-11-17
Base: `feature/dsh-headless-automation` @ `c46513c3d55eb42a91da34b0f709087971e51086`
Branch: `fix/dsh-p0-1-hardening`

## 1. Shell injection

Before: workflow embedded `${{ inputs.prompt }}`, `${{ inputs.task_id }}` and
`${{ inputs.branch }}` directly in shell `run`.

After:

- values are passed through env (`TASK_PROMPT`, `TASK_ID`, `TASK_BRANCH`,
  `BASE_BRANCH`, `DRY_RUN`, `MAX_ATTEMPTS`);
- Python receives them as separate `argv` entries;
- `validate.py` enforces strict task-id and branch patterns;
- `main`/`master` and `..` branch inputs are rejected;
- prompt is passed as one subprocess argument, never through `shell=True`.

Tests cover `;`, `$()`, backticks, newlines and overlong ids.

## 2. Headless timeout

`HeadlessRunner` now uses `communicate(timeout=...)`, kills the child on timeout,
records return code `124`, and marks `timed_out`.

Real subprocess tests:

- sleeping child killed at 0.2s;
- NDJSON without `final` returns `final_event=false`;
- malformed/empty output is logged and does not PASS.

## 3. Logs and state

- NDJSON logs are uploaded as GitHub Actions artifacts.
- Logs are gitignored (`automation/logs/*.ndjson`).
- Only `automation/state/tasks.json` is persisted by the workflow.
- The workflow no longer runs `git add automation/logs`.
- State writes remain atomic.

## 4. Branch safety

- `base_branch` is an explicit workflow input.
- Branch must match `(feature|fix|research|automation)/...`.
- `main`/`master` head is rejected.
- Orchestrator refuses to commit if HEAD resolves to main.
- P0.1 PR target is `feature/dsh-headless-automation`.

## 5. PR failure

`gh pr create` exit code is checked. A non-zero result sets:

```text
status: FAIL
reason: PR_CREATE_FAILED
```

No review/PASS is recorded in that case.

## 6. Reviewer availability

`CODEX_CMD` absent returns:

```text
status: BLOCKED
reason: REVIEWER_UNAVAILABLE
```

It is never converted to PASS. Self-review (`author == reviewer`) remains
`NEEDS_REVISION`.

### Actual availability

```text
interface implemented:       YES
mock reviewer tests:         PASS
local real Codex CLI:        NOT AVAILABLE
cloud real Codex review:     NOT EXECUTED
cloud DSH run:               NOT EXECUTED (secrets not configured)
```

## 7. Tests

```text
tests/test_dsh_automation.py
tests/test_dsh_hardening.py
15 passed
```

New coverage includes shell metacharacters, newline prompt, real timeout kill,
missing final event, reviewer unavailable, PR create failure, protected branch,
and workflow input indirection.

## 8. Remaining gaps

- `DEEPSEEK_API_KEY` and `CODEX_CMD` are not configured in this environment.
- No GitHub-hosted DSH task has been executed.
- No real Codex reviewer has been executed.
- No auto-merge or auto-approval is enabled.

## Final state

```text
P0_1_STATUS: HARDENED_LOCAL
SHELL_INJECTION: FIXED
HEADLESS_TIMEOUT: TESTED
LOGS_COMMITTED: NO
BRANCH_PROTECTION: TESTED
PR_FAILURE: HANDLED
REVIEWER_UNAVAILABLE: BLOCKED
CLOUD_DSH_RUN: NOT_EXECUTED
CLOUD_CODEX_REVIEW: NOT_EXECUTED
AUTO_MERGE: DISABLED
MAIN_MODIFIED: NO
```
