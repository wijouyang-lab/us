# P0.2.12: Independent Review and Targeted Publisher Core Hardening

Date: 2026-11-19

Repository: `wijouyang-lab/us`  
Branch: `deploy/dsh-automation-p0`  
Base main: `42d3a19ee205713fdfa9d959ff04d1fd79d3b65b`  
Reviewed code HEAD: `e5d106b6e8ad274a71ea82cdff604505f8f82767`  
PR: https://github.com/wijouyang-lab/us/pull/567

## 1. Independent review finding

The injectable `publisher_core.publish()` core had a fail-open identity gap on
the existing-Draft reuse path. It checked that a returned PR was Draft, but did
not verify that the PR's head and base matched the current task, and did not
constrain the PR URL to this repository. A mismatched Draft could therefore be
recorded as the task's `REVIEW_PENDING` PR if the core were wired into the
production publisher.

## 2. Remediation committed

Commits:

- `5895be41e7c9cedd925a38fb66f0d8dbc47c33af` — validate Publisher Draft PR identity.
- `e5d106b6e8ad274a71ea82cdff604505f8f82767` — add adapter identity regression tests.

The core now:

- accepts only canonical HTTPS URLs under
  `github.com/wijouyang-lab/us/pull/<positive integer>`;
- rejects credentials, non-default ports, query strings, fragments, and other
  hosts/repositories;
- checks the head and base refs before reusing an existing Draft PR;
- validates a newly created PR URL before fetching it;
- verifies that the fetched PR URL equals the creation URL and that the PR is
  still Draft with the expected head and base;
- rejects invalid PR URLs stored in terminal task state before reporting a
  successful terminal skip.

Five regression-test functions were added for mismatched refs, invalid URLs,
created-PR readback mismatch, and invalid terminal state.

## 3. CI evidence

Run: https://github.com/wijouyang-lab/us/actions/runs/44467523585

Commit: `e5d106b6e8ad274a71ea82cdff604505f8f82767`

- Full test suite: **1516 passed, 1 skipped, 8 warnings**
- `test`: success
- `dsh-install-verify`: success
- `dsh-subprocess-isolation`: success
- `dsh-process-cleanup-windows`: success
- Dividend Quality frontend tests: passed

This run validates the new adapter-core regression tests. It does not exercise
the production Publisher write path or a real DSH task.

## 4. Production path remains intentionally blocked

The production `publisher.main()` still verifies the GitHub Actions OIDC
context and then returns `BLOCKED:LOCK_NOT_IMPLEMENTED`. It does not call
`_publish_main()` or the adapter core. No real publishing was enabled.

The workflow file `.github/workflows/dsh-task.yml` exists on this PR branch but
does not exist on `main` (the main-branch contents lookup returned 404).
GitHub requires a `workflow_dispatch` workflow to exist on the default branch
before it can be manually triggered. Therefore the DSH task workflow is not yet
available as a deployed/manual service. Its branch-level concurrency
configuration is not runtime evidence of an active production lock.

References:
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency

## 5. Remaining blockers / partial items

- `DISTRIBUTED_LOCK`: BLOCKED. The workflow contains branch-scoped Actions
  concurrency, but the workflow is not on the default branch and no explicit
  Publisher lock adapter/lease is integrated or runtime-tested.
- `PUBLISHER_ADAPTER_PRODUCTION_WIRING`: PARTIAL. Fake-port core is tested;
  production `_publish_main()` does not call it.
- `PYTHON_LOCK_HASHES`: BLOCKED. Requirements are exact-pinned but have no
  hashes; `--require-hashes` is not enabled.
- `PROCESS_TREE_WINDOWS_FAILURE`: PARTIAL. Normal Windows cleanup passes;
  taskkill failure, permission, and lingering-descendant paths are not fully
  fault-injected.
- `READER_THREAD_FAILURE`: PARTIAL. Deterministic blocked-reader timeout
  coverage remains incomplete.
- `FULL_DSH_SERVICE_SPAWN`: PARTIAL. The pinned CLI install and subprocess
  environment isolation pass, but no deployed workflow run has spawned a full
  DSH service.
- `REAL_MODEL_EXECUTION`: DISABLED. No real model call and no API-key read.
- `RAW_LOG_UPLOAD`: NO.

## 6. Repository safety state

- `main` remains at `42d3a19ee205713fdfa9d959ff04d1fd79d3b65b`.
- PR #567 remains Draft / Open / Not Merged.
- No approval, merge, auto-merge, real model execution, API-key read, or raw-log
  upload was performed.
