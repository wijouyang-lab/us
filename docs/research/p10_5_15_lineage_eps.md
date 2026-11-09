# P10.5.15 Fact Lineage and Annual EPS

Date: 2026-11-09
Status: **P10_5_15_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. FY2019 Q2/Q3 revenue

Corrected to Total net sales:

```text
Q2: 58,015 = Products 46,565 + Services 11,450
Q3: 53,809 = Products 42,354 + Services 11,455
```

`raw_value` and `value` now both refer to the total, with component values
stored; derivation is `RECONSTRUCTED_FROM_COMPONENTS`.

## 2. 40-cell secondary filing cross-check

Actual secondary facts were extracted from FY2019 10-K accession
`0000320193-19-000119` via XBRL facts, not a TARGET constant.

```text
SECONDARY_FILING_MATCH: 40
MISMATCH:                0
UNRESOLVED:              0
```

Limitation: the source is `SECONDARY_XBRL_FACT_IN_10-K`, not a parsed Note 12
HTML table cell. Table/row/column locator is therefore not yet available.

## 3. Annual EPS

Using Decimal and annual weighted-average shares from the 10-Ks:

| FY | Basic recalc | Diluted recalc | Status |
|---|---:|---:|---|
| 2018 | 12.013415 | 11.905940 | PASS |
| 2019 | 11.965783 | 11.885789 | PASS |

Quarterly EPS was not summed for the annual check.

## 4. Gross margin

`GrossMarginPercentage` remains a separate derived metric; no mixing with
Gross Profit amount. PRE/label audit still incomplete.

## 5. Lineage

```text
core panel cells:        72
fact-level traceable:    29
lineage incomplete:      43
context missing:         43
unit failures:            0
```

43 cells still have empty/generic context (`CASHFLOW_STATEMENT`, `FY_MINUS_9M`,
or empty); those are not claimed as full fact-level traceable.

## 6. Status

```text
P10_5_15_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_15_aapl_panel/
  aapl_core_panel_v5.csv
  aapl_gross_margin_percentage_v5.csv
  aapl_40_secondary_v5.csv
  aapl_annual_eps_reconciliation.csv
  aapl_context_audit_v5.csv
  p10_5_15_status.json
docs/research/p10_5_15_lineage_eps.md
tests/test_p10_5_15_lineage_eps.py
```
