# PR #398 First Real Run Checklist

Date: 2026-10-29 UTC
Status: prepared; **not executed**. Do not merge without user approval.

## Before merge

- [ ] Workflow exists on default branch after approved merge.
- [ ] PR remains Draft until approval.
- [ ] No auto-merge.
- [ ] Confirm `FEEDS` default fallback line exists.
- [ ] Confirm only `research/event-archive` is written.
- [ ] Confirm top-level read / job write permissions.
- [ ] Confirm cron `15 21 * * 1-5` and +20 minute audit buffer.

## First manual run

- [ ] Trigger `Research Event Capture` on default branch with default feeds.
- [ ] Record workflow run ID, UTC start/end, conclusion.
- [ ] Confirm artifact name/ID.
- [ ] Download artifact and inspect `events.json`, `metadata.json`, `audit.json`.
- [ ] Confirm source statuses: Fed ok; BLS skipped if no UA.
- [ ] Confirm no secret printed.

## Archive verification

- [ ] Archive branch has a new commit **or** no commit when no changes.
- [ ] `event_archive_store verify` succeeds.
- [ ] Old run snapshots unchanged.
- [ ] Unique events/versions/observations deltas recorded.
- [ ] Duplicate observations not counted as new events.

## Failure handling

- [ ] If capture fails, no archive overwrite.
- [ ] If archive push fails, report exact error.
- [ ] If no new events, no empty commit.
- [ ] If some sources fail, status remains partial/failed, not full success.

## First scheduled run

- [ ] Confirm GitHub actually schedules on default branch.
- [ ] Record scheduled run ID and whether it matches 21:15 UTC intent.
- [ ] Repeat archive/artifact checks.
- [ ] Verify no production path side effects.

## Price observations

- [ ] Only after real market close, run readiness.
- [ ] Do not fill +1/+5 on weekends/holidays.
- [ ] No zero-fill for missing returns.

## Current blockers

- [ ] No real BLS/SEC User-Agent.
- [ ] No approved price provider; HUBB missing.
- [ ] PR #398 not merged.
