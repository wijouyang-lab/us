# P0 Security Permission Audit

## GitHub permissions

Workflow `.github/workflows/dsh-task.yml` requests only:

```yaml
permissions:
  contents: write
  pull-requests: write
  actions: read
```

No `id-token: write`, no `packages`, no `issues`.

## Branch and PR policy

- `workflow_dispatch` only; no `pull_request_target`.
- First guard rejects `branch == main` or empty branch.
- Draft PR only (`gh pr create --draft`).
- No `gh pr merge` anywhere.
- No auto-approval: reviewer must be independent; `SELF_REVIEW_FORBIDDEN`.
- `can_approve_pull_request_reviews` is false on the repository.
- State/log commits go to the task branch, never `main`.

## Secrets

- `DEEPSEEK_API_KEY` passed only as an env var; never echoed.
- `GITHUB_TOKEN` passed only to `gh`/git.
- `CODEX_CMD` is a command variable, not a printed key.
- Logs may contain model text; they are uploaded as workflow artifacts and are
  not committed by default. State commit only includes `automation/state` and
  `automation/logs`.

## Filesystem

- `git add` is restricted to `docs/research`, `data/research`,
  `tools/research`, `tests`; no `git add -A`.
- No raw market data or SEC JSON is committed by the automation.
- No IBKR, PAPER, Shadow, VPS or purchase path exists.

## Failure behavior

- Headless failure -> `NEEDS_REVISION` until attempt cap, then `FAIL`.
- Reviewer unavailable -> `NEEDS_REVISION`, never PASS.
- Empty diff -> `FAIL`.
- Stale RUNNING -> recovered to QUEUED or terminal FAIL.
- At most 3 attempts.

## Residual risk

- `contents: write` is required to push task branches; it could push main if a
  future change removed the guard. The guard is tested.
- A repository variable `CODEX_CMD` could point to a self-review stub; the
  independent reviewer identity is enforced in code, but not cryptographically.
- GitHub Actions is not a trusted execution boundary for secrets; use a
  short-lived token and rotate `DEEPSEEK_API_KEY`.
