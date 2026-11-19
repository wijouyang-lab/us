# P0 DSH Headless Automation Architecture

## Diagram

```text
workflow_dispatch
  (task_id, prompt, branch, dry_run, max_attempts)
        |
        v
.github/workflows/dsh-task.yml
  - checkout, Python, Node, pinned DSH
  - guard: branch != main
  - run_task.py
        |
        v
TaskStore (automation/state/tasks.json)
  QUEUED -> RUNNING -> REVIEW_PENDING
                         |  PASS
                         |  FAIL
                         v
          NEEDS_REVISION -> retry (max 3)
                         |
                         v
DSH headless --json
  - NDJSON log: automation/logs/<task>-attemptN.ndjson
  - final answer
        |
        v
git branch/push -> gh pr create --draft (base main)
        |
        v
Independent reviewer (CODEX_CMD)
  PASS / FAIL / NEEDS_REVISION
        |
        +--> PASS: stop, human review remains required
        +--> NEEDS_REVISION: retry, max 3
        +--> FAIL: terminal FAIL, log retained
```

## Safety invariants

- workflow is `workflow_dispatch` only;
- branch `main` rejected;
- `gh pr merge` absent;
- Draft PR only;
- reviewer must differ from author (`SELF_REVIEW_FORBIDDEN`);
- no API key is printed;
- logs/state are artifacts and task-branch commits, never `main`;
- at most 3 attempts, then terminal FAIL.

## State schema

`automation/state/tasks.json`:

```json
{
  "version": 1,
  "tasks": {
    "task-id": {
      "status": "QUEUED|RUNNING|REVIEW_PENDING|NEEDS_REVISION|PASS|FAIL|BLOCKED",
      "attempts": 0,
      "max_attempts": 3,
      "branch": "automation/task-id",
      "pr_url": "",
      "last_review": {},
      "history": []
    }
  }
}
```

Writes are atomic (`tempfile` + `os.replace`).

## Required GitHub configuration

- secret `DEEPSEEK_API_KEY` (DSH headless model auth only).
- `GITHUB_TOKEN` is never passed to DSH; checkout uses `persist-credentials: false`.
- no `CODEX_CMD`; ChatGPT reviews the PR externally.
- `GITHUB_TOKEN` default permissions: contents write, pull-requests write.
- No merge queue or auto-merge.

DSH exits before the outer Orchestrator uses GitHub write credentials. DSH
cannot see `GH_TOKEN`/`GITHUB_TOKEN`; a successful PR ends `REVIEW_PENDING`, not
PASS.

## Headless run

```bash
dsh --profile headless --json "Reply with exactly HEADLESS_READY"
```

Actual local proof is in `P0_HEADLESS_RUN_PROOF.md`.


## P0.1.7 three-job trust boundary

```text
Preflight (read) -> Agent (contents: read only, no GH token) -> Publisher (write, fresh runner)
```

Agent emits only a regular-file artifact with source/base commit SHAs. Publisher
revalidates all paths/hashes/symlinks, checks the source SHA, applies atomically,
reuses an existing Draft PR, and persists state with a temporary credential
helper.
