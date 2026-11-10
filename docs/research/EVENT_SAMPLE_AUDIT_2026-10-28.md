# Event Sample Audit and Accumulation Plan

Date: 2026-10-28
Research only. No production changes.

## Current real sample

Source: first real archive run `40661139681`.

| Metric | Value |
|---|---:|
| Unique events | **35** |
| `policy` | 17 |
| `central_bank` | 18 |
| Earliest `source_published_at` | 2026-09-11 |
| Latest `source_published_at` | 2026-10-16 |
| Earliest `first_seen_at` | 2026-10-28T09:02:55Z |
| Latest `first_seen_at` | 2026-10-28T09:02:56Z |
| Real `first_seen_at` present | **35/35** |
| Explicit `event_time` | **0/35** |
| Publication-forward candidates | **35** |
| Entry bars | **0** |
| +1 complete | **0** |
| +5 complete | **0** |

All events were first observed in one capture window. Historical
`published_at` dates do **not** become historical `first_seen_at`.

## Pre-registration gap

| Gate | Required | Current | Gap |
|---|---:|---:|---:|
| Unique events | 200 | 35 | **165** |
| Coverage span | 365 days | <1 day | **~365 days** |
| Entry results | 200 | 0 | 200 |
| +1 results | 200 | 0 | 200 |
| +5 results | 200 | 0 | 200 |
| OOS windows | 2 | 0 | 2 |

The formal gate result is `not_eligible`, not merely a warning:
`docs/research/event_experiment_gate_2026-10-28.json`.

## What RSS backfill can and cannot do

Can:

- Preserve the historical publication dates present in the RSS window.
- Add older headlines only if the provider exposes them and the system records
  a real observation time now.
- Preserve versions and source URLs.

Cannot:

- Reconstruct a historical `first_seen_at` that was never observed.
- Turn a publication date into a first-seen timestamp.
- Count duplicated/re-imported events as new unique events.
- Solve the 12-month coverage requirement or the +1/+5 bar requirement.

Backfilled observations may be used only as forward observations from the
actual capture time, not as historical PIT evidence.

## Accumulation plan

### Minimum frequency

- At least **once daily after US close** (around 21:15 UTC).
- Preferred: two manual/scheduled attempts per day, one pre-close and one
  post-close, to reduce first-seen lag.
- 200 events at the current ~7 events/week needs roughly 29 weeks; the
  12-month lead-time gate cannot be shortened.

### Failure/retry

- Per-source failures do not block Fed.
- Retry once per source after a short delay.
- Preserve error status; never overwrite a valid archive commit on failure.
- BLS/SEC remain skipped until real contact UA secrets exist.

### Dedup and revisions

- Event identity: `event_id` (source + source ID).
- Version identity: content/timestamp hash.
- Same version + later observation = duplicate observation, not new event.
- Changed content = new version, old version retained, `supersedes` link.
- Retractions retained and marked, not deleted.

### Monitoring

- run success/failure;
- per-source status and event count;
- new unique events vs duplicate observations;
- new versions / revisions / retractions;
- archive `verify` status and latest run age;
- missing future bars and price-basis status.

## Timing

Current UTC is still 2026-10-28. 10/28 provider close and the second real
cross-day run are not available yet. No sample was fabricated.
