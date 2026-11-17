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

`codex` is not installed in this local environment. The independent-review
adapter is implemented and tested with a mock reviewer command. Without a
configured `CODEX_CMD`, production review returns:

```text
NEEDS_REVISION / REVIEWER_UNAVAILABLE
```

It never auto-passes.

## GitHub configuration still required

- `DEEPSEEK_API_KEY` secret for headless.
- `CODEX_CMD` repository variable for a real independent reviewer.
- human authorization before any merge.

## Not enabled

- auto-merge;
- PR approval by DSH;
- IBKR/PAPER/Shadow;
- production trading.
