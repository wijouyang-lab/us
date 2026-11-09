# P10.5.14 Revenue Correction and Secondary Cross-Check

Date: 2026-11-10
Status: **P10_5_14_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Revenue correction

P10.5.13 had selected Product revenue for FY2019 Q2/Q3. Corrected to Total net
sales:

| FY | Quarter | Old (Products) | Corrected Total |
|---|---|---:|---:|
| 2019 | Q2 | 46,565 | **58,015** |
| 2019 | Q3 | 42,354 | **53,809** |

All eight revenue values now match the supplied targets.

## 2. 40-cell secondary cross-check

Compared 5 metrics × 8 quarters against FY2018 10-K Note 11 and FY2019 10-K
Note 12:

```text
SECONDARY_FILING_MATCH: 40
SECONDARY_FILING_MISMATCH: 0
```

This is a secondary filing cross-check, not third-party validation.

## 3. Context audit

The correction fixed values, but 41 cells still have empty/generic context:

- empty context strings;
- `CASHFLOW_STATEMENT` generic context;
- `FY_MINUS_9M` used as context rather than derivation method.

Therefore those cells are not full fact-level traceable.

## 4. Gross margin

Added `GrossMarginPercentage` as a separate derived metric. It is not mixed
with `GrossProfit` amount.

## 5. Status

```text
P10_5_14_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 6. Files

```text
data/research/p10_5_14_aapl_panel/
  aapl_two_fy_panel_final_v4.csv
  aapl_40_secondary_crosscheck.csv
  aapl_revenue_8q.csv
  aapl_gross_margin_audit.csv
  aapl_cashflow_lineage_audit.csv
  aapl_context_audit.csv
  p10_5_14_status.json
docs/research/p10_5_14_revenue_crosscheck.md
tests/test_p10_5_14_revenue_crosscheck.py
```
