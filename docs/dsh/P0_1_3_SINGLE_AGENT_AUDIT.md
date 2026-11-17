# P0.1.3: Single-Agent DSH Automation Audit

Date: 2026-11-17
Base: `fix/dsh-p0-1-2-review-guards` @ `4c9749f96126d903c866da00481d5454a18a037d`
Branch: `fix/dsh-single-agent-mode`
Status: **SINGLE_AGENT_LOCAL — CLOUD STILL BLOCKED BY MAIN PROTECTION**

## Decision

DSH is the only code-execution agent. ChatGPT reviews the GitHub PR; no second
CLI is required.

The automation terminal state after a successful Draft PR is:

```text
REVIEW_PENDING
```

It is not PASS. DSH never approves or merges its own PR.

## Changes

- `CODEX_CMD` removed from workflow and orchestrator runtime.
- Codex reviewer is no longer called.
- Draft PR success -> `REVIEW_PENDING`.
- State stores `reviewer: chatgpt` and `AWAITING_INDEPENDENT_PR_REVIEW`.
- `run_with_repair` stops at REVIEW_PENDING.
- Existing shell/rename/process/branch/main-protection guards retained.
- `review.py` remains as an optional legacy adapter for tests, but is not on the
  production path.

## Tests

```text
tests/test_dsh_automation.py
tests/test_dsh_hardening.py
tests/test_dsh_runtime_guardrails.py

25 passed, 1 skipped locally
```

Coverage:

- no reviewer -> task reaches REVIEW_PENDING, never PASS;
- Draft PR URL persisted with state;
- no self-approval API;
- no merge command;
- PR create failure remains FAIL;
- rename both endpoints;
- process timeout;
- branch guards.

The skipped test is POSIX process-group cleanup on Windows; Linux CI runs it.

## Cloud status

Main protection remains:

```text
HTTP 404 Branch not protected
```

Therefore real cloud DSH remains:

```text
BLOCKED / MAIN_PROTECTION_UNVERIFIED
```

DSH headless was previously executed locally (`HEADLESS_READY`). No cloud DSH
run and no real ChatGPT PR review were performed for this branch.

## Remaining

1. main branch protection not enabled;
2. `DEEPSEEK_API_KEY` not configured;
3. no cloud DSH run;
4. no real ChatGPT PR review yet;
5. auto-merge disabled.

## Final state

```text
P0_1_3_STATUS: SINGLE_AGENT_LOCAL
CODEX_RUNTIME_DEPENDENCY: REMOVED
POST_PR_STATE: REVIEW_PENDING
SELF_APPROVAL: FORBIDDEN
AUTO_MERGE: DISABLED
MAIN_PROTECTION: NOT_PROTECTED
CLOUD_DSH_RUN: NOT_EXECUTED
CLOUD_CHATGPT_REVIEW: NOT_EXECUTED
MAIN_MODIFIED: NO
```
