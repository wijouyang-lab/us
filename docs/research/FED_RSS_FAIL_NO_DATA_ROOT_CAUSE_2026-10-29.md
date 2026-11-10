# Fed RSS `fail_no_data` Root Cause

Date: 2026-10-29 UTC
Research only.

## Finding

`fail_no_data` was **not** a feed failure and not caused by zero new event IDs.

It is `coverage_audit.audit_status` when **no events are available at the audit
decision time**.

The first probe used:

```text
decision_at: 2026-10-29T05:13:00Z
capture first_seen: 2026-10-29T05:13:59Z
```

All 35 captured events had `first_seen_at` after `decision_at`, so the as-of
audit correctly excluded them and reported:

```text
total_events: 0
audit_status: fail_no_data
```

The sources themselves were:

```text
fed_all: ok, 20 events
fed_speeches: ok, 15 events
```

## Repeat with a post-capture decision

Second real read:

```text
capture first_seen: 2026-10-29T05:20:23Z
decision_at: 2026-10-29T05:30:00Z
captured: 35
new IDs vs archive: 0
audit: pass
```

This proves:

- feed returned valid data;
- no-new-IDs is compatible with a passing audit;
- `fail_no_data` is an as-of timing state, not a source failure.

## Current feed vs archive

- archive: 36 unique events;
- current feed IDs: 35;
- 0 new IDs;
- one archived event is no longer in the current feed;
- the old event remains in the immutable archive and is not deleted.

## Fix

The workflow now uses a **+20 minute** decision buffer instead of +10. The
capture step has a 15-minute timeout, so the audit decision should fall after
capture completes even with normal latency.

## Regression tests

`tests/test_run_event_capture_cycle.py`:

- decision before first-seen -> `fail_no_data`;
- available event at decision -> audit not `fail_no_data`, total_events 1;
- successful empty feed -> source status `ok` but `fail_no_data`;
- repeated capture dedup remains.

`tests/test_research_event_workflow.py` asserts the +20 minute buffer.

## Status semantics

| State | Meaning |
|---|---|
| source `status=ok`, audit `pass`, new IDs 0 | healthy, no new events |
| source `status=ok`, audit `fail_no_data` | no event available at decision time |
| source empty + audit `fail_no_data` | valid empty response |
| source error/skipped | explicit failure/skip, not success |
| archived event absent from feed | normal feed-window loss; keep archive |
