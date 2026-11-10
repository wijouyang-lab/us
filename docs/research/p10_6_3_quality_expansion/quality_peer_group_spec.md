# Quality V1 Peer Group Specification

The existing V1 code is authoritative and was not modified.

## Grouping

Peer group key:

```text
model_family + accounting_standard + cutoff_date
```

This pilot uses `TECHNOLOGY / US_GAAP` separately at each of the four cutoff
dates.

## Minimum peers

`MIN_PEER = 30` applies to the full scoring group for each cutoff, not to each
individual metric. A company is included only when all four metrics are present:

```text
ROE, ROA, CFO/Assets, Liabilities/Assets
```

Companies with a missing metric are excluded from that date's score and remain
visible in the panel with a missing reason. They are not filled with zero.

## Percentiles

- winsorize each metric at 1st/99th percentile within the peer group;
- rank with average percentile × 100;
- leverage percentile is inverted;
- score = 0.30 × ROE pct + 0.25 × ROA pct + 0.25 × CFO/Assets pct
  + 0.20 × leverage pct.

## Dates

Each cutoff is independent. No company is carried forward from a later date.

## Sample

60 Technology/US_GAAP names, including XLNX as a non-surviving acquisition case.
A group below 30 valid names is `NOT_SCORED_PEER_GROUP_TOO_SMALL`.
