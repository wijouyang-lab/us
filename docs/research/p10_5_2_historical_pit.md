# P10.5.2 Historical PIT Database — Blocked Status

Date: 2026-11-09
Status: **P10_5_2_DATA_BLOCKED**
P10.6: **NOT AUTHORIZED**

This branch records the audit outcome without fabricating missing data.

## Preserved

- AAPL 23 Inline XBRL + 40 Separate XBRL + 3 no-XBRL filings.
- P10.5's 30-company / 120-accession parser validation set.

## Not completed

- 64 required AAPL quarterly data sets: only 2024q1 exists.
- No compliant 30-company historical sample.
- No verified delisted company.
- No real amendment/restatement lineage.
- No real as-of query test.
- No real QTD/YTD/FY derivation.
- No Notes data sets.

## Why blocked

The repository lacks:

- a verified delisted-inclusive ticker-to-CIK history;
- the 63 missing AAPL quarterly ZIPs;
- a real numeric restatement pair;
- a real period-derivation layer.

Marking these as complete would require inventing data.

## Decision

```text
P10_5_2_DATA_BLOCKED
P10_6_ALLOWED = false
```

No Shadow. No IBKR. No PAPER-50000.
