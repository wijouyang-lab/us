# Event Capture Schedule Proposal

Date: 2026-10-28
Research only. Proposal Draft; not merged.

## Trigger

Add one weekday post-close scheduled run:

```yaml
schedule:
  - cron: "15 21 * * 1-5"
```

This is 21:15 UTC, after the US regular close, Monday-Friday. It is paired with
the existing `workflow_dispatch` manual trigger.

## Why

- Fed releases/speeches occur on weekdays.
- A post-close run minimizes first-seen lag for same-day events.
- 35 events in the first observation window implies roughly 7/week; 200 unique
  events needs about 29 weeks.
- The 12-month minimum coverage cannot be shortened by a schedule.

## Controls

- top-level `contents: read`;
- only capture job has `contents: write`;
- writes only `research/event-archive`;
- `concurrency` group `research-event-archive`, no cancellation;
- no production workflow dependency;
- no secret printing;
- artifact retained 90 days.

## Review requirement

This is a separate Draft PR. It must be reviewed before merge. It is not part of
PR #397 and is not auto-merged.
