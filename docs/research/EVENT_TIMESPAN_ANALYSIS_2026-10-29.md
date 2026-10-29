# Event Sample Time-Span Analysis

Date: 2026-10-29 UTC

## Archive facts

| Metric | Value |
|---|---:|
| Unique events | 36 |
| Versions | 36 |
| Observations | 70 |
| `central_bank` | 19 |
| `policy` | 17 |
| Fed press | 21 |
| Fed speeches | 15 |

## first-seen distribution

```text
2026-10-28: 35
2026-10-29: 1
```

- Earliest first-seen: 2026-10-28T09:02:55.813905Z
- Latest first-seen: 2026-10-29T02:35:30.465604Z
- UTC dates represented: **2**
- Observation span: ~17.5 hours, **not** 365 days.

## Published-date distribution

```text
earliest published: 2026-09-11T14:00:00Z
latest published:   2026-10-28T18:00:00Z
```

The published span is ~47 days, but **publication date is not first-seen
coverage**. Historical RSS items were observed on 2026-10-28/29, so the
research observation window remains under one day.

## Why entry/+1/+5 are 0/0/0

- 35 events first seen 2026-10-28 have the 2026-10-28 entry bar.
- 1 event first seen 2026-10-29 has no entry bar yet.
- 2026-10-29 US close is unavailable at this report time; +1 remains pending.
- +5 requires later sessions.
- No zero-fill and no natural-day substitution.

## Archive integrity

- second run added 1 event and 1 version, 35 duplicate observations;
- 0 revisions/retractions/timestamp conflicts;
- previous snapshot unchanged;
- `verify` true.

## Gate gap

```text
events: 36 / 200
observation coverage: 2 UTC dates / 365 days
entry: 35 / 200
+1: 0 / 200
+5: 0 / 200
```

Not eligible. No alpha test.
