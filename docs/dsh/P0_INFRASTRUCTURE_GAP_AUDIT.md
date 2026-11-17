# P0 Infrastructure Gap Audit

Date: 2026-11-17
Repository: `wijouyang-lab/us`
Branch: `feature/dsh-headless-automation`

## Current state (before P0)

| Area | Finding |
|---|---|
| Actions | enabled, `allowed_actions=all`, default workflow permissions `write` |
| Existing workflows | 30+ data/research workflows; `quant-research.yml`, `review.yml`, `quant-fix-tests.yml` exist |
| DSH headless | CLI `0.2.0-rc.2` supports `dsh --profile headless --json` |
| DSH auth | local profile credentials work; GitHub must provide `DEEPSEEK_API_KEY` |
| Task queue | none |
| Persistent state | none for DSH tasks |
| Crash recovery | none |
| Draft PR automation | none |
| Codex reviewer | no `codex` CLI installed locally; interface must be supplied via `CODEX_CMD` |
| Auto-merge | no DSH merge path; `can_approve_pull_request_reviews=false` |

## Gaps

1. No queue/state/recovery for agent tasks.
2. No workflow that invokes DSH headless.
3. No independent reviewer adapter; cannot safely self-approve.
4. No attempt cap/terminal FAIL state.
5. No draft-PR-only policy enforced in code and workflow.

## Reuse

- `tools/ci/push_with_retry.sh` is existing push resilience; not reused because
  this loop must never push to `main`.
- `actions/checkout`, `setup-python`, `setup-node`, artifact upload are reused.
- Existing GitHub Actions permissions are used; no new privileged action.

## Decision

Build a separate, manual-dispatch DSH workflow with:
- atomic JSON state;
- stale RUNNING recovery;
- max 3 attempts;
- DSH headless logs;
- draft PR only;
- independent reviewer interface;
- no merge operation.
