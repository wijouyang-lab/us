# Event Research Dataset Audit

Date: 2026-10-29 UTC
Research only. No archive mutation.

## Dataset build

`tools/research/event_research_dataset.py` joins the real archive with actual
readiness labels and emits:

```text
docs/research/event_research_dataset_2026-10-29.json
```

Current build:

| Field | Value |
|---|---:|
| Events | 36 |
| `forward_pit` | 36 |
| `retrospective_backfill` | 0 |
| `unknown` | 0 |
| entry labels | 35 |
| +1 labels | 0 |
| +5 labels | 0 |
| first-seen 2026-10-28 | 35 |
| first-seen 2026-10-29 | 1 |

## Field separation

Each row records:

- `published_at`;
- `first_seen_at`;
- `available_at = max(published, first_seen, update_first_seen)`;
- `decision_at = available_at` (earliest decision time);
- `source`, stable `source_url`, `content_hash`;
- `timestamp_precision`;
- `observation_mode`;
- `backfill_status`;
- `pit_eligible`;
- `availability_status`;
- `entry_bar_date`, `result_1d_date`, `result_5d_date`;
- `label_status`, `missing_reason`.

The archive itself was not rewritten.

## PIT / retrospective isolation

- A row is `pit_eligible` only when mode is `forward_pit`, publication and
  first-seen exist, and `available_at` exists.
- A row marked `retrospective_backfill` **without** an explicit
  `backfill_source` is downgraded to `unknown`.
- No retrospective rows are currently included.
- The 36 events are forward observations, but their **published dates**
  (2026-09-11..2026-10-28) are not treated as first-seen coverage.

## Why coverage is still short

- first-seen dates: 2026-10-28 (35), 2026-10-29 (1);
- observation span: ~17.5 hours / 2 UTC dates;
- published span ~47 days is **not** observation coverage;
- 1 event has no entry bar yet;
- 35 have entry, but no 2026-10-29 close => +1 pending; +5 later.

## Labels

- 35 rows `pending_future_1d_bar`;
- 1 row `pending_future_entry_bar`;
- 0 zero-filled returns;
- 0 synthetic labels.

## Gate

```text
not_eligible
36 / 200 events
2 UTC dates / 365 days
entry 35 / 200
+1 0 / 200
+5 0 / 200
```

No cost/OOS/multiple-testing or alpha run is authorized.

## Tests

`tests/test_event_research_dataset.py`: **5 passed**

Covered:

- forward PIT available time = first-seen max;
- retrospective without backfill source is rejected/downgraded;
- missing publication fails PIT eligibility;
- all-missing timestamps not PIT;
- missing readiness labels are not zero-filled.

## Limitation

The dataset builder can label historical/backfilled rows, but it cannot turn a
historical publication date into a historical first-seen time. Retrospective
rows must be explicitly marked and remain separate from PIT counts.
