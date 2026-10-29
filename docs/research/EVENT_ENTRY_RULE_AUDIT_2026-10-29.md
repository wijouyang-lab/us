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

## New conservative rule

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
