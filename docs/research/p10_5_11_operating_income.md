# P10.5.11 Operating Income Fix and AAPL Panel Status

Date: 2026-11-09
Status: **P10_5_11_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Operating Income fixed

The prior Q4 was incorrectly computed as FY minus Q3, not FY minus 9M. Also the
consolidated Q1 was initially confused with a geographic segment value.

Correct consolidated quarterly Operating Income (USD millions):

| FY | Q1 | Q2 | Q3 | Q4 | FY |
|---|---:|---:|---:|---:|---:|
| 2018 | 26,274 | 15,894 | 12,612 | 16,118 | 70,898 |
| 2019 | 23,346 | 13,415 | 11,544 | 15,625 | 63,930 |

8/8 match the independent targets exactly.

## 2. Panel still not ready

The 72-cell panel exists, but two issues prevent `AAPL_DATASET_READY`:

1. OCF/Capex/FCF values in the merged panel are still at raw-dollar scale,
   while Revenue/Gross Profit/Net Income are USD millions.
2. Core Revenue/Gross Profit/Net Income/EPS rows use the latest comparative
   10-K accession rather than the period-specific 10-Q/10-K accession.

Therefore:

```text
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 tested set only)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 3. Files

```text
data/research/p10_5_11_aapl_panel/
  aapl_operating_income_context_audit.csv
  aapl_operating_income_quarterly_final.csv
  aapl_operating_income_check.csv
  aapl_two_fy_panel_final.csv
  aapl_two_fy_72_cell_validation.csv
  aapl_two_fy_annual_reconciliation.csv
  aapl_unit_normalization_final.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_11_status.json
docs/research/p10_5_11_operating_income.md
tests/test_p10_5_11_operating_income.py
```
