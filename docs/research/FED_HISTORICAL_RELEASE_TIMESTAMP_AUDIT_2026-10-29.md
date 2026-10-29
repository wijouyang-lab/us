# Fed Historical Release Timestamp Audit

Date: 2026-10-29 UTC
Retrospective only. No PIT promotion.

## Sample audit

Five official pages across months/types:

| Page | HTTP | Page date | Release time | TZ | UTC | Hash prefix |
|---|---:|---|---|---|---|---|
| `bcreg20260930a.htm` | 200 | 2026-09-30 | 09:00 | EDT | 2026-09-30T13:00Z | `da1e6482` |
| `enforcement20261016a.htm` | 200 | 2026-10-16 | 11:00 | EDT | 2026-10-16T15:00Z | `606605d2` |
| `monetary20261013a.htm` | 200 | 2026-10-13 | 14:00 | EDT | 2026-10-13T18:00Z | `6af89db1` |
| `orders20260804a.htm` | 200 | 2026-08-04 | 16:30 | EDT | 2026-08-04T20:30Z | `315e34d3` |
| `other20261009a.htm` | 200 | 2026-10-09 | 10:00 | EDT | 2026-10-09T14:00Z | `81a49750` |

Fields used:

- page date: `p.article__time` text;
- exact time: body text `For release at H:MM a.m./p.m. EDT|EST`;
- timezone: explicit `EDT`/`EST`;
- conversion: EDT=-4, EST=-5, no seasonal guessing;
- missing/ambiguous/invalid time -> date-only or failed.

Sample JSON:

`docs/research/fed_release_time_sample_2026-10-29.json`

## Expanded 114-page parse

Real fetch of all 114 indexed Fed 2026 press pages:

```text
count: 114
exact timestamps: 114
date-only: 0
failed: 0
timezones: EDT 92, EST 22
published range: 2026-01-06T16:00Z .. 2026-10-16T15:00Z
```

Expanded index:

`docs/research/fed_2026_press_retrospective_timed_2026-10-29.json`

Every row remains:

```text
observation_mode: retrospective_backfill
first_seen_at_utc: null
pit_eligible: false
```

The new data adds **exact historical publication timestamps**, not PIT
qualification. It still cannot enter the 36-event PIT count.

## Licensing

Fed Board disclaimer (https://www.federalreserve.gov/disclaimer.htm):

> Unless otherwise indicated, information on Board's website is in the public
> domain and may be copied and distributed without permission. Please cite to
> the Board as the source of the information.

Non-Board photos/graphics/materials are excluded and require the original
rightsholder's permission.

Conclusion: Fed text/press pages are usable for research storage with
attribution, subject to excluding third-party material. This is a written
public-domain basis, unlike Sina/AKShare.

## Caveats

- Release time is the page's stated "For release at" time, not first-seen.
- Page date and URL must still agree; parser fail-closes if date missing.
- No revision history was measured.
- No return labels exist because no approved price provider.
- No historical `first_seen_at` can be reconstructed.
