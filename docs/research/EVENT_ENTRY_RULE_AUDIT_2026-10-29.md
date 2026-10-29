# Event Entry Rule Audit

Date: 2026-10-29 UTC
Retrospective planning only.

## Old rule

`published_at < session close` -> same session close.

Risks:

- an intraday release cannot be executed at that day's official close using
  daily OHLCV alone;
- a 15:59 ET release has no executable path to the 16:00 close;
- daily bars do not reveal whether a trade at the close was possible;
- using same-day close is a look-ahead/execution assumption unless intraday
  execution data and a fill model exist.

## Availability semantics\n\n- PIT rows use evidence-backed `first_seen` as `available_at`.\n- Retrospective rows set `available_at=null`; their exact publication time is\n  `mapping_time`, not a historical system availability time.\n- Entry planning uses `mapping_time` only; it does not promote retrospective\n  rows to PIT.\n\n## New conservative rule

Default: `next_open`.

- event before session open -> same session open;
- event at/after session open -> next session open;
- after close/weekend/holiday/early close -> next session open;
- missing/ambiguous time -> no entry;
- no natural-day arithmetic.

Definitions:

- **entry**: first executable session open after the event is available;
- **+1**: close of the 1st XNYS session after entry;
- **+5**: close of the 5th XNYS session after entry;
- returns remain null until an approved price provider exists.

This is conservative and executable with daily opens, but it still does **not**
prove a fill at the open; a future execution model must handle auction/slippage.

## Mapping impact: 114 Fed events

| Metric | Value |
|---|---:|
| events | 114 |
| old/new entry dates changed | **74** |
| new date later | 74 |
| unchanged (premarket) | 40 |
| +1 dates changed | 74 |
| +5 dates changed | 74 |

Examples:

| Published UTC | Old entry | New entry |
|---|---|---|
| 2026-10-16T15:00Z | 2026-10-16 close | 2026-10-19 open |
| 2026-10-13T18:00Z | 2026-10-13 close | 2026-10-14 open |
| 2026-10-09T14:00Z | 2026-10-09 close | 2026-10-12 open |

The 74 shifts are all later; no event gets an earlier entry.

## Artifacts

New:

`docs/research/fed_2026_press_label_plan_2026-10-29.json`

Legacy comparison:

`docs/research/fed_2026_press_label_plan_legacy_close_2026-10-29.json`

Both have:

```text
mapped: 114
actual return labels: 0
label_status: pending_price_provider
```

## Tests

`tests/test_event_label_plan.py`: **10 passed**

Covered:

- premarket same-session open;
- intraday next-session open;
- exact close;
- after close;
- weekend;
- Thanksgiving;
- early close;
- cross-year;
- missing time;
- old/new rule difference;
- +1/+5 session mapping;
- no return without provider.
## Available-time audit

PIT dataset:

```text
36 events
available_at missing: 0
available_at == first_seen_at: 36/36
```

PIT entry uses the evidence-backed first-seen time, not publication time.

Retrospective Fed dataset:

```text
114 events
available_at: null
availability_known: false
mapping_time: exact published_at
```

These are planning dates only. The exact publication time is not evidence that
the system could have observed the event at that historical moment. No
retrospective row is promoted to PIT.

## Timezone consistency

All event timestamps are UTC; XNYS schedule open/close is UTC; timezone labels
on the Fed page (`EDT`/`EST`) are converted explicitly. No UTC/ET subtraction is
done manually.
## PIT plan

PIT input uses `decision_at >= available_at`.

```text
events: 36
expected entry dates: 36
2026-10-28 entry: 35
2026-10-29 entry: 1
actual entry price labels: 35
actual +1/+5: 0/0
```

The one 10/29 expected entry has no real close yet. Expected entry dates and
actual price labels are separate states.

See `PIT_LABEL_PLAN_AUDIT_2026-10-29.md`.
