# Event Research Status 鈥?2026-10-29 (PR #398)

## Current archive

| Item | Value |
|---|---:|
| Real runs | 2 |
| First run | 40661139681 |
| Second run | 40807180694 |
| Archive commit | 420469c |
| Unique events | 36 |
| Versions | 36 |
| Observations | 70 |
| Verify | true |

## Readiness

| Horizon | Count |
|---|---:|
| entry | 35 |
| +1 | 0 |
| +5 | 0 |
| pending entry | 1 |
| ready | 0 |
| excluded | 0 |

2026-10-29 US close is not yet available at this report time; no future value
was filled.

## Gate

```text
status: not_eligible
unique_events: 36
coverage: <1 day
entry: 35
+1: 0
+5: 0
```

Required: 200 events, 365 days, complete entry/+1/+5, costs, OOS, multiple
testing, PIT.

## Real Fed RSS read-only probe

At 2026-10-29T05:13:59Z, feeds `fed_all,fed_speeches`, no archive write:

```text
captured rows: 35
new event IDs vs archive: 0
archive unique events: 36
audit: fail_no_data
```

No new event was added. One archived event is no longer in the current feed;
it remains preserved. This is a real API read, not a new archive run.

## Scheduled capture

PR #398's `schedule` is not active until the workflow exists on the default
branch. No scheduled run is claimed. Manual dispatch is likewise unavailable
from a branch-only workflow.

## Source blockers

- BLS/SEC: no valid contact User-Agent; skipped, no placeholder.
- SEC/earnings/macro: not executed; terms and timestamps unverified.
- Price provider: no approved source; HUBB still missing; panel 502/503.
