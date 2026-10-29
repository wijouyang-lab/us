# Event Source Coverage and Freshness

Date: 2026-10-29 UTC
Research only.

## Observed at 2026-10-29T05:20Z

| Source | Configured | Real access | Status | Events | Earliest published | Latest published | New IDs | Notes |
|---|---|---|---|---|---|---|---|---|
| Fed press RSS | yes | yes | ok | 20 | 2026-09-16T18:00Z | 2026-10-28T18:00Z | 0 | real read-only probe |
| Fed speeches RSS | yes | yes | ok | 15 | 2026-09-18T13:30Z | 2026-10-15T02:55Z | 0 | actual feed has no newer speech |
| Fed archive cumulative | yes | n/a | verify true | 36 | 鈥?| 鈥?| 鈥?| one archived event absent from current feed |
| BLS CPI | configured | no | skipped_missing_contact_user_agent | 0 | 鈥?| 鈥?| 0 | no real UA |
| BLS employment | configured | no | skipped_missing_contact_user_agent | 0 | 鈥?| 鈥?| 0 | no real UA |
| SEC EDGAR | evaluated | no | not_executed | 0 | 鈥?| 鈥?| 0 | no real UA |
| FRED | evaluated | no | not_executed | 0 | 鈥?| 鈥?| 0 | key/terms not configured |
| BEA | evaluated | no | not_executed | 0 | 鈥?| 鈥?| 0 | key/terms not configured |
| Earnings calendar | evaluated | no | not_executed | 0 | 鈥?| 鈥?| 0 | no approved source |

## Capture result

- captured rows: 35
- unique IDs: 35
- new IDs: **0**
- duplicates vs archive: 35
- archive events: 36
- one old event no longer in current feed: retained, not deleted
- audit with decision after first-seen: **pass**
- archive write: false

The 35 feed rows are **not** 35 new events. They are the same event population
already archived.

## Coverage interpretation

- Source publication window: ~2026-09-16 to 2026-10-28.
- Real first-seen window: one capture day.
- This is **not** 365 days of research coverage.
- Event count is 36 unique, not 35+36.

## Remaining gaps

- BLS/SEC/FRED/BEA not executed.
- SEC exact public timestamps not admitted.
- No earnings source.
- No approved price provider; entry/+1/+5 cannot expand beyond available bars.
