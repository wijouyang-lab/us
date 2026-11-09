# P10.5.13 Unresolved Cell Recovery

Date: 2026-11-09
Status: **P10_5_13_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. All 72 cells recovered

| Field | Cells |
|---|---:|
| Revenue | 8 |
| Gross Profit | 8 |
| Operating Income | 8 |
| Net Income | 8 |
| Basic EPS | 8 |
| Diluted EPS | 8 |
| OCF | 8 |
| Capex | 8 |
| FCF | 8 |

```text
panel_cells:                 72
traceable_cells:             72
unresolved_cells:             0
dimension_contaminated:       0
unit_failures:                0
bad_accession_cells:          0
independently_verified:      32
```

## 2. Recovery details

- FY2018 Q1–Q3 Revenue found under `SalesRevenueNet` in the period-specific
  10-Q accessions.
- FY2018 Q4 Revenue 62,900 from FY2018 10-K quarterly context.
- FY2018 Q4 Operating Income 16,118 from FY − 9M, with both accessions.
- FY2019 Q4 Revenue 64,040, Gross Profit 24,313, Net Income 13,686,
  Basic EPS 3.05, Diluted EPS 3.03 from FY2019 10-K Q4 context.
- FY2019 Q4 Operating Income 15,625 from FY − 9M.
- FY2019 Q1 Net Income uses consolidated fact, not RetainedEarningsMember.

## 3. Units

All monetary cells are USD millions; EPS cells are USD/share.
No double scaling; cash-flow 24/24 exact.

## 4. Why not DATASET_READY

Only 32 cells are independently verified (Operating Income 8 + cash flow 24).
Revenue/Gross Profit/Net Income/EPS remain
`TRACEABLE_NOT_INDEPENDENTLY_VERIFIED`. Gross Profit direct/derived and PRE
presentation audit still incomplete.

```text
AAPL_DATASET_READY:        false
AAPL_FACT_PIT_READY:       true (FY2008 limited)
HISTORICAL_UNIVERSE_READY: false
P10_6_ALLOWED:             false
```

No Shadow, no IBKR, no PAPER-50000.

## 5. Files

```text
data/research/p10_5_13_aapl_panel/
  aapl_two_fy_panel_final_v3.csv
  aapl_72_provenance_audit_v3.csv
  p10_5_13_status.json
docs/research/p10_5_13_panel_recovery.md
tests/test_p10_5_13_panel_recovery.py
```
