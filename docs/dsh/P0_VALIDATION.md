# P0 Validation Record

## Automated tests

```text
tests/test_dsh_automation.py
7 passed
```

Coverage:

- atomic state enqueue/claim/recover;
- max-attempt terminal FAIL;
- dry-run orchestration;
- independent-review guard (`SELF_REVIEW_FORBIDDEN`);
- mock Codex PASS close-loop;
- headless NDJSON parsing;
- workflow is manual-only and has no merge.

## Actual DSH headless proof

Command:

```bash
dsh --profile headless --json "Reply with exactly HEADLESS_READY"
```

Observed final event:

```json
{"type":"final","text":"HEADLESS_READY"}
```

Session: `session-0229ccc2-acbc-4099-a7ea-17e826cdc008`

## Reviewer status

Codex CLI is not required. DSH is the only execution agent. A successful Draft
PR ends `REVIEW_PENDING`; ChatGPT reviews the PR externally. No mock review is
used as a production PASS.

## GitHub configuration still required

- `DEEPSEEK_API_KEY` secret for headless model auth.
- checkout `persist-credentials: false`.
- no `CODEX_CMD`.
- human authorization before any merge.

## Not enabled

- auto-merge;
- PR approval by DSH;
- IBKR/PAPER/Shadow;
- production trading.
