# Scheduled Research Event Capture Review

Date: 2026-10-29 UTC
Scope: PR #398, branch `research/event-capture-schedule`
Status: Draft; **not enabled**.

## Schedule

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "15 21 * * 1-5"
```

- 21:15 UTC, Monday-Friday.
- After the US regular close (20:00 UTC) in both EDT/EST.
- No weekend schedule.
- Manual dispatch remains available.

GitHub scheduled workflows execute from the default branch. This branch-only
workflow cannot run on a schedule until a reviewed merge; it is not claimed as
active.

## Safety / permissions

- top-level `permissions: contents: read`;
- only `capture` job gets `contents: write`;
- `concurrency: research-event-archive`, no cancellation;
- `timeout-minutes: 15`;
- no production scanner/scoring/stop/ledger/order trigger;
- no `push`/`pull_request` workflow trigger;
- no automatic merge.

## Idempotency / archive

- capture output directory is timestamped;
- `event_archive_store import` deduplicates event IDs/versions;
- existing snapshot is fetched, not overwritten;
- `git diff --cached --quiet` avoids empty commits;
- `verify` runs before push;
- push writes only `research/event-archive`.

## Failure semantics

- source errors remain in metadata/status;
- BLS with missing real contact UA is `skipped_missing_contact_user_agent`;
- no placeholder identity;
- partial source failure is not reported as full success;
- artifact upload runs `if: always()` for diagnosis.

## Artifact retention and public-data review

- artifact name: `research-event-capture-${run_id}`;
- retention: 90 days;
- content observed in a real archive: `events.json`, `metadata.json`,
  `audit.json`, `manifest.json`;
- no raw HTTP bodies or credentials are stored by this workflow;
- events are public Fed releases, but artifacts may still be publicly
  downloadable; this is a residual disclosure risk to review before enabling.
- no secret is printed.

## Data limitations

The schedule only collects events. It does **not** compute entry/+1/+5 returns.
Price readiness remains a separate fail-closed step and must not fill future
trading days.

## Verdict

Prepared for review. Not enabled, not merged, no auto-merge. Manual real runs
remain the only proven execution path.
