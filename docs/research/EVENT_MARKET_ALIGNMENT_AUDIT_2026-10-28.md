# Event-to-Market Time Alignment Audit

Date: 2026-10-28
Research only. No strategy, signal, or production changes.

## Inputs

- 35 real Fed events from archive run `40661139681`
- Price panel: `research_price_history_sp500_10y.csv`-equivalent local panel,
  last bar **2026-10-14**
- Decision timestamp: `2026-10-28T09:30:00Z`

Output JSON:

`docs/research/event_market_alignment_audit_2026-10-28.json`

## Time definitions

| Field | Meaning |
|---|---|
| `event_time` | Actual occurrence time; never inferred from publication |
| `source_published_at` | Provider-stated publication time |
| `first_seen_at` | Actual system observation time |
| `available_at` | Conservative max(source publication, first seen, update first seen) |
| `decision_at` | Explicit decision timestamp |
| price bar | Daily bar keyed by calendar date, close assumed 16:00 America/New_York |

## Alignment rule

For a daily bar to be usable:

1. `decision_at` must be at or after `available_at`;
2. the bar's **close** must be strictly after `available_at`;
3. the bar must be a real trading date present in the price panel;
4. the event must have an aware `source_published_at` and `first_seen_at`;
5. source URL and event ID must be present;
6. date-only timestamps are rejected;
7. if a revision's first-seen is after `decision_at`, it is not used.

Close is 16:00 America/New_York, with DST handled by `zoneinfo`. For daily
bars, a pre-market/intraday event can use the same-day close; an event at or
after 16:00 ET, or on a non-trading day, uses the next trading day's close.

## Classification

| Status | Rule |
|---|---|
| `strict_pit` | All required timestamps aware, source/ID present, `event_time` explicit, entry close strictly after availability |
| `descriptive_only` | Availability is valid, but `event_time` is missing/uncertain; no exact occurrence timing claim |
| `excluded` | Missing/naive/date-only timestamp, missing source URL/ID, decision before availability, or no trading bar after availability |

## Actual result

| Metric | Value |
|---|---:|
| Selected events | 35 |
| Strict PIT | **0** |
| Descriptive only | **0** |
| Excluded | **35** |
| Look-ahead flags | 0 |
| Missing `event_time` | 35 |
| Date-only timestamps | 0 |

Every event was excluded for two independent reasons:

```text
event_time_missing
no_price_bar_after_available
```

The price panel ends **2026-10-14**, while the real events were first observed
**2026-10-28**. There is no price bar after `available_at`; using an earlier
close would be look-ahead. This is a data-panel gap, not an event-timing pass.

Therefore the current 35 events are **not eligible for strict PIT event
research**. They can be retained as observation data, but not used for strategy
or market-reaction analysis until a price panel covers post-observation dates.

## What the tests prove

`tests/test_event_market_alignment_audit.py` 鈥?**8 passed**:

- pre-market event uses same-day close;
- exact 16:00 ET uses next session;
- after-close event uses next session;
- weekend event uses next trading day;
- winter/summer DST close instants differ correctly;
- date-only and naive timestamps are excluded;
- missing `event_time` is descriptive-only, not strict;
- late revision is not selected at an earlier decision;
- no look-ahead flag.

These are synthetic alignment tests. They do not override the real-data result
that the current price panel has no post-observation bars.

## Minimum research threshold

### Strict PIT eligible

Must have all of:

- event ID, source, source URL;
- timezone-aware `source_published_at`;
- timezone-aware `first_seen_at`;
- explicit timezone-aware `event_time`;
- conservative `available_at`;
- `decision_at >= available_at`;
- trading bar with close strictly after `available_at`;
- selected version known at `decision_at`.

### Descriptive only

- availability timestamps are valid;
- but `event_time` is missing, date-only, or occurrence timing is otherwise
  uncertain.
- May be used for counts/descriptive analysis only.

### Excluded

- missing/naive/date-only timestamps;
- missing source/URL/ID;
- decision before availability;
- no post-availability trading bar;
- late revision selected incorrectly;
- any look-ahead condition.

## Consequence

No event alpha test is run. The event dataset currently has:

```text
35 observations, 0 strict PIT-eligible events
```

This is consistent with the earlier project rule: collection success is not
alpha, and calendar alignment must be proven before using events as features.

## BLS / SEC

- BLS: `skipped_missing_contact_user_agent`
- SEC: 0 requests, `SEC_USER_AGENT` absent
- No placeholder contacts or fake requests
