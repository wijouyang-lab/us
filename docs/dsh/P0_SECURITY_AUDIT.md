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

- `DEEPSEEK_API_KEY` is passed only to the DSH child env; DSH subprocess tools
  scrub credential-shaped names. It is never echoed.
- `GH_TOKEN`/`GITHUB_TOKEN` are never passed to DSH.
- checkout uses `persist-credentials: false`; no token in `.git/config`.
- outer push uses a per-command `credential.helper=!gh auth git-credential`,
  not a persisted credential.
- no `CODEX_CMD` production dependency (single-agent DSH mode).
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
- ChatGPT PR review is external; DSH never claims PASS.
- `.protected=true` alone is not enough: direct pushes, force pushes, required
  CI checks and required human review still need separate verification.
- GitHub Actions is not a trusted execution boundary for secrets; use a
  short-lived token and rotate `DEEPSEEK_API_KEY`.


## P0.1.7 Publisher filesystem

- no symlink anywhere in a target's parent chain;
- target and broken-symlink targets rejected;
- artifact manifest must be a regular file and match schema/hash/size;
- files/deletes cannot overlap or duplicate;
- Publisher validates all paths before any write and uses atomic replace;
- state push uses the same per-command credential helper.
